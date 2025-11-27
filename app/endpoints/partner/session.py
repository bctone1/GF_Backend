# app/endpoints/partner/session.py
from __future__ import annotations
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.orm import Session
from core.deps import get_db, get_current_partner_user
from crud.partner import session as session_crud
from schemas.partner.session import (
    AiSessionCreate,
    AiSessionUpdate,
    AiSessionResponse,
    AiSessionPage,
    SessionMessageCreate,
    SessionMessageUpdate,
    SessionMessageResponse,
    SessionMessagePage,
)
from schemas.enums import SessionMode, SessionStatus

router = APIRouter()

# ==============================
# AiSession 엔드포인트
# ==============================
@router.get("", response_model=AiSessionPage)
def list_ai_sessions(
    partner_id: int = Path(..., ge=1),
    student_id: Optional[int] = Query(None),
    class_id: Optional[int] = Query(None),
    status: Optional[SessionStatus] = Query(
        None, description="active | completed | canceled | error"
    ),
    mode: Optional[SessionMode] = Query(
        None, description="single | parallel"
    ),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_user),
):
    """
    세션 목록 조회 (파트너 관점).
    """
    rows, total = session_crud.list_sessions(
        db,
        student_id=student_id,
        class_id=class_id,
        status=status,
        mode=mode,
        page=page,
        size=size,
    )
    items = [AiSessionResponse.model_validate(r) for r in rows]
    return {"items": items, "total": total, "page": page, "size": size}


@router.get("/{session_id}", response_model=AiSessionResponse,
            summary="세션타이틀 불러오기")
def get_ai_session(
    partner_id: int = Path(..., ge=1),
    session_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_user),
):
    """
    단일 세션 상세 조회.
    """
    obj = session_crud.get_session(db, session_id=session_id)
    if not obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="session not found"
        )
    return AiSessionResponse.model_validate(obj)


@router.post(
    "",
    response_model=AiSessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="새 대화",
)
def create_ai_session(
    partner_id: int = Path(..., ge=1),
    payload: AiSessionCreate = ...,
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_user),
):
    """
    세션 생성.
    추후에 AI가 자동 요약해서 title 작성하는걸로 변경 예정
    - 프로젝트 코스 클래스와 연관되어 있음. 모델명 표기도 고려해야함(추후)
    """
    data = payload.model_dump(exclude_unset=True)
    # 추후수정: class_id / student_id 가 partner_id 소속인지 검증하는 로직 추가 가능
    obj = session_crud.create_session(db, data=data)
    return AiSessionResponse.model_validate(obj)


@router.patch("/{session_id}", response_model=AiSessionResponse)
def update_ai_session(
    partner_id: int = Path(..., ge=1),
    session_id: int = Path(..., ge=1),
    payload: AiSessionUpdate = ...,
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_user),
):
    """
    세션 메타 정보 업데이트.
    - 상태(status) 변경, 종료시간(ended_at) 갱신, 통계값 보정 등.
    """
    obj = session_crud.get_session(db, session_id=session_id)
    if not obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="session not found"
        )

    data = payload.model_dump(exclude_unset=True)
    obj = session_crud.update_session(db, session=obj, data=data)
    return AiSessionResponse.model_validate(obj)


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_ai_session(
    partner_id: int = Path(..., ge=1),
    session_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_user),
):
    """
    세션 삭제 (메시지는 CASCADE 로 함께 삭제).
    """
    obj = session_crud.get_session(db, session_id=session_id)
    if not obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="session not found"
        )

    session_crud.delete_session(db, session=obj)
    return None


# ==============================
# SessionMessage 엔드포인트
# ==============================
@router.get(
    "/{session_id}/messages",
    response_model=SessionMessagePage,
)
def list_session_messages(
    partner_id: int = Path(..., ge=1),
    session_id: int = Path(..., ge=1),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_user),
):
    """
    특정 세션의 메시지 목록 조회.
    """
    session_obj = session_crud.get_session(db, session_id=session_id)
    if not session_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="session not found"
        )

    rows, total = session_crud.list_messages(
        db, session_id=session_id, page=page, size=size
    )
    items = [SessionMessageResponse.model_validate(r) for r in rows]
    return {"items": items, "total": total, "page": page, "size": size}


@router.post(
    "/{session_id}/messages",
    response_model=SessionMessageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="질문 답변",
)
def create_session_message(
    partner_id: int = Path(..., ge=1),
    session_id: int = Path(..., ge=1),
    payload: SessionMessageCreate = ...,
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_user),
):
    """
    세션에 메시지 추가.
    - 학생 질문/조교 답변/시스템 메시지 등 모두 이 엔드포인트로 기록.
    """
    session_obj = session_crud.get_session(db, session_id=session_id)
    if not session_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="session not found"
        )

    data = payload.model_dump(exclude_unset=True)
    # path 의 session_id 를 우선으로 사용
    data["session_id"] = session_id

    obj = session_crud.create_message(db, data=data)
    return SessionMessageResponse.model_validate(obj)


@router.get(
    "/{session_id}/messages/{message_id}",
    response_model=SessionMessageResponse,
)
def get_session_message(
    partner_id: int = Path(..., ge=1),
    session_id: int = Path(..., ge=1),
    message_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_user),
):
    """
    단일 메시지 조회.
    """
    msg = session_crud.get_message(db, message_id=message_id)
    if not msg or msg.session_id != session_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="message not found"
        )
    return SessionMessageResponse.model_validate(msg)


@router.patch(
    "/{session_id}/messages/{message_id}",
    response_model=SessionMessageResponse,
)
def update_session_message(
    partner_id: int = Path(..., ge=1),
    session_id: int = Path(..., ge=1),
    message_id: int = Path(..., ge=1),
    payload: SessionMessageUpdate = ...,
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_user),
):
    """
    메시지 수정.
    - meta / tokens / latency_ms 보정 등에 사용.
    """
    msg = session_crud.get_message(db, message_id=message_id)
    if not msg or msg.session_id != session_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="message not found"
        )

    data = payload.model_dump(exclude_unset=True)
    msg = session_crud.update_message(db, message=msg, data=data)
    return SessionMessageResponse.model_validate(msg)


@router.delete(
    "/{session_id}/messages/{message_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_session_message(
    partner_id: int = Path(..., ge=1),
    session_id: int = Path(..., ge=1),
    message_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_user),
):
    """
    메시지 삭제.
    """
    msg = session_crud.get_message(db, message_id=message_id)
    if not msg or msg.session_id != session_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="message not found"
        )

    session_crud.delete_message(db, message=msg)
    return None
