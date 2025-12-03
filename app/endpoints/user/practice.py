# app/endpoints/user/practice.py
from __future__ import annotations

from typing import Optional, List, Any

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Path,
    status,
)
from sqlalchemy.orm import Session

from core.deps import get_db, get_current_user
from core import config  # 기본 LLM/연습 모델 설정을 읽기 위함
from models.user.account import AppUser
from crud.partner import classes as classes_crud
from crud.user.practice import (
    practice_session_crud,
    practice_session_model_crud,
    practice_response_crud,
    practice_rating_crud,
    model_comparison_crud,
)
from models.user.practice import PracticeSessionModel
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
    PracticeRatingCreate,
    PracticeRatingUpdate,
    PracticeRatingResponse,
    ModelComparisonCreate,
    ModelComparisonUpdate,
    ModelComparisonResponse,
    PracticeTurnRequest,
    PracticeTurnResponse,
)
from service.user.practice import (
    set_primary_model_for_session,
    run_practice_turn,
    # create_model_comparison_from_metrics,
)
from models.partner.catalog import ModelCatalog
router = APIRouter()


# =========================================
# helpers (내 소유 세션/모델/응답/평가/비교 검증)
# =========================================
def _ensure_my_session(db: Session, session_id: int, me: AppUser):
    session = practice_session_crud.get(db, session_id)
    if not session or session.user_id != me.user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="session not found")
    return session


def _ensure_my_session_model(db: Session, session_model_id: int, me: AppUser):
    model = practice_session_model_crud.get(db, session_model_id)
    if not model:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="model not found")
    session = practice_session_crud.get(db, model.session_id)
    if not session or session.user_id != me.user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="model not found")
    return model, session


def _ensure_my_response(db: Session, response_id: int, me: AppUser):
    resp = practice_response_crud.get(db, response_id)
    if not resp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="response not found")
    model, session = _ensure_my_session_model(db, resp.session_model_id, me)
    return resp, model, session


def _ensure_my_rating(db: Session, rating_id: int, me: AppUser):
    rating = practice_rating_crud.get(db, rating_id)
    if not rating or rating.user_id != me.user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="rating not found")
    return rating


def _ensure_my_comparison(db: Session, comparison_id: int, me: AppUser):
    comp = model_comparison_crud.get(db, comparison_id)
    if not comp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="comparison not found")
    session = practice_session_crud.get(db, comp.session_id)
    if not session or session.user_id != me.user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="comparison not found")
    return comp, session


