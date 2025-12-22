# crud/user/document.py
from __future__ import annotations

from typing import Optional, Sequence, Tuple, List, Any

from sqlalchemy.orm import Session
from sqlalchemy import select, update, delete, func
from sqlalchemy.dialects.postgresql import insert as pg_insert

from models.user.document import (
    Document,
    DocumentUsage,
    DocumentPage,
    DocumentChunk,
    DocumentIngestionSetting,
    DocumentSearchSetting,
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
    DocumentIngestionSettingUpdate,
    DocumentSearchSettingUpdate,
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
        return db.scalar(
            select(Document).where(Document.knowledge_id == knowledge_id)
        )

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
            stmt = stmt.where(Document.name.ilike(f"%{q}%"))

        total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0

        rows = db.scalars(
            stmt.order_by(Document.uploaded_at.desc())
            .offset((page - 1) * size)
            .limit(size)
        ).all()

        return rows, total

    def update(self, db: Session, knowledge_id: int, data: DocumentUpdate) -> Optional[Document]:
        values = data.model_dump(exclude_unset=True)
        if not values:
            return self.get(db, knowledge_id)

        db.execute(
            update(Document)
            .where(Document.knowledge_id == knowledge_id)
            .values(**values)
        )
        db.flush()
        return self.get(db, knowledge_id)

    def delete(self, db: Session, knowledge_id: int) -> None:
        db.execute(
            delete(Document).where(Document.knowledge_id == knowledge_id)
        )
        db.flush()


document_crud = DocumentCRUD()

# =========================================================
# Document Ingestion Settings CRUD
# =========================================================
class DocumentIngestionSettingCRUD:
    def get(self, db: Session, knowledge_id: int) -> Optional[DocumentIngestionSetting]:
        return db.scalar(
            select(DocumentIngestionSetting)
            .where(DocumentIngestionSetting.knowledge_id == knowledge_id)
        )

    def ensure_default(
        self,
        db: Session,
        *,
        knowledge_id: int,
        defaults: dict[str, Any],
    ) -> DocumentIngestionSetting:
        values = {
            "knowledge_id": knowledge_id,
            "chunk_size": defaults["chunk_size"],
            "chunk_overlap": defaults["chunk_overlap"],
            "max_chunks": defaults["max_chunks"],
            "chunk_strategy": defaults["chunk_strategy"],
            "chunking_mode": defaults.get("chunking_mode", "general"),
            "segment_separator": defaults.get("segment_separator"),
            "parent_chunk_size": defaults.get("parent_chunk_size"),
            "parent_chunk_overlap": defaults.get("parent_chunk_overlap"),
            "embedding_provider": defaults["embedding_provider"],
            "embedding_model": defaults["embedding_model"],
            "embedding_dim": defaults["embedding_dim"],
            "extra": defaults.get("extra") or {},
        }

        db.execute(
            pg_insert(DocumentIngestionSetting)
            .values(**values)
            .on_conflict_do_nothing(index_elements=["knowledge_id"])
        )
        db.flush()

        obj = self.get(db, knowledge_id)
        assert obj is not None
        return obj

    def update_by_knowledge_id(
        self,
        db: Session,
        *,
        knowledge_id: int,
        data: DocumentIngestionSettingUpdate,
    ) -> DocumentIngestionSetting:
        values = data.model_dump(exclude_unset=True)
        if values:
            db.execute(
                update(DocumentIngestionSetting)
                .where(DocumentIngestionSetting.knowledge_id == knowledge_id)
                .values(**values)
            )
            db.flush()

        obj = self.get(db, knowledge_id)
        assert obj is not None
        return obj


document_ingestion_setting_crud = DocumentIngestionSettingCRUD()

# =========================================================
# Document Search Settings CRUD
# =========================================================
class DocumentSearchSettingCRUD:
    def get(self, db: Session, knowledge_id: int) -> Optional[DocumentSearchSetting]:
        return db.scalar(
            select(DocumentSearchSetting)
            .where(DocumentSearchSetting.knowledge_id == knowledge_id)
        )

    def ensure_default(
        self,
        db: Session,
        *,
        knowledge_id: int,
        defaults: dict[str, Any],
    ) -> DocumentSearchSetting:
        values = {
            "knowledge_id": knowledge_id,
            "top_k": defaults["top_k"],
            "min_score": defaults["min_score"],
            "score_type": defaults["score_type"],
            "reranker_enabled": defaults["reranker_enabled"],
            "reranker_model": defaults.get("reranker_model"),
            "reranker_top_n": defaults["reranker_top_n"],
        }

        db.execute(
            pg_insert(DocumentSearchSetting)
            .values(**values)
            .on_conflict_do_nothing(index_elements=["knowledge_id"])
        )
        db.flush()

        obj = self.get(db, knowledge_id)
        assert obj is not None
        return obj

    def update_by_knowledge_id(
        self,
        db: Session,
        *,
        knowledge_id: int,
        data: DocumentSearchSettingUpdate,
    ) -> DocumentSearchSetting:
        values = data.model_dump(exclude_unset=True)
        if values:
            db.execute(
                update(DocumentSearchSetting)
                .where(DocumentSearchSetting.knowledge_id == knowledge_id)
                .values(**values)
            )
            db.flush()

        obj = self.get(db, knowledge_id)
        assert obj is not None
        return obj


document_search_setting_crud = DocumentSearchSettingCRUD()

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
        usage = db.scalar(
            select(DocumentUsage).where(
                DocumentUsage.knowledge_id == data.knowledge_id,
                DocumentUsage.user_id == data.user_id,
                DocumentUsage.usage_type == data.usage_type,
            )
        )

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
            usage.usage_count += increment
            usage.last_used_at = now_expr

        db.flush()
        db.refresh(usage)
        return usage


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
        )
        db.add(obj)
        db.flush()
        db.refresh(obj)
        return obj

    def bulk_create(self, db: Session, pages: list[DocumentPageCreate]) -> list[DocumentPage]:
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
        for o in objs:
            db.refresh(o)
        return objs

    def list_by_document(self, db: Session, knowledge_id: int) -> Sequence[DocumentPage]:
        return db.scalars(
            select(DocumentPage)
            .where(DocumentPage.knowledge_id == knowledge_id)
            .order_by(DocumentPage.page_no.asc().nullsfirst())
        ).all()


