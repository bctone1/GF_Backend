# service/user/upload_pipeline.py
from __future__ import annotations

import os
import shutil
import logging
from uuid import uuid4
from typing import Optional, Tuple, Any, Dict
from datetime import datetime, timezone

from fastapi import UploadFile
from sqlalchemy.orm import Session

from core import config
from core.pricing import (
    tokens_for_texts,
    normalize_usage_embedding,
    estimate_embedding_cost_usd,
)

from models.user.document import Document
from schemas.user.document import (
    DocumentCreate,
    DocumentUpdate,
    DocumentPageCreate,
)

from crud.user import document as doc_crud
import crud.supervisor.api_usage as cost

from langchain_community.document_loaders import PyMuPDFLoader

from service.user.document_ingest import ingest_document_text

log = logging.getLogger("api_cost")

# =========================================================
# Constants (정합성 고정)
# =========================================================
_EMBEDDING_DIM_FIXED = 1536
_SCORE_TYPE_FIXED = "cosine_similarity"


# =========================================================
# Helpers
# =========================================================
def _tok_len(s: str) -> int:
    model = getattr(config, "DEFAULT_EMBEDDING_MODEL", "text-embedding-3-small")
    return tokens_for_texts(model, [s])


def _merge_defaults(defaults: Dict[str, Any], override: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    shallow merge
    - extra 는 dict merge
    """
    merged = dict(defaults)
    if not override:
        return merged

    extra = merged.get("extra") or {}
    if isinstance(override.get("extra"), dict):
        extra = {**extra, **override["extra"]}

    merged.update({k: v for k, v in override.items() if k != "extra"})
    merged["extra"] = extra
    return merged


def _validate_ingestion_payload(p: Dict[str, Any]) -> None:
    if int(p["chunk_size"]) < 1:
        raise ValueError("chunk_size must be >= 1")
    if int(p["chunk_overlap"]) < 0:
        raise ValueError("chunk_overlap must be >= 0")
    if int(p["chunk_overlap"]) >= int(p["chunk_size"]):
        raise ValueError("chunk_overlap must be < chunk_size")
    if int(p["max_chunks"]) < 1:
        raise ValueError("max_chunks must be >= 1")

    if int(p.get("embedding_dim", _EMBEDDING_DIM_FIXED)) != _EMBEDDING_DIM_FIXED:
        raise ValueError("embedding_dim must be 1536")

    if p.get("embedding_provider") not in (None, "openai"):
        raise ValueError("embedding_provider must be 'openai'")
    if p.get("embedding_model") not in (
        None,
        getattr(config, "DEFAULT_EMBEDDING_MODEL", "text-embedding-3-small"),
    ):
        raise ValueError("embedding_model must match DEFAULT_EMBEDDING_MODEL")


def _validate_search_payload(p: Dict[str, Any]) -> None:
    if int(p["top_k"]) < 1:
        raise ValueError("top_k must be >= 1")

    ms = float(p["min_score"])
    if ms < 0.0 or ms > 1.0:
        raise ValueError("min_score must be between 0 and 1")

    if p.get("score_type") != _SCORE_TYPE_FIXED:
        raise ValueError("score_type must be cosine_similarity")

    if int(p["reranker_top_n"]) < 1:
        raise ValueError("reranker_top_n must be >= 1")
    if int(p["reranker_top_n"]) > int(p["top_k"]):
        raise ValueError("reranker_top_n must be <= top_k")


# =========================================================
# UploadPipeline
# =========================================================
class UploadPipeline:
    """
    역할 분리 원칙(통일안):
    - UploadPipeline
      * 파일 저장
      * 텍스트 추출
      * 페이지 저장
      * 상태 업데이트 / 비용 집계
      * chunking/embedding/store_chunks 는 ingest service로 위임

    - document_ingest.ingest_document_text
      * general / parent_child chunking
      * child embedding
      * chunk 저장 + chunk_count 갱신
    """

    def __init__(self, db: Session, user_id: int):
        self.db = db
        self.user_id = int(user_id)
        self.folder_rel = os.path.join(str(self.user_id), "document")
        self.base_dir = getattr(config, "UPLOAD_FOLDER", "./uploads")

    # -----------------------------------------------------
    # File / Text
    # -----------------------------------------------------
    def _save_file(self, file: UploadFile) -> tuple[str, str]:
        user_dir = os.path.join(self.base_dir, self.folder_rel)
        os.makedirs(user_dir, exist_ok=True)

        origin = file.filename or "uploaded.pdf"
        fname = f"{self.user_id}_{uuid4().hex[:8]}_{origin}"
        fpath = os.path.join(user_dir, fname)

        file.file.seek(0)
        with open(fpath, "wb") as f:
            shutil.copyfileobj(file.file, f, length=1024 * 1024)

        return fpath, fname

    def extract_text(self, file_path: str) -> Tuple[str, int]:
        ext = os.path.splitext(file_path)[1].lower()

        if ext in (".md", ".txt"):
            with open(file_path, "r", encoding="utf-8") as f:
                text = f.read().strip()
            # 텍스트 파일은 페이지 개념이 없으므로 1로 고정
            return text, 1

        # PDF (default)
        docs = PyMuPDFLoader(file_path).load()
        text = "\n".join(d.page_content for d in docs if getattr(d, "page_content", "")).strip()
        return text, len(docs)

    # -----------------------------------------------------
    # Store
    # -----------------------------------------------------
    def store_pages(self, knowledge_id: int, num_pages: int):
        # 재처리 시 중복 방지(있으면 삭제)
        deleter = getattr(doc_crud.document_page_crud, "delete_by_document", None)
        if callable(deleter):
            deleter(self.db, knowledge_id)

        pages = [
            DocumentPageCreate(
                knowledge_id=knowledge_id,
                page_no=i,
            )
            for i in range(1, num_pages + 1)
        ]
        if pages:
            doc_crud.document_page_crud.bulk_create(self.db, pages)

    # -----------------------------------------------------
    # Init (sync)
    # -----------------------------------------------------
    def init_document(
        self,
        file: UploadFile,
        *,
        ingestion_override: Optional[Dict[str, Any]] = None,
        search_override: Optional[Dict[str, Any]] = None,
        scope: str = "knowledge_base",
        session_id: Optional[int] = None,
    ) -> Document:
        fpath, fname = self._save_file(file)

        doc = doc_crud.document_crud.create(
            self.db,
            DocumentCreate(
                owner_id=self.user_id,
                name=fname,
                file_format=file.content_type or "application/octet-stream",
                file_size_bytes=os.path.getsize(fpath),
                folder_path=self.folder_rel,
                status="uploading",
                chunk_count=0,
                progress=0,
                scope=scope,
                session_id=session_id,
            ),
        )
        self.db.flush()
        self.db.refresh(doc)

        base_ing = dict(getattr(config, "DEFAULT_INGESTION"))
        base_sea = dict(getattr(config, "DEFAULT_SEARCH"))

        base_ing["embedding_dim"] = _EMBEDDING_DIM_FIXED
        base_sea["score_type"] = _SCORE_TYPE_FIXED

        ing = _merge_defaults(base_ing, ingestion_override)
        sea = _merge_defaults(base_sea, search_override)

        ing["embedding_dim"] = _EMBEDDING_DIM_FIXED
        sea["score_type"] = _SCORE_TYPE_FIXED

        _validate_ingestion_payload(ing)
        _validate_search_payload(sea)

        doc_crud.document_ingestion_setting_crud.ensure_default(
            self.db, knowledge_id=doc.knowledge_id, defaults=ing
        )
        doc_crud.document_search_setting_crud.ensure_default(
            self.db, knowledge_id=doc.knowledge_id, defaults=sea
        )

        self.db.flush()
        return doc

    # -----------------------------------------------------
    # Process (background)
    # -----------------------------------------------------
    def process_document(self, knowledge_id: int) -> None:
        doc = doc_crud.document_crud.get(self.db, knowledge_id)
        if not doc:
            return

        file_path = os.path.join(
            self.base_dir,
            doc.folder_path or self.folder_rel,
            doc.name,
        )

        try:
            ing = doc_crud.document_ingestion_setting_crud.get(self.db, knowledge_id)
            if not ing:
                raise RuntimeError("ingestion setting not found")

            embed_model = getattr(ing, "embedding_model", None) or getattr(
                config, "DEFAULT_EMBEDDING_MODEL", "text-embedding-3-small"
            )

            # 1) 상태 업데이트
            doc_crud.document_crud.update(
                self.db,
                knowledge_id=knowledge_id,
                data=DocumentUpdate(status="embedding", progress=5),
            )
            self.db.commit()

            # 2) 텍스트 추출 + 페이지 저장
            text, num_pages = self.extract_text(file_path)
            self.store_pages(knowledge_id, num_pages)
            self.db.commit()

            # 3) chunking/embedding/store_chunks 위임
            #    - ingest_document_text는 child chunk들만 임베딩
            #    - (child_count, total_tokens) 리턴을 기대 (2번 파일에서 맞출 거야)
            child_count, total_tokens = ingest_document_text(
                self.db,
                document=doc,
                full_text=text,
            )
            self.db.commit()

            # 4) 비용 집계 (임베딩 토큰 기준)
            usage = normalize_usage_embedding(int(total_tokens))
            usd = estimate_embedding_cost_usd(
                model=embed_model,
                total_tokens=usage["embedding_tokens"],
            )
            cost.add_event(
                self.db,
                ts_utc=datetime.now(timezone.utc),
                product="embedding",
                model=embed_model,
                llm_tokens=0,
                embedding_tokens=usage["embedding_tokens"],
                audio_seconds=0,
                cost_usd=usd,
            )

            # 5) 완료
            doc_crud.document_crud.update(
                self.db,
                knowledge_id=knowledge_id,
                data=DocumentUpdate(status="ready", progress=100),
            )
            self.db.commit()

        except Exception as e:
            self.db.rollback()
            doc_crud.document_crud.update(
                self.db,
                knowledge_id=knowledge_id,
                data=DocumentUpdate(status="failed", error_message=str(e)),
            )
            self.db.commit()
            raise
