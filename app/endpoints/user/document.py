# app/endpoints/user/document.py
from __future__ import annotations

from typing import Optional, List
from database.session import SessionLocal
from fastapi import (
    APIRouter,
    File,
    Depends,
    HTTPException,
    Query,
    Path,
    status,
    UploadFile,
    BackgroundTasks,
)
from sqlalchemy import select
from sqlalchemy.orm import Session
from core import config
from core.deps import get_db, get_current_user
from models.user.account import AppUser

from crud.user.document import (
    document_crud,
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

def run_document_pipeline_background(user_id: int, knowledge_id: int) -> None:
    """
    BackgroundTasks에서 호출할 실제 작업 함수.
    - 새로운 DB 세션을 열어서 사용 후 닫는다.
    """
    db = SessionLocal()
    try:
        pipeline = UploadPipeline(db, user_id=user_id)
        pipeline.process_document(knowledge_id=knowledge_id)
    finally:
        db.close()


# =========================================================
# Document (내 문서)
# =========================================================
@router.get(
    "/document",
    response_model=Page[DocumentResponse],
    operation_id="list_my_document",
    summary="내 문서 리스트 조회",
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
    문서 메타데이터만 직접 생성하는 예약 엔드포인트.
    실제 파일 업로드/파싱/임베딩은 /user/upload 사용.
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
    summary="지식베이스 파일 업로드 (비동기 처리)",
    description=(
        "파일을 업로드하면 즉시 Document row를 생성하고 반환한다.\n"
        "- 최초 상태는 status='uploading', progress=0.\n"
        "- 실제 텍스트 추출/청크/임베딩 등 무거운 작업은 BackgroundTasks에서 비동기로 수행.\n"
        "- 프론트는 응답에서 받은 knowledge_id로 "
        "`GET /user/document/{knowledge_id}`를 폴링하여\n"
        "status/progress/error_message를 확인하면서 프로그레스 바를 갱신하면 된다."
    ),
)
def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="file required",
        )

    # === 1) 파일 사이즈 체크 (10MB 제한) ===
    max_bytes = config.DOCUMENT_MAX_SIZE_BYTES

    # SpooledTemporaryFile 기준: 끝으로 이동해서 크기 재고, 다시 처음으로 돌려놓기
    file.file.seek(0, 2)     # 파일 끝으로
    size = file.file.tell()  # 현재 위치 = 파일 크기
    file.file.seek(0)        # 다시 처음으로

    if size > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"파일 최대용량 도달. 최대 {config.DOCUMENT_MAX_SIZE_MB}MB 까지만 업로드할 수 있음",
        )

    # 2) 파일 저장 + Document row 생성 (status='uploading', progress=0)
    pipeline = UploadPipeline(db, user_id=me.user_id)
    # 여기서 size를 같이 넘겨서 file_size_bytes로 쓰게 하면 좋음
    doc = pipeline.init_document(file)

    # 3) 일단 여기까지 커밋해서 Document가 확정되도록 함
    db.commit()
    db.refresh(doc)

    # 4) 백그라운드에서 무거운 처리 실행
    background_tasks.add_task(
        run_document_pipeline_background,
        me.user_id,
        doc.knowledge_id,
    )

    # 5) 지금 시점의 Document 상태 반환 (uploading / 0%)
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
    """
    문서 상세 + 현재 상태/진행률 조회용.
    - status, progress, error_message 등을 함께 내려줌 (스키마에 포함되어 있다면).
    """
    doc = document_crud.get(db, knowledge_id=knowledge_id)
    if not doc or doc.owner_id != me.user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="document not found",
        )
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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="document not found",
        )

    updated = document_crud.update(db, knowledge_id=knowledge_id, data=data)
    db.commit()
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="document not found",
        )
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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="document not found",
        )

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
    # 타입 힌트용 더미 (사용 안 함)
    _ = select(DocumentTagCreate.__config__.orm_model) if False else None

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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="document not found",
        )

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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="document not found",
        )

    tag = document_tag_crud.ensure(db, name=body.name)
    assignment_in = DocumentTagAssignmentCreate(
        knowledge_id=knowledge_id,
        tag_id=tag.tag_id,
    )
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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="document not found",
        )

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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="document not found",
        )

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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="document not found",
        )

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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="document not found",
        )

    chunks = document_chunk_crud.list_by_document_page(
        db,
        knowledge_id=knowledge_id,
        page_id=page_id,
    )
    return [DocumentChunkResponse.model_validate(c) for c in chunks]
