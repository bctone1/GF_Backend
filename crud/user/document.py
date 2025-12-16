# crud/user/document.py
from __future__ import annotations

from typing import Optional, Sequence, Tuple, List

from sqlalchemy.orm import Session
from sqlalchemy import select, update, delete, func

from models.user.document import (
    Document,
    DocumentUsage,
    DocumentPage,
    DocumentChunk,
)
from schemas.user.document import (
    DocumentCreate,
    DocumentUpdate,
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
            status=data.status or "uploading",
            chunk_count=data.chunk_count or 0,
            progress=data.progress or 0,
            error_message=data.error_message,
        )
        db.add(obj)
        db.flush()
        db.refresh(obj)
        return obj

    def get(self, db: Session, knowledge_id: int) -> Optional[Document]:
        stmt = select(Document).where(Document.knowledge_id == knowledge_id)
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
        stmt = select(Document).where(Document.owner_id == owner_id)

        if status:
            stmt = stmt.where(Document.status == status)

        if q:
            like = f"%{q}%"
            stmt = stmt.where(Document.name.ilike(like))

        total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0

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
        knowledge_id: int,
        data: DocumentUpdate,
    ) -> Optional[Document]:
        values = {
            k: v
            for k, v in data.model_dump(exclude_unset=True).items()
            if v is not None
        }
        if not values:
            return self.get(db, knowledge_id)

        stmt = (
            update(Document)
            .where(Document.knowledge_id == knowledge_id)
            .values(**values)
        )
        db.execute(stmt)
        db.flush()
        return self.get(db, knowledge_id)

    def delete(self, db: Session, knowledge_id: int) -> None:
        stmt = delete(Document).where(Document.knowledge_id == knowledge_id)
        db.execute(stmt)
        db.flush()


