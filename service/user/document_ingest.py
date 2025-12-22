# service/user/document_ingest.py
from __future__ import annotations

from typing import Sequence, Optional, List

from sqlalchemy.orm import Session

from models.user.document import Document
from crud.user.document import (
    document_chunk_crud,
    document_ingestion_setting_crud,
)
from schemas.user.document import DocumentChunkCreate
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_service.embedding.get_vector import texts_to_vectors


# =========================================================
# helpers
# =========================================================
def _build_child_splitter(
    *,
    chunk_size: int,
    chunk_overlap: int,
    strategy: str,
):
    if strategy == "recursive":
        return RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
    raise ValueError(f"Unsupported chunk_strategy: {strategy}")


def _split_parents(
    *,
    text: str,
    separator: Optional[str],
) -> list[str]:
    """
    separator 기준으로 parent segment 분리
    - separator 없으면 전체를 하나의 parent로 취급
    """
    if not separator:
        return [text.strip()] if text.strip() else []

    parts = [p.strip() for p in text.split(separator)]
    return [p for p in parts if p]


# =========================================================
# main service
# =========================================================
def ingest_document_text(
    db: Session,
    *,
    document: Document,
    full_text: str,
) -> int:
    """
    ingestion_setting 기준으로
    - general / parent_child 모드 처리
    - child chunk만 embedding
    반환: 생성된 child chunk 수
    """
    setting = document_ingestion_setting_crud.get(db, document.knowledge_id)
    if setting is None:
        raise RuntimeError("DocumentIngestionSetting not found")

    # 기본값 방어
    chunking_mode = getattr(setting, "chunking_mode", "general")
    segment_separator = getattr(setting, "segment_separator", None)

    # -----------------------------------------------------
    # 0) 기존 청크 삭제 (reindex)
    # -----------------------------------------------------
    document_chunk_crud.delete_by_document(db, document.knowledge_id)

    # -----------------------------------------------------
    # 1) child splitter 준비
    # -----------------------------------------------------
    child_splitter = _build_child_splitter(
        chunk_size=int(setting.chunk_size),
        chunk_overlap=int(setting.chunk_overlap),
        strategy=str(setting.chunk_strategy),
    )

    chunk_rows: list[tuple[DocumentChunkCreate, Optional[Sequence[float]]]] = []

    global_chunk_index = 1
    total_child_count = 0

    # =====================================================
    # 2) GENERAL MODE
    # =====================================================
    if chunking_mode == "general":
        child_texts = child_splitter.split_text(full_text)
        if not child_texts:
            return 0

        vectors = texts_to_vectors(child_texts)

        for i, (text, vec) in enumerate(zip(child_texts, vectors), start=1):
            chunk_rows.append(
                (
                    DocumentChunkCreate(
                        knowledge_id=document.knowledge_id,
                        chunk_level="child",
                        parent_chunk_id=None,
                        segment_index=1,
                        chunk_index_in_segment=i,
                        chunk_index=global_chunk_index,
                        chunk_text=text,
                    ),
                    vec,
                )
            )
            global_chunk_index += 1
            total_child_count += 1

        document_chunk_crud.bulk_create(db, chunk_rows)

    # =====================================================
    # 3) PARENT–CHILD MODE
    # =====================================================
    else:
        parents = _split_parents(
            text=full_text,
            separator=segment_separator,
        )

        for seg_idx, parent_text in enumerate(parents, start=1):
            # -------------------------
            # 3-1) parent chunk (NO vector)
            # -------------------------
            parent_row = document_chunk_crud.create(
                db,
                DocumentChunkCreate(
                    knowledge_id=document.knowledge_id,
                    chunk_level="parent",
                    parent_chunk_id=None,
                    segment_index=seg_idx,
                    chunk_index=None,
                    chunk_index_in_segment=None,
                    chunk_text=parent_text,
                ),
                vector=None,
            )

            # -------------------------
            # 3-2) child chunks
            # -------------------------
            child_texts = child_splitter.split_text(parent_text)
            if not child_texts:
                continue

            vectors = texts_to_vectors(child_texts)

            for i, (text, vec) in enumerate(zip(child_texts, vectors), start=1):
                chunk_rows.append(
                    (
                        DocumentChunkCreate(
                            knowledge_id=document.knowledge_id,
                            chunk_level="child",
                            parent_chunk_id=parent_row.chunk_id,
                            segment_index=seg_idx,
                            chunk_index_in_segment=i,
                            chunk_index=global_chunk_index,
                            chunk_text=text,
                        ),
                        vec,
                    )
                )
                global_chunk_index += 1
                total_child_count += 1

        if chunk_rows:
            document_chunk_crud.bulk_create(db, chunk_rows)

    # -----------------------------------------------------
    # 4) 문서 통계 업데이트
    # -----------------------------------------------------
    document.chunk_count = total_child_count
    db.flush()

    return total_child_count
