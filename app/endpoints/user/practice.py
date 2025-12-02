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
   [요청 시나리오]

    1. **새 대화 시작**
       - `session_id = 0` 으로 호출
       - 서버가 새로운 practice_session 을 만들고,
         설정된 기본 모델들(`PRACTICE_MODELS` 중 enabled/default)로 세션을 초기화한 뒤
         각 모델에 한 번씩 질문을 보내서 첫 응답을 생성
       - 응답에 포함된 `session_id` 를 이후 턴에서 그대로 재사용

    2. **기존 대화 이어서 하기**
       - 이전에 받은 `session_id` 로 호출 (`/sessions/{session_id}/chat`)
       - `session_model_ids` 를 비워 두면: 해당 세션에 등록된 **모든 모델**에게 질문을 보냄
       - `session_model_ids` 에 ID 배열을 넣으면: 그 ID에 해당하는 모델들만 호출합니다.

    3. **지식베이스(RAG) 기반으로 질문하기**
       - `document_ids` 에 사용자가 업로드한 문서 ID 배열을 넘기면,
         서버가 해당 문서들의 벡터 임베딩을 이용해
         질문과 가장 관련도 높은 청크들(top-k)을 찾아 **프롬프트 앞에 컨텍스트로 붙인 뒤**
         각 LLM에 전달
       - 아무 값도 안 넘기면 일반 LLM 채팅처럼 동작

    [요청 바디]

    - `prompt_text` (필수): 이번 턴에서 보낼 사용자 질문 텍스트
    - `session_model_ids` : 이번 턴에 호출할 세션-모델 ID 목록 널값 하면 자동 디폴트 실행됨
    - `document_ids` : 참고할 지식베이스 문서 ID 목록
    - 한 session 안에 practice_session_models가 여러 개 붙을 수 있음
    - /sessions/{session_id}/chat 호출할 때:
        session_model_ids 비워두면 → 그 세션에 등록된 모든 모델한테 동시에 질문 보냄
        session_model_ids 배열 채우면 → 거기에 있는 모델들만 호출
        results[] 배열에 모델별 응답이 각각 한 칸씩 들어옴

    [응답 구조]

    - `session_id` : 현재 대화 세션 ID
    - `session_title` : 세션 제목 (첫 턴에서 자동 생성, 이후 유지)
    - `prompt_text` : 이번 턴에서 보낸 질문 텍스트
    - `results[]` : **모델별 응답 리스트** (밑에건 아직 구현중)
        - `session_model_id` : 세션 내 모델 식별자
        - `model_name` : 논리 모델 이름 (예: `gpt-4o-mini`, `claude-3.7-haiku`)
        - `response_id` : 저장된 응답 ID
        - `response_text` : 해당 모델의 답변 텍스트
        - `token_usage` : 토큰 사용량 정보(있을 때만 값 존재)
        - `latency_ms` : 해당 모델 응답까지 걸린 시간(ms)
        - `created_at` : 응답 생성 시각
        - `is_primary` : 대표 모델 여부 (자동 제목 생성 등에 사용)config에서 함

    [프로세스]
    - 새 대화 시작:
      - `POST /user/practice/sessions/0/chat` 한 번 호출 → `session_id` 저장
    - 이후 턴:
      - 같은 `session_id` 로 계속 `/chat` 호출
    - 화면 구성:
      - `results` 배열을 기반으로 **모델별 컬럼**을 만들어
        각 모델의 답변/레이턴시/토큰 사용량을 나란히 비교해서 보여줌(구현중)
    - 항상 class_id 를 필수로 받는다.
      - session_id == 0 인 경우: 이 class 에 속한 새 practice_session 생성
      - session_id > 0 인 경우: 해당 세션의 class_id 와 요청 class_id 가 일치하는지 검증
    """

    # 1) session_id == 0 → 새 세션 + 기본 모델 자동 생성
    if session_id == 0:
        # 새 세션 생성일 때는 session_model_ids 지정을 막아둠 (아직 존재하지 않는 id이므로)
        if body.session_model_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="session_id=0 일 때는 session_model_ids 를 지정할 수 없습니다.",
            )

        # 새 practice_session 생성 (class_id 필수)
        session = practice_session_crud.create(
            db,
            PracticeSessionCreate(
                user_id=me.user_id,
                class_id=class_id,
                title=None,
                notes=None,
            ),
        )

        # 기본 연습 모델 목록 결정 (config.PRACTICE_MODELS 기준)
        practice_models = getattr(config, "PRACTICE_MODELS", {}) or {}
        default_model_names: list[str] = []

        # 1순위: enabled=True 이면서 default=True 인 모델들
        for name, conf in practice_models.items():
            if not isinstance(conf, dict):
                continue
            if conf.get("enabled", True) and conf.get("default", False):
                default_model_names.append(name)

        # 2순위: enabled=True 인 첫 번째 모델
        if not default_model_names:
            for name, conf in practice_models.items():
                if isinstance(conf, dict) and conf.get("enabled", True):
                    default_model_names.append(name)
                    break

        if not default_model_names:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="사용 가능한 연습 모델이 설정되어 있지 않습니다. PRACTICE_MODELS를 확인하세요.",
            )

        # 세션에 기본 모델들 생성 (첫 번째만 is_primary=True)
        models: list[PracticeSessionModel] = []
        is_first = True
        for name in default_model_names:
            m = practice_session_model_crud.create(
                db,
                PracticeSessionModelCreate(
                    session_id=session.session_id,
                    model_name=name,
                    is_primary=is_first,
                ),
            )
            models.append(m)
            is_first = False

    # 2) session_id > 0 → 기존 세션에 대해 턴 실행
    else:
        session = _ensure_my_session(db, session_id, me)

        # 세션이 특정 class 에 묶여 있어야 하고, 요청한 class_id 와 일치해야 함
        if session.class_id is None:
            # 기존 데이터라 class_id 가 비어 있는 세션이면 바로 바인딩해도 되고,
            # 아니면 400 을 던질 수도 있는데, 여기서는 엄격하게 막는다.
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="this session is not bound to any class (class_id is NULL)",
            )

        if session.class_id != class_id:
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
            models = practice_session_model_crud.list_by_session(db, session_id=session.session_id)

    if not models:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="no models configured for this session",
        )

    turn_result = run_practice_turn(
        db=db,
        session=session,
        models=models,    # 다중 LLM 모델 할때 여기서 모델 여러개 받음
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