# app/endpoints/user/practice.py
from __future__ import annotations

from typing import Optional, List

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
)
from schemas.user.practice import PracticeTurnRequest, PracticeTurnResponse

from service.user.practice import (
    set_primary_model_for_session,
    run_practice_turn,  # 추후 LLM 연동 시 사용
    # create_model_comparison_from_metrics,  # 메트릭 기반 비교 생성 시 사용
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

    # 1) is_primary 변경 요청이 포함된 경우 → service에서 처리
    if data.is_primary is True:
        target = set_primary_model_for_session(
            db,
            me=me,
            session_id=model.session_id,
            target_session_model_id=session_model_id,
        )
        db.commit()
        return PracticeSessionModelResponse.model_validate(target)

    # 2) 일반 업데이트 (model_name 등)
    updated = practice_session_model_crud.update(
        db,
        session_model_id=session_model_id,
        data=data,
    )
    db.commit()

    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="model not found",
        )

    return PracticeSessionModelResponse.model_validate(updated)


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

    # NOTE:
    # - 실제 LLM 호출 + token_usage/latency 계산은
    #   service.user.practice.run_practice_turn 을 사용해 별도 /chat 엔드포인트로 빼는 방식 추천


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

    # NOTE:
    # - 메트릭 기반 비교 생성은 service.user.practice.create_model_comparison_from_metrics
    #   를 사용하는 별도 엔드포인트로 빼는 방식 추천


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

## LLM  창에 입력 들어올때 쓰는 엔드포인트
@router.post(
    "/sessions/{session_id}/chat",
    response_model=PracticeTurnResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="run_practice_turn_for_session",
)
def run_practice_turn_endpoint(
    session_id: int = Path(..., ge=1),
    body: PracticeTurnRequest = ...,
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    # 세션 소유권 체크
    session = _ensure_my_session(db, session_id, me)

    # 어떤 모델들에 보낼지 결정
    if body.session_model_ids:
        models: list[PracticeSessionModel] = []
        for sm_id in body.session_model_ids:
            model, model_session = _ensure_my_session_model(db, sm_id, me)
            if model_session.session_id != session_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="session_model does not belong to this session",
                )
            models.append(model)
    else:
        # 지정 없으면 세션에 등록된 모든 모델에 병렬 호출
        models = practice_session_model_crud.list_by_session(db, session_id=session_id)

    if not models:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="no models configured for this session",
        )

    turn_result = run_practice_turn(
        db=db,
        session=session,
        models=models,
        prompt_text=body.prompt_text,
        user=me,
    )
    db.commit()
    return PracticeTurnResponse.model_validate(turn_result)
