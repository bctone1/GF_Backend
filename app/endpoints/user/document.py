# app/endpoints/user/document.py
from __future__ import annotations

from typing import Optional, List, Tuple

from fastapi import APIRouter,File, Depends, HTTPException, Query, Path, status,UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from core.deps import get_db, get_current_user
from models.user.account import AppUser

from crud.user.document import (
    document_crud,
    document_job_crud,
    document_tag_crud,
    document_tag_assignment_crud,
    document_usage_crud,
    document_page_crud,
    document_chunk_crud,
)

from schemas.base import Page
from schemas.user.document import (
    DocumentCreate,
    DocumentUpdate,
    DocumentResponse,
    DocumentTagCreate,
    DocumentTagUpdate,
    DocumentTagResponse,
    DocumentTagAssignmentCreate,
    DocumentTagAssignmentResponse,
    DocumentUsageResponse,
    DocumentPageResponse,
    DocumentChunkResponse,
)

from service.user.upload_pipeline import UploadPipeline
router = APIRouter()


# =========================================================
# Document (내 문서)
# =========================================================
@router.get(
    "/document",
    response_model=Page[DocumentResponse],
    operation_id="list_my_document",
    summary="내문서 리스트"
)
def list_my_document(
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    status_filter: Optional[str] = Query(None, alias="status"),
    q: Optional[str] = Query(None, description="문서명 검색어"),
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    rows, total = document_crud.get_by_owner(
        db,
        owner_id=me.user_id,
        status=status_filter,
        q=q,
        page=page,
        size=size,
    )
    items = [DocumentResponse.model_validate(r) for r in rows]
    return {"items": items, "total": total, "page": page, "size": size}


@router.post(
    "/document",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="create_document",
)
def create_document(
    data: DocumentCreate,
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    """
    문서 레코딩용(메타데이터 기록) 추후에 API등 연결시 구글 드라이브라던가..
    혹은 다른 팀원(프로젝트 할때나)
    지금은 굳이 안씀(예약엔드포인트)
    """
    # owner_id는 토큰 기준으로 강제
    data_for_create = data.model_copy(update={"owner_id": me.user_id})
    doc = document_crud.create(db, data_for_create)
    db.commit()
    return DocumentResponse.model_validate(doc)


@router.post(
    "/upload",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="upload_document",
    summary="업로드",
)
def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="file required",
        )

    # 로그인한 유저 기준으로 업로드 파이프라인 실행
    pipeline = UploadPipeline(db, user_id=me.user_id)
    doc = pipeline.run(file)

    # SQLAlchemy 객체 → Pydantic 응답 스키마
    return DocumentResponse.model_validate(doc)




@router.get(
    "/document/{knowledge_id}",
    response_model=DocumentResponse,
    operation_id="get_document_detail",
)
def get_document_detail(
    knowledge_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    doc = document_crud.get(db, knowledge_id=knowledge_id)
    if not doc or doc.owner_id != me.user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="document not found")
    return DocumentResponse.model_validate(doc)


@router.patch(
    "/document/{knowledge_id}",
    response_model=DocumentResponse,
    operation_id="update_document",
)
def update_document(
    knowledge_id: int = Path(..., ge=1),
    data: DocumentUpdate = ...,
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    doc = document_crud.get(db, knowledge_id=knowledge_id)
    if not doc or doc.owner_id != me.user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="document not found")

    updated = document_crud.update(db, knowledge_id=knowledge_id, data=data)
    db.commit()
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="document not found")
    return DocumentResponse.model_validate(updated)


@router.delete(
    "/document/{knowledge_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="delete_document",
)
def delete_document(
    knowledge_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    doc = document_crud.get(db, knowledge_id=knowledge_id)
    if not doc or doc.owner_id != me.user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="document not found")

    document_crud.delete(db, knowledge_id=knowledge_id)
    db.commit()
    return None


# =========================================================
# Document Tags (태그)
# =========================================================
@router.get(
    "/document/tags",
    response_model=List[DocumentTagResponse],
    operation_id="list_all_document_tags",
)
def list_all_document_tags(
    q: Optional[str] = Query(None, description="태그명 검색어"),
    db: Session = Depends(get_db),
    _: AppUser = Depends(get_current_user),
):
    stmt = select(DocumentTagCreate.__config__.orm_model) if False else None  # 타입 힌트용 더미
    # 위 한 줄은 그냥 타입힌트용, 실제로 사용되진 않음

    from models.user.document import DocumentTag  # 로컬 import (순환 방지용)

    stmt = select(DocumentTag)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(DocumentTag.name.ilike(like))
    stmt = stmt.order_by(DocumentTag.name.asc())

    tags = list(db.scalars(stmt).all())
    return [DocumentTagResponse.model_validate(t) for t in tags]