# =========================================
# Practice Sessions
# =========================================
@router.get(
    "/sessions",
    response_model=Page[PracticeSessionResponse],
    operation_id="list_my_practice_sessions",
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
    summary="새 대화(세션)",
)
def create_practice_session(
    data: PracticeSessionCreate,
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    data_in = data.model_copy(update={"user_id": me.user_id})
    session = practice_session_crud.create(db, data_in)
    db.commit()
    return PracticeSessionResponse.model_validate(session)

# =========================================
# LLM /chat 엔드포인트
# =========================================
@router.post(
    "/sessions/{session_id}/chat",
    response_model=PracticeTurnResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="run_practice_turn_for_session",
    summary="실제 LLM 실습 턴 실행(if==0, 새 세션 생성)",
)
def run_practice_turn_endpoint(
    session_id: int = Path(
        ...,
        ge=0,
        description="0이면 자동으로 새 세션을 생성 실행, 1 이상이면 해당 세션에서 이어서 대화",
    ),
    class_id: int = Query(
        ...,
        ge=1,
        description="이 연습 세션이 속한 Class ID (partner.classes.id)",
    ),
    body: PracticeTurnRequest = ...,
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    """
    [기능 개요]

    - 특정 강의실(class_id)에 연결된 LLM 설정을 기준으로, 멀티 모델 실습 턴을 실행하는 엔드포인트.
    - `session_id == 0` 이면: 새 practice_session 을 만들고, 해당 class 의 LLM 설정으로
      `practice_session_models` 를 자동 구성한 뒤 첫 턴을 실행한다.
    - `session_id > 0` 이면: 기존 세션에 대해 이어서 턴을 실행한다.

    [동작 상세]

    1. **새 대화 시작 (session_id = 0)**

       - 필수: `class_id` 와 `prompt_text`.
       - 현재 로그인 유저(`me.user_id`) 기준으로 새 `practice_session` 을 생성하고,
         `class_id` 로 해당 세션을 강의실에 묶는다.
       - `partner.classes.id = class_id` 인 row를 조회:
         - 없거나 `status != "active"` 이면 `400 (유효하지 않은 class_id 입니다.)`.
       - `class.primary_model_id` + `class.allowed_model_ids` 에서
         **model_catalog_id 리스트**를 만든 뒤,
         각각에 대해 `partner.model_catalog` 존재 여부를 검증한다.
           - `logical_name` 이 있으면 그 값을,
             없으면 `model_name` 을 사용해서 `PracticeSessionModel.model_name` 에 저장한다.
       - 만들어진 모델 목록에 대해:
         - 첫 번째만 `is_primary = True`, 나머지는 `False` 인
           `PracticeSessionModel` 레코드를 생성한다.
       - 이렇게 생성된 세션/모델들을 대상으로
         이번 턴의 `prompt_text` 를 바로 LLM 에 보내고, 응답을 저장한다.
       - 현재 구현에서는 `session_id=0` 인 경우 `body.session_model_ids` 값은 사용되지 않고 무시된다.

    2. **기존 대화 이어가기 (session_id > 0)**

       - `_ensure_my_session` 으로 세션이 현재 유저(me.user_id)의 것인지 검증한다.
       - 세션에 묶인 `class_id` 를 검증한다.
         - 세션의 `class_id` 가 `None` 이면:
           - 최초 1회에 한해, 이번에 들어온 `class_id` 로 바인딩하고 저장한다.
         - 세션의 `class_id` 가 이미 있는데, 쿼리로 들어온 `class_id` 와 다르면:
           - `400 (class_id does not match this session)` 을 반환한다.
       - 어떤 세션-모델을 호출할지 결정:
         - `body.session_model_ids` 가 비어 있으면:
           - 이 세션에 등록된 **모든** `PracticeSessionModel` 을 조회해서 호출한다.
         - `body.session_model_ids` 에 값이 있으면:
           - 각 ID에 대해 `_ensure_my_session_model` 로
             - 현재 유저 소유 여부,
             - 해당 세션에 속한 모델인지 여부를 검증한 뒤,
             - 이 세션에 속한 모델만 모아 호출한다.

    3. **지식베이스(RAG) 기반 질문 (선택)**

       - `body.document_ids` 에 값이 들어오면:
         - 각 `document_id` 가 현재 유저의 문서인지 검증한다.
         - 질문 텍스트를 임베딩한 뒤,
           pgvector 기반 유사도 검색으로 관련도가 높은 청크들을 top-k 로 조회한다.
         - 검색된 청크 텍스트들을 하나의 컨텍스트 문자열로 합쳐서,
           LLM 프롬프트 앞부분에 붙인 뒤 질문을 전달한다.
       - `document_ids` 를 비우면 일반 LLM 채팅처럼 동작한다.

    [요청 바디 (PracticeTurnRequest)]

    - `prompt_text` (필수): 이번 턴에서 보낼 사용자 질문 텍스트.
    - `session_model_ids` (선택):
        - 비우면: 해당 세션에 등록된 **모든** 모델에게 질문을 보낸다.
        - 채우면: 배열에 포함된 `session_model_id` 들에 해당하는 모델만 호출한다.
          (값은 `user.practice_session_models.session_model_id` 기준)
    - `document_ids` (선택): RAG 에 사용할 내 문서 ID 목록.

    [응답 구조 (PracticeTurnResponse)]

    - `session_id` : 현재 대화 세션 ID.
    - `session_title` : 세션 제목.
        - 첫 턴에서 아직 제목이 없으면, 대표 모델 응답을 기반으로 LLM이 자동 생성한다.
    - `prompt_text` : 이번 턴에서 보낸 질문 텍스트.
    - `results[]` : 모델별 응답 리스트 (`PracticeTurnModelResult`):
        - `session_model_id` : `user.practice_session_models.session_model_id`.
        - `model_name` : 논리 모델 이름
          (예: `gpt-4o-mini`, `claude-3-haiku-20240307` 등,
          `config.PRACTICE_MODELS` 의 key 와 대응).
        - `response_id` : `user.practice_responses.response_id`.
        - `response_text` : 해당 모델의 답변 텍스트.
        - `token_usage` : 토큰 사용량 정보(있을 때만 값 존재).
        - `latency_ms` : 해당 모델 응답까지 걸린 시간(ms).
        - `created_at` : 응답 생성 시각.
        - `is_primary` : 이 세션에서 대표 모델인지 여부.

    [주의사항]

    - 항상 `class_id` 쿼리 파라미터가 필수이다.
    - 세션과 세션-모델은 항상 현재 로그인한 유저의 소유인지 검증된다.
    - 실제 LLM provider / 물리 모델명은
      `config.PRACTICE_MODELS[model_name]` 설정을 통해 매핑된다.
    """

    # 1) session_id == 0 → 새 세션 + class 설정 기반 기본 모델 자동 생성
    if session_id == 0:
        # 새 practice_session 생성
        session = practice_session_crud.create(
            db,
            PracticeSessionCreate(
                user_id=me.user_id,
                class_id=class_id,
                title=None,
                notes=None,
            ),
        )

        # class 설정에서 사용할 모델 목록 가져오기
        class_obj = classes_crud.get_class(db, class_id=class_id)
        if not class_obj or class_obj.status != "active":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="유효하지 않은 class_id 입니다.",
            )

        # 1) class 에 설정된 model_catalog id 목록 수집
        model_catalog_ids: list[int] = []

        if class_obj.primary_model_id:
            model_catalog_ids.append(class_obj.primary_model_id)

        if class_obj.allowed_model_ids:
            for mid in class_obj.allowed_model_ids:
                if mid not in model_catalog_ids:
                    model_catalog_ids.append(mid)

        if not model_catalog_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="이 class 에 설정된 모델이 없습니다. 강의 설정에서 모델을 추가하세요.",
            )

        # 2) 각 catalog id → 실제 LLM logical name 으로 매핑
        model_names: list[str] = []
        for mc_id in model_catalog_ids:
            catalog = db.get(ModelCatalog, mc_id)
            if not catalog:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"유효하지 않은 model_catalog id: {mc_id}",
                )

            # logical_name 이 있으면 그걸 우선 사용, 없으면 model_name 사용
            logical_name = getattr(catalog, "logical_name", None)
            name = logical_name or catalog.model_name
            model_names.append(name)

        # 3) 세션-모델 레코드 생성 (첫 번째만 is_primary=True)
        models: list[PracticeSessionModel] = []
        for idx, name in enumerate(model_names):
            m = practice_session_model_crud.create(
                db,
                PracticeSessionModelCreate(
                    session_id=session.session_id,
                    model_name=name,         # 더 이상 model_catalog_id 없음
                    is_primary=(idx == 0),
                ),
            )
            models.append(m)

    # 2) session_id > 0 → 기존 세션에 대해 턴 실행
    else:
        session = _ensure_my_session(db, session_id, me)

        # 세션이 특정 class 에 묶여 있어야 하고, 요청한 class_id 와 일치해야 함
        if session.class_id is None:
            # 기존 데이터 호환용: 아직 class 에 안 묶인 세션이면
            # 이번에 들어온 class_id 로 한 번만 바인딩해 준다.
            session.class_id = class_id
            db.add(session)
            db.commit()
        elif session.class_id != class_id:
            # 이미 다른 class 에 묶여 있는데, 다른 class_id 로 호출한 경우는 에러
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="class_id does not match this session",
            )

        # 어떤 모델들에 보낼지 결정
        if body.session_model_ids:
            models: list[PracticeSessionModel] = []
            for sm_id in body.session_model_ids:
                model, model_session = _ensure_my_session_model(db, sm_id, me)
                if model_session.session_id != session.session_id:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="session_model does not belong to this session",
                    )
                models.append(model)
        else:
            # 지정 없을시 세션에 등록된 모든 모델에 순차 호출
            models = practice_session_model_crud.list_by_session(
                db,
                session_id=session.session_id,
            )

    if not models:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="no models configured for this session",
        )

    turn_result = run_practice_turn(
        db=db,
        session=session,
        models=models,   # 다중 LLM 모델일 때 여기서 모델 여러 개 받음
        prompt_text=body.prompt_text,
        user=me,
        document_ids=body.document_ids,
    )
    db.commit()
    return turn_result


