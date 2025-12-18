# service/user/upload_pipeline.py
import os
import shutil
from uuid import uuid4
from typing import List, Optional, Tuple, Any, Dict
from datetime import datetime, timezone
import logging

from fastapi import UploadFile
from sqlalchemy.orm import Session

from models.user.document import Document
from crud.user import document as doc_crud
from schemas.user.document import (
    DocumentCreate,
    DocumentUpdate,
    DocumentPageCreate,
    DocumentChunkCreate,
)
import crud.supervisor.api_usage as cost
from core import config
from core.pricing import (
    tokens_for_texts,
    normalize_usage_embedding,
    estimate_embedding_cost_usd,
)

from langchain_community.document_loaders import PyMuPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

from langchain_service.embedding.get_vector import texts_to_vectors

log = logging.getLogger("api_cost")

# 프리뷰 LLM 사용 여부(현재는 안 쓰지만 남겨둠)
_USE_LLM_PREVIEW = getattr(config, "USE_LLM_PREVIEW", False)
if _USE_LLM_PREVIEW:
    from langchain_service.prompt.prompt import pdf_preview_prompt  # type: ignore


# 정합성 고정(벡터 컬럼 차원과 동일)
_EMBEDDING_DIM_FIXED = 1536
_SCORE_TYPE_FIXED = "cosine_similarity"


def _tok_len(s: str) -> int:
    model = getattr(config, "DEFAULT_EMBEDDING_MODEL", "text-embedding-3-small")
    return tokens_for_texts(model, [s])