document_page_crud = DocumentPageCRUD()

# =========================================================
# Document Chunks CRUD (parent-child aware)
# =========================================================
class DocumentChunkCRUD:
    def create(
        self,
        db: Session,
        data: DocumentChunkCreate,
        *,
        vector: Optional[Sequence[float]] = None,
    ) -> DocumentChunk:
        obj = DocumentChunk(
            knowledge_id=data.knowledge_id,
            page_id=data.page_id,
            chunk_level=data.chunk_level,
            parent_chunk_id=data.parent_chunk_id,
            segment_index=data.segment_index,
            chunk_index_in_segment=data.chunk_index_in_segment,
            chunk_index=data.chunk_index,
            chunk_text=data.chunk_text,
            vector_memory=list(vector) if vector is not None else None,
        )
        db.add(obj)
        db.flush()
        db.refresh(obj)
        return obj

    def bulk_create(
        self,
        db: Session,
        items: list[tuple[DocumentChunkCreate, Optional[Sequence[float]]]],
    ) -> list[DocumentChunk]:
        objs: list[DocumentChunk] = []
        for data, vector in items:
            obj = DocumentChunk(
                knowledge_id=data.knowledge_id,
                page_id=data.page_id,
                chunk_level=data.chunk_level,
                parent_chunk_id=data.parent_chunk_id,
                segment_index=data.segment_index,
                chunk_index_in_segment=data.chunk_index_in_segment,
                chunk_index=data.chunk_index,
                chunk_text=data.chunk_text,
                vector_memory=list(vector) if vector is not None else None,
            )
            db.add(obj)
            objs.append(obj)

        db.flush()
        for o in objs:
            db.refresh(o)
        return objs

    def delete_by_document(self, db: Session, knowledge_id: int) -> int:
        res = db.execute(
            delete(DocumentChunk).where(DocumentChunk.knowledge_id == knowledge_id)
        )
        db.flush()
        return int(res.rowcount or 0)

    def list_by_document(self, db: Session, knowledge_id: int) -> Sequence[DocumentChunk]:
        return db.scalars(
            select(DocumentChunk)
            .where(DocumentChunk.knowledge_id == knowledge_id)
            .order_by(
                DocumentChunk.segment_index.asc(),
                DocumentChunk.chunk_level.desc(),  # parent 먼저
                DocumentChunk.chunk_index_in_segment.asc().nullsfirst(),
            )
        ).all()

    def search_by_vector(
        self,
        db: Session,
        *,
        query_vector: Sequence[float],
        knowledge_id: Optional[int] = None,
        top_k: int = 8,
        min_score: Optional[float] = None,
        score_type: str = "cosine_similarity",
    ) -> List[DocumentChunk]:
        if score_type != "cosine_similarity":
            raise ValueError("Only cosine_similarity is supported")

        stmt = select(DocumentChunk).where(DocumentChunk.chunk_level == "child")
        if knowledge_id is not None:
            stmt = stmt.where(DocumentChunk.knowledge_id == knowledge_id)

        dist = DocumentChunk.vector_memory.cosine_distance(query_vector)  # type: ignore

        if min_score is not None:
            stmt = stmt.where(dist <= (1.0 - float(min_score)))

        return list(
            db.scalars(stmt.order_by(dist).limit(top_k)).all()
        )


document_chunk_crud = DocumentChunkCRUD()

# =========================================================
# Shortcut
# =========================================================
def search_chunks_by_vector(
    db: Session,
    *,
    query_vector: Sequence[float],
    knowledge_id: Optional[int] = None,
    top_k: int = 8,
    min_score: Optional[float] = None,
    score_type: str = "cosine_similarity",
) -> List[DocumentChunk]:
    return document_chunk_crud.search_by_vector(
        db=db,
        query_vector=query_vector,
        knowledge_id=knowledge_id,
        top_k=top_k,
        min_score=min_score,
        score_type=score_type,
    )
