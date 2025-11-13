# crud/user/document.py
from __future__ import annotations

from typing import Optional, Sequence, Tuple
from datetime import datetime

from sqlalchemy.orm import Session
from sqlalchemy import select, update, delete, func

from models.user.document import (
    Document,
    DocumentProcessingJob,
    DocumentTag,
    DocumentTagAssignment,
    DocumentUsage,
    DocumentPage,
    DocumentChunk,
)
from schemas.user.document import (
    DocumentCreate,
    DocumentUpdate,
    DocumentProcessingJobCreate,
    DocumentProcessingJobUpdate,
    DocumentTagCreate,
    DocumentTagUpdate,
    DocumentTagAssignmentCreate,
    DocumentUsageCreate,
    DocumentUsageUpdate,
    DocumentPageCreate,
    DocumentPageUpdate,
    DocumentChunkCreate,
    DocumentChunkUpdate,
)


# =========================================================
# Documents CRUD
# =========================================================
class DocumentCRUD:
    def create(self, db: Session, data: DocumentCreate) -> Document:
        obj = Document(
            owner_id=data.owner_id,
            name=data.name,
            file_format=data.file_format,
            file_size_bytes=data.file_size_bytes,
            folder_path=data.folder_path,
            status=data.status or "processing",
            chunk_count=data.chunk_count or 0,
            uploaded_at=data.uploaded_at or datetime.now(datetime.utc),
        )
        db.add(obj)
        db.commit()
        db.refresh(obj)
        return obj

    def get(self, db: Session, document_id: int) -> Optional[Document]:
        stmt = select(Document).where(Document.document_id == document_id)
        return db.scalar(stmt)

    def get_by_owner(
        self,
        db: Session,
        owner_id: int,
        *,
        status: Optional[str] = None,
        q: Optional[str] = None,
        page: int = 1,
        size: int = 50,
    ) -> Tuple[Sequence[Document], int]:
        """
        단순 목록 조회 + 페이징.
        """
        stmt = select(Document).where(Document.owner_id == owner_id)

        if status:
            stmt = stmt.where(Document.status == status)

        if q:
            # 아주 단순 name LIKE 검색 (pg_trgm 인덱스는 DB 쪽에 있음)
            like = f"%{q}%"
            stmt = stmt.where(Document.name.ilike(like))

        total = db.scalar(
            select(func.count()).select_from(stmt.subquery())
        ) or 0

        stmt = (
            stmt.order_by(Document.uploaded_at.desc())
            .offset((page - 1) * size)
            .limit(size)
        )
        rows = db.scalars(stmt).all()
        return rows, total

    def update(
        self,
        db: Session,
        document_id: int,
        data: DocumentUpdate,
    ) -> Optional[Document]:
        stmt = (
            update(Document)
            .where(Document.document_id == document_id)
            .values(
                **{
                    k: v
                    for k, v in data.model_dump(exclude_unset=True).items()
                    if v is not None
                }
            )
            .returning(Document)
        )
        result = db.execute(stmt).scalar_one_or_none()
        db.commit()
        return result

    def delete(self, db: Session, document_id: int) -> None:
        stmt = delete(Document).where(Document.document_id == document_id)
        db.execute(stmt)
        db.commit()


document_crud = DocumentCRUD()


# =========================================================
# Document Processing Jobs CRUD
# =========================================================
class DocumentProcessingJobCRUD:
    def create(self, db: Session, data: DocumentProcessingJobCreate) -> DocumentProcessingJob:
        obj = DocumentProcessingJob(
            document_id=data.document_id,
            stage=data.stage,
            status=data.status or "queued",
            message=data.message,
            started_at=data.started_at,
            completed_at=data.completed_at,
        )
        db.add(obj)
        db.commit()
        db.refresh(obj)
        return obj

    def list_by_document(
        self,
        db: Session,
        document_id: int,
    ) -> Sequence[DocumentProcessingJob]:
        stmt = (
            select(DocumentProcessingJob)
            .where(DocumentProcessingJob.document_id == document_id)
            .order_by(DocumentProcessingJob.started_at.nullsfirst())
        )
        return db.scalars(stmt).all()

    def update(
        self,
        db: Session,
        job_id: int,
        data: DocumentProcessingJobUpdate,
    ) -> Optional[DocumentProcessingJob]:
        stmt = (
            update(DocumentProcessingJob)
            .where(DocumentProcessingJob.job_id == job_id)
            .values(
                **{
                    k: v
                    for k, v in data.model_dump(exclude_unset=True).items()
                }
            )
            .returning(DocumentProcessingJob)
        )
        result = db.execute(stmt).scalar_one_or_none()
        db.commit()
        return result


