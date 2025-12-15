# app/endpoints/user/practice.py
from __future__ import annotations

from typing import List, Any

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Path,
    status,
    Body,
)
from sqlalchemy.orm import Session

from core.deps import get_db, get_current_user
from core import config
from models.user.account import AppUser

from crud.user.practice import (
    practice_session_crud,
    practice_session_model_crud,
    practice_response_crud,
)

from schemas.base import Page
from schemas.user.practice import (
    PracticeSessionCreate,
    PracticeSessionUpdate,
    PracticeSessionResponse,
    PracticeSessionModelCreate,
    PracticeSessionModelUpdate,
    PracticeSessionModelResponse,
    PracticeResponseCreate,
    PracticeResponseUpdate,
    PracticeResponseResponse,
    PracticeTurnRequest,
    PracticeTurnResponse,
    GenerationParams,
)

from service.user.practice import (
    ensure_my_session,
    ensure_my_session_model,
    ensure_my_response,
    set_primary_model_for_session,
    run_practice_turn_for_session,
)

router = APIRouter()


def _init_default_models_for_session(db: Session, *, session_id: int) -> None:
    """
    세션 생성 직후, 튜닝 UI가 바로 뜰 수 있게 기본 모델들을 미리 생성해둠.
    - config.PRACTICE_MODELS 중 enabled=True 모델들을 전부 생성
    - primary는 default=True인 모델(없으면 첫 모델)로 1개만 보장
    """
    existing = practice_session_model_crud.list_by_session(db, session_id=session_id)
    if existing:
        return

    enabled = [
        (k, v) for k, v in config.PRACTICE_MODELS.items()
        if v.get("enabled") is True
    ]
    if not enabled:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="no_enabled_practice_models",
        )

    # primary 후보: default=True 우선, 없으면 첫 enabled
    primary_key = None
    for k, v in enabled:
        if v.get("default") is True:
            primary_key = k
            break
    if primary_key is None:
        primary_key = enabled[0][0]

    primary_candidate_id: int | None = None

    for k, v in enabled:
        model_name = v.get("model_name") or k
        data_in = PracticeSessionModelCreate(
            session_id=session_id,
            model_name=model_name,
            # 일단 False로 만들고, 아래에서 set_primary로 1개만 보장
            is_primary=False,
            generation_params=dict(config.PRACTICE_DEFAULT_GENERATION),
        )
        created = practice_session_model_crud.create(db, data_in)
        if k == primary_key and primary_candidate_id is None:
            # CRUD가 반환하는 PK 이름이 session_model_id라고 가정(프로젝트 기존 흐름)
            primary_candidate_id = getattr(created, "session_model_id", None)

    db.commit()

    if primary_candidate_id:
        set_primary_model_for_session(
            db,
            me=None,  # 서비스가 me를 꼭 쓰면 여기서 쓰지 말고 아래처럼 endpoint에서 처리해
            session_id=session_id,
            target_session_model_id=primary_candidate_id,
        )
        db.commit()