@router.get(
    "/sessions/{session_id}",
    response_model=PracticeSessionResponse,
    operation_id="get_practice_session",
)
def get_practice_session(
    session_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    session = _ensure_my_session(db, session_id, me)
    return PracticeSessionResponse.model_validate(session)


@router.patch(
    "/sessions/{session_id}",
    response_model=PracticeSessionResponse,
    operation_id="update_practice_session",
)
def update_practice_session(
    session_id: int = Path(..., ge=1),
    data: PracticeSessionUpdate = ...,
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    _ = _ensure_my_session(db, session_id, me)
    updated = practice_session_crud.update(db, session_id=session_id, data=data)
    db.commit()
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="session not found")
    return PracticeSessionResponse.model_validate(updated)


@router.delete(
    "/sessions/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="delete_practice_session",
)
def delete_practice_session(
    session_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    _ = _ensure_my_session(db, session_id, me)
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
    _ = _ensure_my_session(db, session_id, me)
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
    """
    유저의 practice_session_models 테이블에 저장됨
    """
    _ = _ensure_my_session(db, session_id, me)
    data_in = data.model_copy(update={"session_id": session_id})
    model = practice_session_model_crud.create(db, data_in)
    db.commit()
    return PracticeSessionModelResponse.model_validate(model)


@router.patch(
    "/models/{session_model_id}",
    response_model=PracticeSessionModelResponse,
    operation_id="update_practice_session_model",
)
def update_practice_session_model(
    session_model_id: int = Path(..., ge=1),
    data: PracticeSessionModelUpdate = ...,
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    model, _session = _ensure_my_session_model(db, session_model_id, me)

    # 1) is_primary=True 인 경우: primary 토글 흐름
    if data.is_primary is True:
        update_data: dict[str, Any] = {}
        if data.model_name is not None:
            update_data["model_name"] = data.model_name

        if update_data:
            model = practice_session_model_crud.update(
                db,
                session_model_id=session_model_id,
                data=update_data,
            )

        target = set_primary_model_for_session(
            db,
            me=me,
            session_id=model.session_id,
            target_session_model_id=session_model_id,
        )
        # set_primary_model_for_session 안에서 commit을 안 한다면 여기서 commit
        # db.commit()
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
        # CRUD에서 commit 한다면 여기서는 안 해도 됨
        # db.commit()

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
    _model, _session = _ensure_my_session_model(db, session_model_id, me)
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
    _model, _session = _ensure_my_session_model(db, session_model_id, me)
    responses = practice_response_crud.list_by_session_model(
        db, session_model_id=session_model_id
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
    _model, _session = _ensure_my_session_model(db, session_model_id, me)

    # path param 기준으로 session_model_id 강제
    data_in = data.model_copy(update={"session_model_id": session_model_id})
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
    resp, _model, _session = _ensure_my_response(db, response_id, me)
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
    _resp, _model, _session = _ensure_my_response(db, response_id, me)
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
    _resp, _model, _session = _ensure_my_response(db, response_id, me)
    practice_response_crud.delete(db, response_id=response_id)
    db.commit()
    return None


# =========================================
# Model Comparisons
# =========================================
@router.get(
    "/sessions/{session_id}/comparisons",
    response_model=List[ModelComparisonResponse],
    operation_id="list_model_comparisons_for_session",
)
def list_model_comparisons_for_session(
    session_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    _ = _ensure_my_session(db, session_id, me)
    comps = model_comparison_crud.list_by_session(db, session_id=session_id)
    return [ModelComparisonResponse.model_validate(c) for c in comps]


@router.post(
    "/sessions/{session_id}/comparisons",
    response_model=ModelComparisonResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="create_model_comparison",
    summary="모델 비교 생성",
)
def create_model_comparison(
    session_id: int = Path(..., ge=1),
    body: ModelComparisonCreate = ...,
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    _ = _ensure_my_session(db, session_id, me)

    data_in = body.model_copy(update={"session_id": session_id})
    comp = model_comparison_crud.create(db, data_in)
    db.commit()
    return ModelComparisonResponse.model_validate(comp)


@router.patch(
    "/comparisons/{comparison_id}",
    response_model=ModelComparisonResponse,
    operation_id="update_model_comparison",
)
def update_model_comparison(
    comparison_id: int = Path(..., ge=1),
    body: ModelComparisonUpdate = ...,
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    _comp, _session = _ensure_my_comparison(db, comparison_id, me)
    updated = model_comparison_crud.update(
        db, comparison_id=comparison_id, data=body
    )
    db.commit()
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="comparison not found")
    return ModelComparisonResponse.model_validate(updated)


@router.delete(
    "/comparisons/{comparison_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="delete_model_comparison",
)
def delete_model_comparison(
    comparison_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    _comp, _session = _ensure_my_comparison(db, comparison_id, me)
    model_comparison_crud.delete(db, comparison_id=comparison_id)
    db.commit()
    return None


# =========================================
# Practice Ratings
# =========================================
@router.get(
    "/responses/{response_id}/ratings",
    response_model=List[PracticeRatingResponse],
    operation_id="list_practice_ratings_for_response",
)
def list_practice_ratings_for_response(
    response_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    _resp, _model, _session = _ensure_my_response(db, response_id, me)
    ratings = practice_rating_crud.list_by_response(db, response_id=response_id)
    return [PracticeRatingResponse.model_validate(r) for r in ratings]


@router.put(
    "/responses/{response_id}/rating",
    response_model=PracticeRatingResponse,
    operation_id="upsert_my_practice_rating",
)
def upsert_my_practice_rating(
    response_id: int = Path(..., ge=1),
    body: PracticeRatingCreate = ...,
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    _resp, _model, _session = _ensure_my_response(db, response_id, me)

    data_in = PracticeRatingCreate(
        response_id=response_id,
        user_id=me.user_id,
        score=body.score,
        feedback=body.feedback,
    )
    rating = practice_rating_crud.upsert(db, data_in)
    db.commit()
    return PracticeRatingResponse.model_validate(rating)


@router.patch(
    "/ratings/{rating_id}",
    response_model=PracticeRatingResponse,
    operation_id="update_my_practice_rating",
)
def update_my_practice_rating(
    rating_id: int = Path(..., ge=1),
    body: PracticeRatingUpdate = ...,
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    rating = _ensure_my_rating(db, rating_id, me)
    updated = practice_rating_crud.update(db, rating_id=rating_id, data=body)
    db.commit()
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="rating not found")
    return PracticeRatingResponse.model_validate(updated)


@router.delete(
    "/ratings/{rating_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="delete_my_practice_rating",
)
def delete_my_practice_rating(
    rating_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    _ = _ensure_my_rating(db, rating_id, me)
    practice_rating_crud.delete(db, rating_id=rating_id)
    db.commit()
    return None