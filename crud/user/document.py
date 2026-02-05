# crud/user/document.py
from __future__ import annotations

from typing import Optional, Sequence, Tuple, List, Any, Dict

from sqlalchemy.orm import Session
from sqlalchemy import select, update, delete, func, case
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
    DocumentPageCreate,
    DocumentChunkCreate,
    DocumentIngestionSettingCreate,
    DocumentIngestionSettingUpdate,
    DocumentSearchSettingCreate,
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
            scope=getattr(data, "scope", None) or "knowledge_base",
            session_id=getattr(data, "session_id", None),
            # uploaded_at은 서버에서 채우는 구조면 굳이 안 넣어도 됨
            uploaded_at=data.uploaded_at if getattr(data, "uploaded_at", None) is not None else None,
        )
        db.add(obj)
        db.flush()
        return obj

    def get(self, db: Session, knowledge_id: int) -> Optional[Document]:
        return db.scalar(select(Document).where(Document.knowledge_id == int(knowledge_id)))

    def get_by_owner(
        self,
        db: Session,
        owner_id: int,
        *,
        status: Optional[str] = None,
        q: Optional[str] = None,
        scope: Optional[str] = "knowledge_base",
        page: int = 1,
        size: int = 50,
    ) -> Tuple[Sequence[Document], int]:
        stmt = select(Document).where(Document.owner_id == int(owner_id))

        if scope is not None:
            stmt = stmt.where(Document.scope == scope)
        if status:
            stmt = stmt.where(Document.status == status)
        if q:
            stmt = stmt.where(Document.name.ilike(f"%{q}%"))

        total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0

        order_col = getattr(Document, "uploaded_at", None) or getattr(Document, "created_at", None)
        if order_col is not None:
            stmt = stmt.order_by(order_col.desc())
        else:
            stmt = stmt.order_by(Document.knowledge_id.desc())

        rows = db.scalars(
            stmt.offset(max(page - 1, 0) * size).limit(size)
        ).all()

        return rows, int(total)

    def update(self, db: Session, *, knowledge_id: int, data: DocumentUpdate) -> Optional[Document]:
        values = data.model_dump(exclude_unset=True)
        if not values:
            return self.get(db, knowledge_id)

        db.execute(
            update(Document)
            .where(Document.knowledge_id == int(knowledge_id))
            .values(**values)
        )
        db.flush()
        return self.get(db, knowledge_id)

    def delete(self, db: Session, *, knowledge_id: int) -> None:
        db.execute(delete(Document).where(Document.knowledge_id == int(knowledge_id)))
        db.flush()


document_crud = DocumentCRUD()

# =========================================================
# Document Ingestion Settings CRUD
# - schema Create를 통해 defaults를 정규화/검증 후 저장
# - extra: patch merge (None이면 {}로 clear)
# =========================================================
class DocumentIngestionSettingCRUD:
    def get(self, db: Session, knowledge_id: int) -> Optional[DocumentIngestionSetting]:
        return db.scalar(
            select(DocumentIngestionSetting).where(DocumentIngestionSetting.knowledge_id == int(knowledge_id))
        )

    def ensure_default(
        self,
        db: Session,
        *,
        knowledge_id: int,
        defaults: Dict[str, Any],
    ) -> DocumentIngestionSetting:
        # 스키마로 정규화/검증/기본값 주입
        normalized = DocumentIngestionSettingCreate(knowledge_id=int(knowledge_id), **(defaults or {}))
        values = normalized.model_dump()

        stmt = (
            pg_insert(DocumentIngestionSetting)
            .values(**values)
            .on_conflict_do_update(
                index_elements=["knowledge_id"],
                set_={
                    "chunk_size": values["chunk_size"],
                    "chunk_overlap": values["chunk_overlap"],
                    "max_chunks": values["max_chunks"],
                    "chunk_strategy": values["chunk_strategy"],
                    "chunking_mode": values["chunking_mode"],
                    "segment_separator": values["segment_separator"],
                    "parent_chunk_size": values["parent_chunk_size"],
                    "parent_chunk_overlap": values["parent_chunk_overlap"],
                    "embedding_provider": values["embedding_provider"],
                    "embedding_model": values["embedding_model"],
                    "embedding_dim": values["embedding_dim"],
                    "extra": values["extra"],
                },
            )
        )
        db.execute(stmt)
        db.flush()

        obj = self.get(db, knowledge_id)
        if obj is None:
            raise RuntimeError("DocumentIngestionSetting ensure_default failed")
        return obj

    def update_by_knowledge_id(
        self,
        db: Session,
        *,
        knowledge_id: int,
        data: DocumentIngestionSettingUpdate,
    ) -> DocumentIngestionSetting:
        values = data.model_dump(exclude_unset=True)

        # extra patch merge / clear
        if "extra" in values:
            if values["extra"] is None:
                values["extra"] = {}  # clear
            elif isinstance(values["extra"], dict):
                cur = self.get(db, knowledge_id)
                cur_extra = (getattr(cur, "extra", None) or {}) if cur is not None else {}
                if not isinstance(cur_extra, dict):
                    cur_extra = {}
                values["extra"] = {**cur_extra, **values["extra"]}

        if values:
            db.execute(
                update(DocumentIngestionSetting)
                .where(DocumentIngestionSetting.knowledge_id == int(knowledge_id))
                .values(**values)
            )
            db.flush()

        obj = self.get(db, knowledge_id)
        if obj is None:
            raise RuntimeError("DocumentIngestionSetting not found")
        return obj