# =========================================
# Practice Sessions
# =========================================
@router.get(
    "/sessions",
    response_model=Page[PracticeSessionResponse],
    operation_id="list_my_practice_sessions",
    summary="내 세션 불러오기",
)
def list_my_practice_sessions(
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    rows, total = practice_session_crud.list_by_user(
        db,
        user_id=me.user_id,
        page=page,
        size=size,
    )
    items = [PracticeSessionResponse.model_validate(r) for r in rows]
    return {"items": items, "total": total, "page": page, "size": size}


@router.post(
    "/sessions",
    response_model=PracticeSessionResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="create_practice_session",
    summary="새 대화(세션): 세션 생성 + 기본 모델 미리 생성",
)
def create_practice_session(
    data: PracticeSessionCreate,
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    """
    새 대화 버튼 UX:
    1) 세션 생성
    2) 기본 세션모델(여러개) 미리 생성 -> 바로 PATCH로 튜닝 가능
    """
    class_id = getattr(data, "class_id", None)
    if not class_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="class_id_required")

    session = practice_session_crud.create(
        db=db,
        data=data,
        user_id=me.user_id,
    )

    # 기본 모델들 생성(튜닝 UI 즉시 가능)
    # NOTE: set_primary_model_for_session가 me를 꼭 요구하면,
    # 여기 helper에서 me=None 쓰지 말고 endpoint에서 primary 보장 로직을 직접 처리해.
    _init_default_models_for_session(db, session_id=session.session_id)

    return PracticeSessionResponse.model_validate(session)


# =========================================
# Quick Run (바로 입력) - session_id==0 제거 대체
# =========================================
@router.post(
    "/sessions/run",
    response_model=PracticeTurnResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="run_practice_turn_for_new_session",
    summary="바로 입력: 새 세션 생성 + 첫 턴 실행",
)
def run_practice_turn_new_session_endpoint(
    class_id: int = Query(..., ge=1, description="이 연습 세션이 속한 Class ID (partner.classes.id)"),
    project_id: int | None = Query(
        None,
        ge=1,
        description="새 세션 생성 시 연결할 Project ID (user.projects.project_id)",
    ),
    body: PracticeTurnRequest = Body(...),
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    """
    - 새 세션 생성 + 모델 구성 + 첫 턴 실행을 한번에 처리(빠른 시작)
    - 기존의 session_id==0  외부 API에서 제거(내부에서 돌림)
    `gpt-4o-mini`, `gpt-5-mini` , `gpt-3.5-turbo` , `claude-3-haiku-20240307` , `gemini-2.5-flash`
    """
    turn_result = run_practice_turn_for_session(
        db=db,
        me=me,
        session_id=0,          # 내부적으로만 사용(외부 API에서 숨김)
        class_id=class_id,
        project_id=project_id,
        body=body,
    )
    db.commit()
    return turn_result


# =========================================
# LLM /chat (기존 세션 전용)
# =========================================
@router.post(
    "/sessions/{session_id}/chat",
    response_model=PracticeTurnResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="run_practice_turn_for_existing_session",
    summary="기존 세션에서 실습 턴 실행",
)
def run_practice_turn_endpoint(
    session_id: int = Path(..., ge=1, description="1 이상: 해당 세션에서 이어서 대화"),
    body: PracticeTurnRequest = Body(...),
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    """
    - session_id > 0: 기존 세션에서 실행
    - class_id는 세션에 저장된 값을 사용(쿼리로 안 받음)
    - body.knowledge_id가 있으면 이번 턴에서만 override 가능
     세션에 등록된 모델 중 선택 실행 모델 :
        `gpt-4o-mini`, `gpt-5-mini` , `gpt-3.5-turbo` , `claude-3-haiku-20240307` , `gemini-2.5-flash`
    """
    session = ensure_my_session(db, session_id, me)

    turn_result = run_practice_turn_for_session(
        db=db,
        me=me,
        session_id=session_id,
        class_id=session.class_id,
        project_id=session.project_id,
        body=body,
    )
    db.commit()
    return turn_result




@router.get(
    "/sessions/{session_id}",
    response_model=PracticeSessionResponse,
    operation_id="get_practice_session",
    summary="세션 대화목록"
)
def get_practice_session(
    session_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    session = ensure_my_session(db, session_id, me)

    # 이 세션에 속한 모든 응답 조회
    resp_rows = practice_response_crud.list_by_session(
        db,
        session_id=session.session_id,
    )
    resp_items = [
        PracticeResponseResponse.model_validate(r) for r in resp_rows
    ]

    return PracticeSessionResponse(
        session_id=session.session_id,
        user_id=session.user_id,
        class_id=session.class_id,
        project_id=session.project_id,
        # NEW: 세션에 연결된 지식베이스도 응답에 포함
        knowledge_id=getattr(session, "knowledge_id", None),
        title=session.title,
        created_at=session.created_at,
        updated_at=session.updated_at,
        notes=getattr(session, "notes", None),
        responses=resp_items,
    )


@router.patch(
    "/sessions/{session_id}",
    response_model=PracticeSessionResponse,
    operation_id="update_practice_session",
    summary="세션 제목/메타 수정"
)
def update_practice_session(
    session_id: int = Path(..., ge=1),
    data: PracticeSessionUpdate = ...,
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    """
    - body: class_id / project_id / knowledge_id / title / notes 중 일부만 PATCH
    """
    _ = ensure_my_session(db, session_id, me)
    updated = practice_session_crud.update(db, session_id=session_id, data=data)
    db.commit()
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="session not found")
    return PracticeSessionResponse.model_validate(updated)


@router.delete(
    "/sessions/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="delete_practice_session",
    summary="세션 삭제"
)
def delete_practice_session(
    session_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    _ = ensure_my_session(db, session_id, me)
    practice_session_crud.delete(db, session_id=session_id)
    db.commit()
    return None


# =========================================
# Practice Session Models
# =========================================
@router.get(
    "/sessions/{session_id}/models",
    response_model=List[PracticeSessionModelResponse],
    operation_id="list_practice_session_models",
)
def list_practice_session_models(
    session_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    _ = ensure_my_session(db, session_id, me)
    models = practice_session_model_crud.list_by_session(db, session_id=session_id)
    return [PracticeSessionModelResponse.model_validate(m) for m in models]


@router.post(
    "/sessions/{session_id}/models",
    response_model=PracticeSessionModelResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="create_practice_session_model",
    summary="세션에 모델 추가",
)
def create_practice_session_model(
    session_id: int = Path(..., ge=1),
    data: PracticeSessionModelCreate = ...,
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    _ = ensure_my_session(db, session_id, me)
    data_in = data.model_copy(update={"session_id": session_id})
    model = practice_session_model_crud.create(db, data_in)
    db.commit()
    return PracticeSessionModelResponse.model_validate(model)


@router.patch(
    "/models/{session_model_id}",
    response_model=PracticeSessionModelResponse,
    operation_id="user_update_practice_session_model",
    summary="LLM 파라미터 튜닝",
)
def update_practice_session_model(
    session_model_id: int = Path(..., ge=1),
    data: PracticeSessionModelUpdate = ...,
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    model, _session = ensure_my_session_model(db, session_model_id, me)

    # 1) is_primary=True 인 경우: primary 토글 흐름
    if data.is_primary is True:
        target = set_primary_model_for_session(
            db,
            me=me,
            session_id=model.session_id,
            target_session_model_id=session_model_id,
        )
        return PracticeSessionModelResponse.model_validate(target)

    # 2) is_primary=False 또는 안 온 경우: 일반 필드만 수정
    update_data = data.model_dump(exclude_unset=True)
    update_data.pop("is_primary", None)

    if update_data:
        model = practice_session_model_crud.update(
            db,
            session_model_id=session_model_id,
            data=update_data,
        )
        db.commit()

    return PracticeSessionModelResponse.model_validate(model)


@router.delete(
    "/models/{session_model_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="delete_practice_session_model",
)
def delete_practice_session_model(
    session_model_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    _model, _session = ensure_my_session_model(db, session_model_id, me)
    practice_session_model_crud.delete(db, session_model_id=session_model_id)
    db.commit()
    return None


# =========================================
# Practice Responses
# =========================================
@router.get(
    "/models/{session_model_id}/responses",
    response_model=List[PracticeResponseResponse],
    operation_id="list_practice_responses_by_model",
)
def list_practice_responses_by_model(
    session_model_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    _model, _session = ensure_my_session_model(db, session_model_id, me)
    responses = practice_response_crud.list_by_session_model(
        db,
        session_model_id=session_model_id,
    )
    return [PracticeResponseResponse.model_validate(r) for r in responses]


@router.post(
    "/models/{session_model_id}/responses",
    response_model=PracticeResponseResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="create_practice_response",
    summary="실습 응답 생성",
)
def create_practice_response(
    session_model_id: int = Path(..., ge=1),
    data: PracticeResponseCreate = ...,
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    _model, _session = ensure_my_session_model(db, session_model_id, me)

    data_in = data.model_copy(
        update={
            "session_model_id": session_model_id,
            "session_id": _session.session_id,
            "model_name": _model.model_name,
        }
    )
    resp = practice_response_crud.create(db, data_in)
    db.commit()
    return PracticeResponseResponse.model_validate(resp)


@router.get(
    "/responses/{response_id}",
    response_model=PracticeResponseResponse,
    operation_id="get_practice_response",
)
def get_practice_response(
    response_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    """
    특정 응답 1개 상세 열기(예: 히스토리에서 응답 카드 클릭 → 상세/공유/디버그 화면)
    """
    resp, _model, _session = ensure_my_response(db, response_id, me)
    return PracticeResponseResponse.model_validate(resp)


@router.patch(
    "/responses/{response_id}",
    response_model=PracticeResponseResponse,
    operation_id="update_practice_response",
)
def update_practice_response(
    response_id: int = Path(..., ge=1),
    data: PracticeResponseUpdate = ...,
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    """
    응답 레코드의 일부를 수정(예: 사용자가 별점/메모/태그 같은 필드를 응답에 붙이거나,
    관리자/파트너가 “검수 상태” 같은 메타를 업데이트할 때)
    ※ LLM 텍스트 자체를 수정하게 할지 여부는 정책 선택.
    """
    _resp, _model, _session = ensure_my_response(db, response_id, me)
    updated = practice_response_crud.update(db, response_id=response_id, data=data)
    db.commit()
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="response not found")
    return PracticeResponseResponse.model_validate(updated)


@router.delete(
    "/responses/{response_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="delete_practice_response",
)
def delete_practice_response(
    response_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    """
    특정 턴만 삭제(예: 실수로 민감정보를 넣어서 해당 턴만 지우고 싶을 때, 혹은 대화 전체는 남기고 일부 턴만 제거).
    """
    _resp, _model, _session = ensure_my_response(db, response_id, me)
    practice_response_crud.delete(db, response_id=response_id)
    db.commit()
    return None