document_job_crud = DocumentProcessingJobCRUD()


# =========================================================
# Document Tags CRUD
# =========================================================
class DocumentTagCRUD:
    def get_by_name(self, db: Session, name: str) -> Optional[DocumentTag]:
        stmt = select(DocumentTag).where(DocumentTag.name == name)
        return db.scalar(stmt)

    def create(self, db: Session, data: DocumentTagCreate) -> DocumentTag:
        obj = DocumentTag(name=data.name)
        db.add(obj)
        db.commit()
        db.refresh(obj)
        return obj

    def ensure(self, db: Session, name: str) -> DocumentTag:
        """
        태그 있으면 반환, 없으면 생성.
        """
        tag = self.get_by_name(db, name)
        if tag:
            return tag
        return self.create(db, DocumentTagCreate(name=name))

    def update(
        self,
        db: Session,
        tag_id: int,
        data: DocumentTagUpdate,
    ) -> Optional[DocumentTag]:
        stmt = (
            update(DocumentTag)
            .where(DocumentTag.tag_id == tag_id)
            .values(
                **{
                    k: v
                    for k, v in data.model_dump(exclude_unset=True).items()
                }
            )
            .returning(DocumentTag)
        )
        result = db.execute(stmt).scalar_one_or_none()
        db.commit()
        return result


document_tag_crud = DocumentTagCRUD()


# =========================================================
# Document Tag Assignments CRUD
# =========================================================
class DocumentTagAssignmentCRUD:
    def assign(
        self,
        db: Session,
        data: DocumentTagAssignmentCreate,
    ) -> DocumentTagAssignment:
        obj = DocumentTagAssignment(
            document_id=data.document_id,
            tag_id=data.tag_id,
        )
        db.add(obj)
        db.commit()
        db.refresh(obj)
        return obj

    def list_by_document(
        self,
        db: Session,
        document_id: int,
    ) -> Sequence[DocumentTagAssignment]:
        stmt = select(DocumentTagAssignment).where(
            DocumentTagAssignment.document_id == document_id
        )
        return db.scalars(stmt).all()

    def delete(
        self,
        db: Session,
        assignment_id: int,
    ) -> None:
        stmt = delete(DocumentTagAssignment).where(
            DocumentTagAssignment.assignment_id == assignment_id
        )
        db.execute(stmt)
        db.commit()


document_tag_assignment_crud = DocumentTagAssignmentCRUD()


# =========================================================
# Document Usage CRUD
# =========================================================
class DocumentUsageCRUD:
    def upsert_usage(
        self,
        db: Session,
        data: DocumentUsageCreate,
        *,
        increment: int = 1,
    ) -> DocumentUsage:
        """
        (document_id, user_id, usage_type) 단위로 사용량 증가.
        """
        stmt = select(DocumentUsage).where(
            DocumentUsage.document_id == data.document_id,
            DocumentUsage.user_id == data.user_id,
            DocumentUsage.usage_type == data.usage_type,
        )
        usage = db.scalar(stmt)

        now = data.last_used_at or datetime.now(datetime.utc)

        if usage is None:
            usage = DocumentUsage(
                document_id=data.document_id,
                user_id=data.user_id,
                usage_type=data.usage_type,
                usage_count=data.usage_count or increment,
                last_used_at=now,
            )
            db.add(usage)
        else:
            usage.usage_count += increment
            usage.last_used_at = now

        db.commit()
        db.refresh(usage)
        return usage

    def list_by_document(
        self,
        db: Session,
        document_id: int,
    ) -> Sequence[DocumentUsage]:
        stmt = select(DocumentUsage).where(
            DocumentUsage.document_id == document_id
        )
        return db.scalars(stmt).all()

    def update(
        self,
        db: Session,
        usage_id: int,
        data: DocumentUsageUpdate,
    ) -> Optional[DocumentUsage]:
        stmt = (
            update(DocumentUsage)
            .where(DocumentUsage.usage_id == usage_id)
            .values(
                **{
                    k: v
                    for k, v in data.model_dump(exclude_unset=True).items()
                }
            )
            .returning(DocumentUsage)
        )
        result = db.execute(stmt).scalar_one_or_none()
        db.commit()
        return result


