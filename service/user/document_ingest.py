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
from langchain_service.embedding.get_vector import texts_to_vectors

from service.user.document_chunking import (
    build_splitter,
    split_segments,
    clean_texts,
)

# =========================================================
# helpers
# =========================================================
def _count_tokens(model: str, texts: List[str]) -> int:
    if not texts:
        return 0
    return int(tokens_for_texts(model, texts))


def _tok_len_factory(model: str) -> Callable[[str], int]:
    def _tok_len(s: str) -> int:
        return _count_tokens(model, [s])

    return _tok_len


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

    chunking_mode = getattr(setting, "chunking_mode", "general")
    segment_separator = getattr(setting, "segment_separator", None)

    # parent_child인데 separator가 비어있으면 디폴트로 보강(레거시 row 방어)
    if chunking_mode == "parent_child" and not segment_separator:
        segment_separator = "\n\n"

    # child settings
    child_chunk_size = int(getattr(setting, "chunk_size", 800) or 800)
    child_chunk_overlap = int(getattr(setting, "chunk_overlap", 200) or 0)
    chunk_strategy = str(getattr(setting, "chunk_strategy", "recursive") or "recursive")
    max_chunks = int(getattr(setting, "max_chunks", 0) or 0)  # 0이면 제한 없음

    # parent settings (parent_child에서만 의미)
    parent_chunk_size_raw = getattr(setting, "parent_chunk_size", None)
    parent_chunk_overlap_raw = getattr(setting, "parent_chunk_overlap", None)

    parent_chunk_size = int(parent_chunk_size_raw) if parent_chunk_size_raw is not None else None
    parent_chunk_overlap = int(parent_chunk_overlap_raw) if parent_chunk_overlap_raw is not None else 0

    embed_model = (
        getattr(setting, "embedding_model", None)
        or getattr(config, "DEFAULT_EMBEDDING_MODEL", "text-embedding-3-small")
    )

    # -----------------------------------------------------
    # 0) 기존 청크 삭제 (reindex)
    # -----------------------------------------------------
    document_chunk_crud.delete_by_document(db, document.knowledge_id)

    if not full_text or not full_text.strip():
        document.chunk_count = 0
        db.flush()
        return 0, 0

    # -----------------------------------------------------
    # 1) splitter 준비
    # -----------------------------------------------------
    tok_len = _tok_len_factory(embed_model)

    child_splitter = build_splitter(
        chunk_size=child_chunk_size,
        chunk_overlap=child_chunk_overlap,
        strategy=chunk_strategy,
        length_function=tok_len,
    )

    parent_splitter = None
    if chunking_mode == "parent_child" and parent_chunk_size:
        parent_splitter = build_splitter(
            chunk_size=parent_chunk_size,
            chunk_overlap=parent_chunk_overlap,
            strategy=chunk_strategy,
            length_function=tok_len,
        )

    chunk_rows: list[tuple[DocumentChunkCreate, Optional[Sequence[float]]]] = []

    global_chunk_index = 1
    total_child_count = 0
    total_tokens = 0

    remaining = max_chunks if max_chunks > 0 else None  # child 기준 제한(None이면 무제한)

    # =====================================================
    # 2) GENERAL MODE
    # =====================================================
    if chunking_mode == "general":
        child_texts = clean_texts(child_splitter.split_text(full_text))
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
        segments = split_segments(text=full_text, separator=segment_separator)

        for seg_idx, segment_text in enumerate(segments, start=1):
            if remaining is not None and remaining <= 0:
                break

            # segment을 parent 단위로 추가 분할(옵션)
            if parent_splitter is not None:
                parent_texts = clean_texts(parent_splitter.split_text(segment_text))
            else:
                st = (segment_text or "").strip()
                parent_texts = [st] if st else []

            if not parent_texts:
                continue

            child_in_segment = 1  # segment 내 child 순번(여러 parent를 걸쳐 연속 증가)

            for parent_text in parent_texts:
                if remaining is not None and remaining <= 0:
                    break

                parent_text = (parent_text or "").strip()
                if not parent_text:
                    continue

                # child 먼저 만들어보고(없으면 parent row도 만들 필요 없음)
                child_texts = clean_texts(child_splitter.split_text(parent_text))
                if remaining is not None:
                    child_texts = child_texts[:remaining]

                if not child_texts:
                    continue

                # parent row 생성 (NO vector)
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

                # child embedding + rows
                vectors = texts_to_vectors(child_texts)
                total_tokens += _count_tokens(embed_model, child_texts)

                for text, vec in zip(child_texts, vectors):
                    chunk_rows.append(
                        (
                            DocumentChunkCreate(
                                knowledge_id=document.knowledge_id,
                                chunk_level="child",
                                parent_chunk_id=parent_row.chunk_id,
                                segment_index=seg_idx,
                                chunk_index_in_segment=child_in_segment,
                                chunk_index=global_chunk_index,
                                chunk_text=text,
                            ),
                            vec,
                        )
                    )
                    child_in_segment += 1
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
