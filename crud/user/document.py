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
# Document Settings CRUD (1:1, knowledge_id PK)
# =========================================================
class DocumentIngestionSettingCRUD:
    def get(self, db: Session, knowledge_id: int) -> Optional[DocumentIngestionSetting]:
        stmt = select(DocumentIngestionSetting).where(
            DocumentIngestionSetting.knowledge_id == knowledge_id
        )
        return db.scalar(stmt)

    def create_default(
        self,
        db: Session,
        *,
        knowledge_id: int,
        defaults: dict[str, Any],
    ) -> DocumentIngestionSetting:
        """
        기본 row 생성 (이미 존재하면 IntegrityError 가능)
        - commit은 바깥에서
        """
        obj = DocumentIngestionSetting(
            knowledge_id=knowledge_id,
            chunk_size=defaults["chunk_size"],
            chunk_overlap=defaults["chunk_overlap"],
            max_chunks=defaults["max_chunks"],
            chunk_strategy=defaults["chunk_strategy"],
            embedding_provider=defaults["embedding_provider"],
            embedding_model=defaults["embedding_model"],
            embedding_dim=defaults["embedding_dim"],  # DB에서 1536 제약
            extra=defaults.get("extra") or {},
        )
        db.add(obj)
        db.flush()
        db.refresh(obj)
        return obj

    def ensure_default(
        self,
        db: Session,
        *,
        knowledge_id: int,
        defaults: dict[str, Any],
    ) -> DocumentIngestionSetting:
        """
        - “없으면 생성, 있으면 유지” (UPSERT do nothing)
        - 문서 생성 직후 호출해서 row 존재를 보장하는 용도
        """
        values = {
            "knowledge_id": knowledge_id,
            "chunk_size": defaults["chunk_size"],
            "chunk_overlap": defaults["chunk_overlap"],
            "max_chunks": defaults["max_chunks"],
            "chunk_strategy": defaults["chunk_strategy"],
            "embedding_provider": defaults["embedding_provider"],
            "embedding_model": defaults["embedding_model"],
            "embedding_dim": defaults["embedding_dim"],
            "extra": defaults.get("extra") or {},
        }

        stmt = (
            pg_insert(DocumentIngestionSetting)
            .values(**values)
            .on_conflict_do_nothing(index_elements=["knowledge_id"])
        )
        db.execute(stmt)
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
        """
        부분 수정(PATCH)
        - schema 단에서 chunk_overlap < chunk_size 등 검증
        - embedding_dim은 1536만 허용(스키마 + DB 제약)
        """
        values = data.model_dump(exclude_unset=True)
        if not values:
            obj = self.get(db, knowledge_id)
            assert obj is not None
            return obj

        stmt = (
            update(DocumentIngestionSetting)
            .where(DocumentIngestionSetting.knowledge_id == knowledge_id)
            .values(**values)
        )
        db.execute(stmt)
        db.flush()

        obj = self.get(db, knowledge_id)
        assert obj is not None
        return obj


class DocumentSearchSettingCRUD:
    def get(self, db: Session, knowledge_id: int) -> Optional[DocumentSearchSetting]:
        stmt = select(DocumentSearchSetting).where(
            DocumentSearchSetting.knowledge_id == knowledge_id
        )
        return db.scalar(stmt)

    def create_default(
        self,
        db: Session,
        *,
        knowledge_id: int,
        defaults: dict[str, Any],
    ) -> DocumentSearchSetting:
        obj = DocumentSearchSetting(
            knowledge_id=knowledge_id,
            top_k=defaults["top_k"],
            min_score=defaults["min_score"],          # 유사도 기준
            score_type=defaults["score_type"],        # DB에서 cosine_similarity 고정 제약
            reranker_enabled=defaults["reranker_enabled"],
            reranker_model=defaults.get("reranker_model"),
            reranker_top_n=defaults["reranker_top_n"],
        )
        db.add(obj)
        db.flush()
        db.refresh(obj)
        return obj

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

        stmt = (
            pg_insert(DocumentSearchSetting)
            .values(**values)
            .on_conflict_do_nothing(index_elements=["knowledge_id"])
        )
        db.execute(stmt)
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
        if not values:
            obj = self.get(db, knowledge_id)
            assert obj is not None
            return obj

        stmt = (
            update(DocumentSearchSetting)
            .where(DocumentSearchSetting.knowledge_id == knowledge_id)
            .values(**values)
        )
        db.execute(stmt)
        db.flush()

        obj = self.get(db, knowledge_id)
        assert obj is not None
        return obj


document_ingestion_setting_crud = DocumentIngestionSettingCRUD()
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

    def delete_by_document(self, db: Session, knowledge_id: int) -> int:
        """
        reindex 전에 기존 청크 정리용 (단순 삭제)
        반환: 삭제된 row 수
        """
        stmt = delete(DocumentChunk).where(DocumentChunk.knowledge_id == knowledge_id)
        res = db.execute(stmt)
        db.flush()
        return int(res.rowcount or 0)

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
        min_score: Optional[float] = None,    # 유사도 기준(0~1)
        score_type: str = "cosine_similarity",
    ) -> List[DocumentChunk]:
        """
        score_type은 cosine_similarity만 지원
        - pgvector는 cosine_distance로 정렬/필터가 쉬워서
          min_score(유사도) -> max_distance(거리) = 1 - min_score 로 변환해서 필터함
        """
        if score_type != "cosine_similarity":
            raise ValueError("Only cosine_similarity is supported in MVP")

        stmt = select(DocumentChunk)
        if knowledge_id is not None:
            stmt = stmt.where(DocumentChunk.knowledge_id == knowledge_id)

        dist = DocumentChunk.vector_memory.cosine_distance(query_vector)  # type: ignore[attr-defined]

        if min_score is not None:
            # 유사도(min_score) >= x  <=>  거리(distance) <= 1 - x
            max_distance = 1.0 - float(min_score)
            stmt = stmt.where(dist <= max_distance)

        stmt = stmt.order_by(dist).limit(top_k)
        chunks = db.scalars(stmt).all()
        return list(chunks)


document_chunk_crud = DocumentChunkCRUD()


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
