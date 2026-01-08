# service/user/document_ingest.py
from __future__ import annotations

from typing import Sequence, Optional, List, Tuple, Callable

from sqlalchemy.orm import Session

from core import config
from core.pricing import tokens_for_texts

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
def _count_tokens(model: str, texts: List[str]) -> int:
    """
    embedding 비용 계산용 토큰 카운트
    - core.pricing.tokens_for_texts는 "총 토큰 수(int)"를 반환한다고 가정
    """
    if not texts:
        return 0
    return int(tokens_for_texts(model, texts))


def _tok_len_factory(model: str) -> Callable[[str], int]:
    def _tok_len(s: str) -> int:
        return _count_tokens(model, [s])
    return _tok_len


def _build_child_splitter(
    *,
    chunk_size: int,
    chunk_overlap: int,
    strategy: str,
    length_function: Optional[Callable[[str], int]] = None,
):
    if strategy == "recursive":
        return RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=length_function,
            separators=["\n\n", "\n", " ", ""],
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
        return [text.strip()] if text and text.strip() else []

    parts = [p.strip() for p in text.split(separator)]
    return [p for p in parts if p]


def _clean_texts(texts: List[str]) -> List[str]:
    return [t.strip() for t in texts if t and t.strip()]


# =========================================================
# main service
# =========================================================
def ingest_document_text(
    db: Session,
    *,
    document: Document,
    full_text: str,
) -> Tuple[int, int]:
    """
    ingestion_setting 기준으로
    - general / parent_child 모드 처리
    - child chunk만 embedding
    반환: (생성된 child chunk 수, 임베딩에 사용된 총 토큰 수)
    """
    setting = document_ingestion_setting_crud.get(db, document.knowledge_id)
    if setting is None:
        raise RuntimeError("DocumentIngestionSetting not found")

    # 기본값 방어
    chunking_mode = getattr(setting, "chunking_mode", "general")
    segment_separator = getattr(setting, "segment_separator", None)

    chunk_size = int(getattr(setting, "chunk_size", 800) or 800)
    chunk_overlap = int(getattr(setting, "chunk_overlap", 200) or 0)
    chunk_strategy = str(getattr(setting, "chunk_strategy", "recursive") or "recursive")
    max_chunks = int(getattr(setting, "max_chunks", 0) or 0)  # 0이면 제한 없음(방어)
    embed_model = (
        getattr(setting, "embedding_model", None)
        or getattr(config, "DEFAULT_EMBEDDING_MODEL", "text-embedding-3-small")
    )

    # -----------------------------------------------------
    # 0) 기존 청크 삭제 (reindex)
    # -----------------------------------------------------
    document_chunk_crud.delete_by_document(db, document.knowledge_id)

    # 텍스트가 비면 바로 끝
    if not full_text or not full_text.strip():
        document.chunk_count = 0
        db.flush()
        return 0, 0

    # -----------------------------------------------------
    # 1) child splitter 준비
    # -----------------------------------------------------
    child_splitter = _build_child_splitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        strategy=chunk_strategy,
        length_function=_tok_len_factory(embed_model),
    )

    chunk_rows: list[tuple[DocumentChunkCreate, Optional[Sequence[float]]]] = []

    global_chunk_index = 1
    total_child_count = 0
    total_tokens = 0

    # max_chunks 제어용(전체 child 기준)
    remaining = max_chunks if max_chunks > 0 else None  # None이면 무제한

    # =====================================================
    # 2) GENERAL MODE
    # =====================================================
    if chunking_mode == "general":
        child_texts = _clean_texts(child_splitter.split_text(full_text))
        if remaining is not None:
            child_texts = child_texts[:remaining]

        if not child_texts:
            document.chunk_count = 0
            db.flush()
            return 0, 0

        vectors = texts_to_vectors(child_texts)
        total_tokens += _count_tokens(embed_model, child_texts)

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

        if chunk_rows:
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
            # child 제한 도달 시 종료
            if remaining is not None and remaining <= 0:
                break

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
                    chunk_text=parent_text.strip(),
                ),
                vector=None,
            )

            # -------------------------
            # 3-2) child chunks
            # -------------------------
            child_texts = _clean_texts(child_splitter.split_text(parent_text))
            if not child_texts:
                continue

            if remaining is not None:
                child_texts = child_texts[:remaining]

            if not child_texts:
                continue

            vectors = texts_to_vectors(child_texts)
            total_tokens += _count_tokens(embed_model, child_texts)

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
                if remaining is not None:
                    remaining -= 1
                    if remaining <= 0:
                        break

        if chunk_rows:
            document_chunk_crud.bulk_create(db, chunk_rows)

    # -----------------------------------------------------
    # 4) 문서 통계 업데이트
    # -----------------------------------------------------
    document.chunk_count = total_child_count
    db.flush()

    return total_child_count, total_tokens