document_ingestion_setting_crud = DocumentIngestionSettingCRUD()

# =========================================================
# Document Search Settings CRUD
# - schema Create로 Decimal/min_score, reranker_top_n<=top_k 검증
# =========================================================
class DocumentSearchSettingCRUD:
    def get(self, db: Session, knowledge_id: int) -> Optional[DocumentSearchSetting]:
        return db.scalar(
            select(DocumentSearchSetting).where(DocumentSearchSetting.knowledge_id == int(knowledge_id))
        )

    def ensure_default(
        self,
        db: Session,
        *,
        knowledge_id: int,
        defaults: Dict[str, Any],
    ) -> DocumentSearchSetting:
        normalized = DocumentSearchSettingCreate(knowledge_id=int(knowledge_id), **(defaults or {}))
        values = normalized.model_dump()

        stmt = (
            pg_insert(DocumentSearchSetting)
            .values(**values)
            .on_conflict_do_update(
                index_elements=["knowledge_id"],
                set_={
                    "top_k": values["top_k"],
                    "min_score": values["min_score"],        # Decimal 유지
                    "score_type": values["score_type"],      # 고정값
                    "reranker_enabled": values["reranker_enabled"],
                    "reranker_model": values["reranker_model"],
                    "reranker_top_n": values["reranker_top_n"],
                },
            )
        )
        db.execute(stmt)
        db.flush()

        obj = self.get(db, knowledge_id)
        if obj is None:
            raise RuntimeError("DocumentSearchSetting ensure_default failed")
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
                .where(DocumentSearchSetting.knowledge_id == int(knowledge_id))
                .values(**values)
            )
            db.flush()

        obj = self.get(db, knowledge_id)
        if obj is None:
            raise RuntimeError("DocumentSearchSetting not found")
        return obj


document_search_setting_crud = DocumentSearchSettingCRUD()

# =========================================================
# Document Usage CRUD (UPSERT + increment)
# =========================================================
class DocumentUsageCRUD:
    def upsert_usage(
        self,
        db: Session,
        data: DocumentUsageCreate,
        *,
        increment: int = 1,
    ) -> DocumentUsage:
        now_expr = data.last_used_at or func.now()

        values = {
            "knowledge_id": int(data.knowledge_id),
            "user_id": int(data.user_id),
            "usage_type": data.usage_type,
            "usage_count": int(getattr(data, "usage_count", None) or increment),
            "last_used_at": now_expr,
        }

        stmt = (
            pg_insert(DocumentUsage)
            .values(**values)
            .on_conflict_do_update(
                index_elements=["knowledge_id", "user_id", "usage_type"],
                set_={
                    "usage_count": DocumentUsage.usage_count + int(increment),
                    "last_used_at": now_expr,
                },
            )
        )
        db.execute(stmt)
        db.flush()

        obj = db.scalar(
            select(DocumentUsage).where(
                DocumentUsage.knowledge_id == int(data.knowledge_id),
                DocumentUsage.user_id == int(data.user_id),
                DocumentUsage.usage_type == data.usage_type,
            )
        )
        if obj is None:
            raise RuntimeError("DocumentUsage upsert failed")
        return obj


document_usage_crud = DocumentUsageCRUD()