def _merge_defaults(defaults: Dict[str, Any], override: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    shallow merge + extra는 dict merge
    """
    merged = dict(defaults)
    if not override:
        return merged

    # extra만 병합
    extra = merged.get("extra") or {}
    if "extra" in override and isinstance(override["extra"], dict):
        extra = {**extra, **override["extra"]}

    merged.update({k: v for k, v in override.items() if k != "extra"})
    merged["extra"] = extra
    return merged


def _validate_ingestion_payload(p: Dict[str, Any]) -> None:
    # 최소 sanity check (나머진 schema/DB가 막음)
    if int(p["chunk_size"]) < 1:
        raise ValueError("chunk_size must be >= 1")
    if int(p["chunk_overlap"]) < 0:
        raise ValueError("chunk_overlap must be >= 0")
    if int(p["chunk_overlap"]) >= int(p["chunk_size"]):
        raise ValueError("chunk_overlap must be < chunk_size")
    if int(p["max_chunks"]) < 1:
        raise ValueError("max_chunks must be >= 1")

    # 1536 only
    if int(p.get("embedding_dim", _EMBEDDING_DIM_FIXED)) != _EMBEDDING_DIM_FIXED:
        raise ValueError("embedding_dim must be 1536")

    # MVP 고정(현재 texts_to_vectors 경로와 정합성)
    if p.get("embedding_provider") not in (None, "openai"):
        raise ValueError("embedding_provider must be 'openai'")
    if p.get("embedding_model") not in (None, getattr(config, "DEFAULT_EMBEDDING_MODEL", "text-embedding-3-small")):
        raise ValueError("embedding_model must match DEFAULT_EMBEDDING_MODEL")


def _validate_search_payload(p: Dict[str, Any]) -> None:
    if int(p["top_k"]) < 1:
        raise ValueError("top_k must be >= 1")

    # 유사도(min_score) 기준
    ms = float(p["min_score"])
    if ms < 0.0 or ms > 1.0:
        raise ValueError("min_score must be between 0 and 1")

    # 고정(혼용 금지)
    if p.get("score_type") != _SCORE_TYPE_FIXED:
        raise ValueError("score_type must be cosine_similarity")

    if int(p["reranker_top_n"]) < 1:
        raise ValueError("reranker_top_n must be >= 1")
    if int(p["reranker_top_n"]) > int(p["top_k"]):
        raise ValueError("reranker_top_n must be <= top_k")


class UploadPipeline:
    """
    1) init_document(file, ingestion_override?, search_override?):
       - 파일 저장
       - Document row 생성
       - DocumentIngestionSetting / DocumentSearchSetting 기본 row 2개 생성(override 반영)
       - 여기까지는 요청 핸들러에서 실행(트랜잭션 안)

    2) process_document(knowledge_id):
       - ingestion 설정 조회 후 chunking/embedding에 적용
       - 텍스트 추출 → 페이지 저장 → 청크 생성 → 임베딩 저장
    """

    def __init__(self, db: Session, user_id: int):
        self.db = db
        self.user_id = int(user_id)
        self.folder_rel = os.path.join(str(self.user_id), "document")
        self.base_dir = getattr(config, "UPLOAD_FOLDER", "./uploads")

        self.max_file_size_bytes: int = getattr(
            config,
            "DOCUMENT_MAX_SIZE_BYTES",
            10 * 1024 * 1024,
        )

    # ---------------------------
    # 공용 유틸
    # ---------------------------
    def _save_file(self, file: UploadFile) -> tuple[str, str]:
        """
        파일을 디스크에 저장하고 (절대경로, 파일명) 반환
        """
        user_dir = os.path.join(self.base_dir, self.folder_rel)
        os.makedirs(user_dir, exist_ok=True)

        origin = file.filename or "uploaded.pdf"
        fname = f"{self.user_id}_{uuid4().hex[:8]}_{origin}"
        fpath = os.path.join(user_dir, fname)

        file.file.seek(0)
        with open(fpath, "wb") as f:
            shutil.copyfileobj(file.file, f, length=1024 * 1024)  # 1MB 버퍼

        return fpath, fname

    def _load_docs(self, file_path: str):
        return PyMuPDFLoader(file_path).load()

    def extract_text(self, file_path: str) -> Tuple[str, int]:
        docs = self._load_docs(file_path)
        text = "\n".join(
            d.page_content for d in docs if getattr(d, "page_content", "")
        ).strip()
        return text, len(docs)

    def chunk_text(
        self,
        text: str,
        *,
        chunk_size: int,
        chunk_overlap: int,
        max_chunks: int,
        chunk_strategy: str,
    ) -> List[str]:
        """
        ingestion 설정 적용
        - chunk_strategy는 recursive만 지원(우선은 과확장 방지)
        """
        if chunk_strategy != "recursive":
            raise ValueError("Only chunk_strategy='recursive' is supported in MVP")

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=_tok_len,
            separators=["\n\n", "\n", " ", ""],
        )
        chunks = splitter.split_text(text)
        if max_chunks and len(chunks) > max_chunks:
            chunks = chunks[:max_chunks]
        return chunks

    def embed_chunks(self, chunks: List[str]) -> Tuple[List[str], List[List[float]]]:
        """
        청크 리스트를 임베딩한다.
        - 빈/공백 청크 제거
        - texts_to_vectors() 사용
        """
        cleaned = [c for c in chunks if c and c.strip()]
        if not cleaned:
            return [], []

        vectors: List[List[float]] = texts_to_vectors(cleaned)
        return cleaned, vectors

    def store_pages(
        self,
        knowledge_id: int,
        num_pages: int,
        image_urls: Optional[List[str]] = None,
    ):
        pages: List[DocumentPageCreate] = []
        for i in range(1, num_pages + 1):
            img = (
                image_urls[i - 1]
                if image_urls and (i - 1) < len(image_urls)
                else None
            )
            pages.append(
                DocumentPageCreate(
                    knowledge_id=knowledge_id,
                    page_no=i,
                    image_url=img,
                )
            )
        if pages:
            doc_crud.document_page_crud.bulk_create(self.db, pages)

    def store_chunks(
        self,
        knowledge_id: int,
        chunks: List[str],
        vectors: List[List[float]],
    ):
        if not chunks or not vectors:
            return

        items: List[tuple[DocumentChunkCreate, List[float]]] = []
        for idx, (txt, vec) in enumerate(zip(chunks, vectors), start=1):
            schema = DocumentChunkCreate(
                knowledge_id=knowledge_id,
                page_id=None,
                chunk_index=idx,
                chunk_text=txt,
            )
            items.append((schema, vec))

        doc_crud.document_chunk_crud.bulk_create(self.db, items)

        # chunk_count 갱신 (commit은 호출하는 쪽에서)
        update_in = DocumentUpdate(chunk_count=len(chunks))
        doc_crud.document_crud.update(self.db, knowledge_id=knowledge_id, data=update_in)

    # Document.progress / status / error_message 갱신 헬퍼
    def _update_document(
        self,
        knowledge_id: int,
        *,
        status: Optional[str] = None,
        progress: Optional[int] = None,
        error_message: Optional[str] = None,
    ):
        payload = {}
        if status is not None:
            payload["status"] = status
        if progress is not None:
            payload["progress"] = progress
        if error_message is not None:
            payload["error_message"] = error_message

        if not payload:
            return

        update_in = DocumentUpdate(**payload)
        doc_crud.document_crud.update(self.db, knowledge_id=knowledge_id, data=update_in)
        self.db.commit()

    # ---------------------------
    # 1) 요청 시 바로 실행되는 부분
    # ---------------------------
    def init_document(
        self,
        file: UploadFile,
        *,
        ingestion_override: Optional[Dict[str, Any]] = None,
        search_override: Optional[Dict[str, Any]] = None,
    ) -> Document:
        """
        - 파일 저장
        - Document row 생성
        - settings row 2개를 문서 생성 직후 무조건 생성/보장(override 반영)
        """
        fpath, fname = self._save_file(file)
        file_size_bytes = os.path.getsize(fpath)
        file_format = file.content_type or "application/octet-stream"

        doc_in = DocumentCreate(
            owner_id=self.user_id,
            name=fname,
            file_format=file_format,
            file_size_bytes=file_size_bytes,
            folder_path=self.folder_rel,
            status="uploading",
            chunk_count=0,
            progress=0,
            error_message=None,
        )
        doc = doc_crud.document_crud.create(self.db, doc_in)
        self.db.flush()
        self.db.refresh(doc)

        # defaults + override 병합
        base_ing = dict(getattr(config, "DEFAULT_INGESTION"))
        base_sea = dict(getattr(config, "DEFAULT_SEARCH"))

        # 고정값 강제(혼용/정합성 방지)
        base_ing["embedding_dim"] = _EMBEDDING_DIM_FIXED
        base_sea["score_type"] = _SCORE_TYPE_FIXED

        ing_payload = _merge_defaults(base_ing, ingestion_override)
        sea_payload = _merge_defaults(base_sea, search_override)

        # 다시 한 번 고정값 덮어쓰기(override로 바뀌는 거 방지)
        ing_payload["embedding_dim"] = _EMBEDDING_DIM_FIXED
        sea_payload["score_type"] = _SCORE_TYPE_FIXED

        _validate_ingestion_payload(ing_payload)
        _validate_search_payload(sea_payload)

        # 문서 생성 직후 settings 2row 보장 (UPSERT do nothing)
        doc_crud.document_ingestion_setting_crud.ensure_default(
            self.db,
            knowledge_id=doc.knowledge_id,
            defaults=ing_payload,
        )
        doc_crud.document_search_setting_crud.ensure_default(
            self.db,
            knowledge_id=doc.knowledge_id,
            defaults=sea_payload,
        )

        # commit은 엔드포인트에서 한 번에 해도 되고,
        # 여기서 해도 됨. (현재 코드 스타일 유지: 바깥에서 commit 가능)
        self.db.flush()
        return doc

    # ---------------------------
    # 2) 백그라운드에서 돌릴 무거운 처리
    # ---------------------------
    def process_document(self, knowledge_id: int) -> None:
        """
        ingestion 설정을 읽어서 chunking/embedding에 적용
        """
        doc = doc_crud.document_crud.get(self.db, knowledge_id)
        if not doc:
            return

        # 파일 경로 복원
        folder_path = doc.folder_path or self.folder_rel
        file_path = os.path.join(self.base_dir, folder_path, doc.name)

        try:
            # 0) ingestion 설정 조회(없으면 기본값으로 ensure)
            ing = doc_crud.document_ingestion_setting_crud.get(self.db, knowledge_id)
            if ing is None:
                base_ing = dict(getattr(config, "DEFAULT_INGESTION"))
                base_ing["embedding_dim"] = _EMBEDDING_DIM_FIXED
                _validate_ingestion_payload(base_ing)
                ing = doc_crud.document_ingestion_setting_crud.ensure_default(
                    self.db,
                    knowledge_id=knowledge_id,
                    defaults=base_ing,
                )

            # 정합성 체크 (vector_memory=1536이므로 여기서도 막아줌)
            if int(getattr(ing, "embedding_dim", 0)) != _EMBEDDING_DIM_FIXED:
                raise ValueError("Invalid embedding_dim: must be 1536")
            if getattr(ing, "embedding_provider", "openai") != "openai":
                raise ValueError("Invalid embedding_provider: only openai is supported in MVP")
            if getattr(ing, "embedding_model", None) != getattr(config, "DEFAULT_EMBEDDING_MODEL", "text-embedding-3-small"):
                raise ValueError("Invalid embedding_model: must match DEFAULT_EMBEDDING_MODEL in MVP")

            # 1) 상태: embedding 시작
            self._update_document(
                knowledge_id,
                status="embedding",
                progress=5,
                error_message=None,
            )

            # 2) 텍스트 추출
            text, num_pages = self.extract_text(file_path)
            self._update_document(
                knowledge_id,
                progress=15,
            )

            # 3) 페이지 저장
            self.store_pages(knowledge_id, num_pages)
            self.db.commit()
            self._update_document(
                knowledge_id,
                progress=30,
            )

            # 4) 청크 생성 (설정 적용)
            chunks = self.chunk_text(
                text,
                chunk_size=int(ing.chunk_size),
                chunk_overlap=int(ing.chunk_overlap),
                max_chunks=int(ing.max_chunks),
                chunk_strategy=str(ing.chunk_strategy),
            )
            self._update_document(
                knowledge_id,
                progress=45,
            )

            # 5) 임베딩 계산
            chunks, vectors = self.embed_chunks(chunks)
            if vectors:
                self._update_document(
                    knowledge_id,
                    progress=70,
                )

                # 6) 청크 + 벡터 저장
                self.store_chunks(knowledge_id, chunks, vectors)

                # ==== 비용 집계: 임베딩 ====
                try:
                    total_tokens = sum(_tok_len(c or "") for c in chunks)
                    usage = normalize_usage_embedding(total_tokens)
                    usd = estimate_embedding_cost_usd(
                        model=getattr(config, "DEFAULT_EMBEDDING_MODEL", "text-embedding-3-small"),
                        total_tokens=usage["embedding_tokens"],
                    )
                    log.info(
                        "api-cost: will record embedding tokens=%d usd=%s",
                        usage["embedding_tokens"],
                        usd,
                    )
                    cost.add_event(
                        self.db,
                        ts_utc=datetime.now(timezone.utc),
                        product="embedding",
                        model=getattr(config, "DEFAULT_EMBEDDING_MODEL", "text-embedding-3-small"),
                        llm_tokens=0,
                        embedding_tokens=usage["embedding_tokens"],
                        audio_seconds=0,
                        cost_usd=usd,
                    )
                    self.db.commit()
                    log.info(
                        "api-cost: recorded embedding tokens=%d usd=%s",
                        usage["embedding_tokens"],
                        usd,
                    )
                except Exception as e:
                    log.exception("api-cost embedding record failed: %s", e)

            # 7) 완료
            self._update_document(
                knowledge_id,
                status="ready",
                progress=100,
            )

        except Exception as e:
            # 실패 시 상태/에러메시지 기록
            try:
                self._update_document(
                    knowledge_id,
                    status="failed",
                    error_message=str(e),
                )
            except Exception:
                pass
            raise