document_crud = DocumentCRUD()


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
        (knowledge_id, user_id, usage_type) 단위로 사용량 증가.
        commit 은 바깥에서 한 번만
        """
        stmt = select(DocumentUsage).where(
            DocumentUsage.knowledge_id == data.knowledge_id,
            DocumentUsage.user_id == data.user_id,
            DocumentUsage.usage_type == data.usage_type,
        )
        usage = db.scalar(stmt)

        now_expr = data.last_used_at or func.now()

        if usage is None:
            usage = DocumentUsage(
                knowledge_id=data.knowledge_id,
                user_id=data.user_id,
                usage_type=data.usage_type,
                usage_count=data.usage_count or increment,
                last_used_at=now_expr,
            )
            db.add(usage)
        else:
            usage.usage_count = (usage.usage_count or 0) + increment
            usage.last_used_at = now_expr

        db.flush()
        db.refresh(usage)
        return usage

    def list_by_document(
        self,
        db: Session,
        knowledge_id: int,
    ) -> Sequence[DocumentUsage]:
        stmt = select(DocumentUsage).where(DocumentUsage.knowledge_id == knowledge_id)
        return db.scalars(stmt).all()

    def update(
        self,
        db: Session,
        usage_id: int,
        data: DocumentUsageUpdate,
    ) -> Optional[DocumentUsage]:
        values = {k: v for k, v in data.model_dump(exclude_unset=True).items()}
        if not values:
            stmt = select(DocumentUsage).where(DocumentUsage.usage_id == usage_id)
            return db.scalar(stmt)

        stmt = (
            update(DocumentUsage)
            .where(DocumentUsage.usage_id == usage_id)
            .values(**values)
        )
        db.execute(stmt)
        db.flush()
        stmt = select(DocumentUsage).where(DocumentUsage.usage_id == usage_id)
        return db.scalar(stmt)


document_usage_crud = DocumentUsageCRUD()


# =========================================================
# Document Pages CRUD
# =========================================================
class DocumentPageCRUD:
    def create(self, db: Session, data: DocumentPageCreate) -> DocumentPage:
        obj = DocumentPage(
            knowledge_id=data.knowledge_id,
            page_no=data.page_no,
            image_url=data.image_url,
            # created_at 은 DB default 사용
        )
        db.add(obj)
        db.flush()
        db.refresh(obj)
        return obj

    def bulk_create(
        self,
        db: Session,
        pages: list[DocumentPageCreate],
    ) -> list[DocumentPage]:
        objs: list[DocumentPage] = []
        for p in pages:
            obj = DocumentPage(
                knowledge_id=p.knowledge_id,
                page_no=p.page_no,
                image_url=p.image_url,
            )
            db.add(obj)
            objs.append(obj)
        db.flush()
        for obj in objs:
            db.refresh(obj)
        return objs

    def list_by_document(
        self,
        db: Session,
        knowledge_id: int,
    ) -> Sequence[DocumentPage]:
        stmt = (
            select(DocumentPage)
            .where(DocumentPage.knowledge_id == knowledge_id)
            .order_by(DocumentPage.page_no.asc().nullsfirst())
        )
        return db.scalars(stmt).all()


document_page_crud = DocumentPageCRUD()


# =========================================================
# Document Chunks CRUD
# =========================================================
class DocumentChunkCRUD:
    def create(
        self,
        db: Session,
        data: DocumentChunkCreate,
        *,
        vector: Sequence[float],
    ) -> DocumentChunk:
        obj = DocumentChunk(
            knowledge_id=data.knowledge_id,
            page_id=data.page_id,
            chunk_index=data.chunk_index,
            chunk_text=data.chunk_text,
            vector_memory=list(vector),
            # created_at 은 DB default 사용
        )
        db.add(obj)
        db.flush()
        db.refresh(obj)
        return obj

    def bulk_create(
        self,
        db: Session,
        items: list[tuple[DocumentChunkCreate, Sequence[float]]],
    ) -> list[DocumentChunk]:
        objs: list[DocumentChunk] = []
        for data, vector in items:
            obj = DocumentChunk(
                knowledge_id=data.knowledge_id,
                page_id=data.page_id,
                chunk_index=data.chunk_index,
                chunk_text=data.chunk_text,
                vector_memory=list(vector),
            )
            db.add(obj)
            objs.append(obj)
        db.flush()
        for obj in objs:
            db.refresh(obj)
        return objs

    def list_by_document(
        self,
        db: Session,
        knowledge_id: int,
    ) -> Sequence[DocumentChunk]:
        stmt = (
            select(DocumentChunk)
            .where(DocumentChunk.knowledge_id == knowledge_id)
            .order_by(DocumentChunk.chunk_index.asc())
        )
        return db.scalars(stmt).all()

    def list_by_document_page(
        self,
        db: Session,
        knowledge_id: int,
        page_id: Optional[int] = None,
    ) -> Sequence[DocumentChunk]:
        stmt = select(DocumentChunk).where(DocumentChunk.knowledge_id == knowledge_id)
        if page_id is not None:
            stmt = stmt.where(DocumentChunk.page_id == page_id)
        stmt = stmt.order_by(DocumentChunk.chunk_index.asc())
        return db.scalars(stmt).all()

    def search_by_vector(
        self,
        db: Session,
        *,
        query_vector: Sequence[float],
        knowledge_id: Optional[int] = None,
        top_k: int = 8,
    ) -> List[DocumentChunk]:
        stmt = select(DocumentChunk)
        if knowledge_id is not None:
            stmt = stmt.where(DocumentChunk.knowledge_id == knowledge_id)

        stmt = (
            stmt.order_by(
                DocumentChunk.vector_memory.cosine_distance(query_vector)  # type: ignore[attr-defined]
            )
            .limit(top_k)
        )
        chunks = db.scalars(stmt).all()
        return list(chunks)


document_chunk_crud = DocumentChunkCRUD()


def search_chunks_by_vector(
    db: Session,
    *,
    query_vector: Sequence[float],
    knowledge_id: Optional[int] = None,
    top_k: int = 8,
) -> List[DocumentChunk]:
    return document_chunk_crud.search_by_vector(
        db=db,
        query_vector=query_vector,
        knowledge_id=knowledge_id,
        top_k=top_k,
    )