# =========================================================
# Document Pages CRUD
# =========================================================
class DocumentPageCRUD:
    def create(self, db: Session, data: DocumentPageCreate) -> DocumentPage:
        obj = DocumentPage(
            knowledge_id=data.knowledge_id,
            page_no=data.page_no,
            image_url=getattr(data, "image_url", None),
        )
        db.add(obj)
        db.flush()
        return obj

    def bulk_create(self, db: Session, pages: list[DocumentPageCreate]) -> None:
        if not pages:
            return
        objs = [
            DocumentPage(
                knowledge_id=p.knowledge_id,
                page_no=p.page_no,
                image_url=getattr(p, "image_url", None),
            )
            for p in pages
        ]
        db.add_all(objs)
        db.flush()

    def delete_by_document(self, db: Session, knowledge_id: int) -> int:
        res = db.execute(delete(DocumentPage).where(DocumentPage.knowledge_id == int(knowledge_id)))
        db.flush()
        return int(res.rowcount or 0)

    def list_by_document(self, db: Session, knowledge_id: int) -> Sequence[DocumentPage]:
        return db.scalars(
            select(DocumentPage)
            .where(DocumentPage.knowledge_id == int(knowledge_id))
            .order_by(DocumentPage.page_no.asc().nullsfirst())
        ).all()


document_page_crud = DocumentPageCRUD()

# =========================================================
# Document Chunks CRUD (parent-child aware)
# =========================================================
class DocumentChunkCRUD:
    def get(self, db: Session, chunk_id: int) -> Optional[DocumentChunk]:
        return db.scalar(select(DocumentChunk).where(DocumentChunk.chunk_id == int(chunk_id)))

    def create(
        self,
        db: Session,
        data: DocumentChunkCreate,
        *,
        vector: Optional[Sequence[float]] = None,
    ) -> DocumentChunk:
        obj = DocumentChunk(
            knowledge_id=data.knowledge_id,
            page_id=getattr(data, "page_id", None),
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
        return obj

    def bulk_create(
        self,
        db: Session,
        items: list[tuple[DocumentChunkCreate, Optional[Sequence[float]]]],
    ) -> None:
        if not items:
            return
        objs: list[DocumentChunk] = []
        for data, vector in items:
            objs.append(
                DocumentChunk(
                    knowledge_id=data.knowledge_id,
                    page_id=getattr(data, "page_id", None),
                    chunk_level=data.chunk_level,
                    parent_chunk_id=data.parent_chunk_id,
                    segment_index=data.segment_index,
                    chunk_index_in_segment=data.chunk_index_in_segment,
                    chunk_index=data.chunk_index,
                    chunk_text=data.chunk_text,
                    vector_memory=list(vector) if vector is not None else None,
                )
            )
        db.add_all(objs)
        db.flush()

    def delete_by_document(self, db: Session, knowledge_id: int) -> int:
        res = db.execute(delete(DocumentChunk).where(DocumentChunk.knowledge_id == int(knowledge_id)))
        db.flush()
        return int(res.rowcount or 0)

    def list_by_document(self, db: Session, knowledge_id: int) -> Sequence[DocumentChunk]:
        parent_first = case((DocumentChunk.chunk_level == "parent", 0), else_=1)
        return db.scalars(
            select(DocumentChunk)
            .where(DocumentChunk.knowledge_id == int(knowledge_id))
            .order_by(
                DocumentChunk.segment_index.asc().nullsfirst(),
                parent_first.asc(),
                DocumentChunk.chunk_index_in_segment.asc().nullsfirst(),
                DocumentChunk.chunk_index.asc().nullsfirst(),
                DocumentChunk.chunk_id.asc(),
            )
        ).all()

    def list_children_by_parent(self, db: Session, parent_chunk_id: int) -> Sequence[DocumentChunk]:
        return db.scalars(
            select(DocumentChunk)
            .where(
                DocumentChunk.parent_chunk_id == int(parent_chunk_id),
                DocumentChunk.chunk_level == "child",
            )
            .order_by(
                DocumentChunk.chunk_index_in_segment.asc().nullsfirst(),
                DocumentChunk.chunk_index.asc().nullsfirst(),
                DocumentChunk.chunk_id.asc(),
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
            stmt = stmt.where(DocumentChunk.knowledge_id == int(knowledge_id))

        dist = DocumentChunk.vector_memory.cosine_distance(query_vector)  # type: ignore

        if min_score is not None:
            stmt = stmt.where(dist <= (1.0 - float(min_score)))

        return list(db.scalars(stmt.order_by(dist).limit(int(top_k))).all())


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