document_usage_crud = DocumentUsageCRUD()


# =========================================================
# Document Pages CRUD
# =========================================================
class DocumentPageCRUD:
    def create(self, db: Session, data: DocumentPageCreate) -> DocumentPage:
        obj = DocumentPage(
            document_id=data.document_id,
            page_no=data.page_no,
            image_url=data.image_url,
            created_at=data.created_at or datetime.now(datetime.utc),
        )
        db.add(obj)
        db.commit()
        db.refresh(obj)
        return obj

    def bulk_create(
        self,
        db: Session,
        pages: list[DocumentPageCreate],
    ) -> list[DocumentPage]:
        objs: list[DocumentPage] = []
        now = datetime.now(datetime.utc)
        for p in pages:
            obj = DocumentPage(
                document_id=p.document_id,
                page_no=p.page_no,
                image_url=p.image_url,
                created_at=p.created_at or now,
            )
            db.add(obj)
            objs.append(obj)
        db.commit()
        for obj in objs:
            db.refresh(obj)
        return objs

    def list_by_document(
        self,
        db: Session,
        document_id: int,
    ) -> Sequence[DocumentPage]:
        stmt = (
            select(DocumentPage)
            .where(DocumentPage.document_id == document_id)
            .order_by(DocumentPage.page_no.asc().nullsfirst())
        )
        return db.scalars(stmt).all()


document_page_crud = DocumentPageCRUD()


# =========================================================
# Document Chunks CRUD
# =========================================================
class DocumentChunkCRUD:
    def create(self, db: Session, data: DocumentChunkCreate) -> DocumentChunk:
        obj = DocumentChunk(
            document_id=data.document_id,
            page_id=data.page_id,
            chunk_index=data.chunk_index,
            chunk_text=data.chunk_text,
            # vector_memory는 service 레이어에서 임베딩 후 세팅
            created_at=data.created_at or datetime.now(datetime.utc),
        )
        db.add(obj)
        db.commit()
        db.refresh(obj)
        return obj

    def bulk_create(
        self,
        db: Session,
        chunks: list[DocumentChunk],
    ) -> list[DocumentChunk]:
        """
        service 레이어에서 이미 vector_memory까지 채운 DocumentChunk 인스턴스를
        한 번에 넣고 싶을 때 사용.
        """
        for ch in chunks:
            db.add(ch)
        db.commit()
        for ch in chunks:
            db.refresh(ch)
        return chunks

    def list_by_document(
        self,
        db: Session,
        document_id: int,
    ) -> Sequence[DocumentChunk]:
        stmt = (
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document_id)
            .order_by(DocumentChunk.chunk_index.asc())
        )
        return db.scalars(stmt).all()

    def list_by_document_page(
        self,
        db: Session,
        document_id: int,
        page_id: Optional[int] = None,
    ) -> Sequence[DocumentChunk]:
        stmt = select(DocumentChunk).where(
            DocumentChunk.document_id == document_id
        )
        if page_id is not None:
            stmt = stmt.where(DocumentChunk.page_id == page_id)
        stmt = stmt.order_by(DocumentChunk.chunk_index.asc())
        return db.scalars(stmt).all()


document_chunk_crud = DocumentChunkCRUD()