@router.get(
    "/document/{knowledge_id}/tags",
    response_model=List[DocumentTagResponse],
    operation_id="list_document_tags",
)
def list_document_tags(
    knowledge_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    doc = document_crud.get(db, knowledge_id=knowledge_id)
    if not doc or doc.owner_id != me.user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="document not found")

    from models.user.document import DocumentTag, DocumentTagAssignment

    stmt = (
        select(DocumentTag)
        .join(
            DocumentTagAssignment,
            DocumentTagAssignment.tag_id == DocumentTag.tag_id,
        )
        .where(DocumentTagAssignment.knowledge_id == knowledge_id)
        .order_by(DocumentTag.name.asc())
    )
    tags = list(db.scalars(stmt).all())
    return [DocumentTagResponse.model_validate(t) for t in tags]


@router.post(
    "/document/{knowledge_id}/tags",
    response_model=DocumentTagResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="add_document_tag",
)
def add_document_tag(
    knowledge_id: int = Path(..., ge=1),
    body: DocumentTagCreate = ...,
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    doc = document_crud.get(db, knowledge_id=knowledge_id)
    if not doc or doc.owner_id != me.user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="document not found")

    tag = document_tag_crud.ensure(db, name=body.name)
    assignment_in = DocumentTagAssignmentCreate(knowledge_id=knowledge_id, tag_id=tag.tag_id)
    document_tag_assignment_crud.assign(db, assignment_in)
    db.commit()
    return DocumentTagResponse.model_validate(tag)


@router.delete(
    "/document/{knowledge_id}/tags/{tag_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="remove_document_tag",
)
def remove_document_tag(
    knowledge_id: int = Path(..., ge=1),
    tag_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    doc = document_crud.get(db, knowledge_id=knowledge_id)
    if not doc or doc.owner_id != me.user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="document not found")

    from models.user.document import DocumentTagAssignment

    # assignment_id를 직접 넘기지 않으므로 (doc, tag)로 조회 후 삭제
    stmt = select(DocumentTagAssignment).where(
        DocumentTagAssignment.knowledge_id == knowledge_id,
        DocumentTagAssignment.tag_id == tag_id,
    )
    assignment = db.scalars(stmt).first()
    if assignment:
        db.delete(assignment)
        db.flush()
        db.commit()
    else:
        # 멱등하게 204
        db.rollback()
    return None


# =========================================================
# Document Usage (사용량 조회 - READ ONLY)
# =========================================================
@router.get(
    "/document/{knowledge_id}/usage",
    response_model=List[DocumentUsageResponse],
    operation_id="list_document_usage",
)
def list_document_usage(
    knowledge_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    doc = document_crud.get(db, knowledge_id=knowledge_id)
    if not doc or doc.owner_id != me.user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="document not found")

    usages = document_usage_crud.list_by_document(db, knowledge_id=knowledge_id)
    return [DocumentUsageResponse.model_validate(u) for u in usages]


# =========================================================
# Document Pages / Chunks (조회 전용)
# =========================================================
@router.get(
    "/document/{knowledge_id}/pages",
    response_model=List[DocumentPageResponse],
    operation_id="list_document_pages",
)
def list_document_pages(
    knowledge_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    doc = document_crud.get(db, knowledge_id=knowledge_id)
    if not doc or doc.owner_id != me.user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="document not found")

    pages = document_page_crud.list_by_document(db, knowledge_id=knowledge_id)
    return [DocumentPageResponse.model_validate(p) for p in pages]


@router.get(
    "/document/{knowledge_id}/chunks",
    response_model=List[DocumentChunkResponse],
    operation_id="list_document_chunks",
)
def list_document_chunks(
    knowledge_id: int = Path(..., ge=1),
    page_id: Optional[int] = Query(None, ge=1),
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    doc = document_crud.get(db, knowledge_id=knowledge_id)
    if not doc or doc.owner_id != me.user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="document not found")

    chunks = document_chunk_crud.list_by_document_page(
        db,
        knowledge_id=knowledge_id,
        page_id=page_id,
    )
    return [DocumentChunkResponse.model_validate(c) for c in chunks]


