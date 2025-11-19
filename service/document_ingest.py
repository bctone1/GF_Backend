# service/document_ingest.py
from __future__ import annotations

import os
import shutil
import logging
from uuid import uuid4
from typing import List, Optional, Tuple
from datetime import datetime, timezone

from fastapi import UploadFile
from sqlalchemy.orm import Session

from langchain_community.document_loaders import PyMuPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

import core.config as config
from core.pricing import (
    tokens_for_texts,           # tiktoken 기반 토큰 계산
    normalize_usage_embedding,
    estimate_embedding_cost_usd,
)

from langchain_service.embedding.get_vector import texts_to_vectors

from crud.user.document import (
    document_crud,
    document_job_crud,
    document_page_crud,
    document_chunk_crud,
)
from schemas.user.document import (
    DocumentCreate,
    DocumentUpdate,
    DocumentProcessingJobCreate,
    DocumentProcessingJobUpdate,
    DocumentPageCreate,
)

from crud.supervisor import api_usage


log = logging.getLogger("api_cost")


def _tok_len(s: str) -> int:
    """
    임베딩 토큰 계산용 길이 함수.
    langchain_text_splitters 의 length_function 에 넘겨서
    '토큰 기준 chunk_size' 로 자르도록 사용.
    """
    model = getattr(config, "DEFAULT_EMBEDDING_MODEL", "text-embedding-3-small")
    return tokens_for_texts(model, [s])


class DocumentIngestService:
    """
    GF용 문서 인제스트 파이프라인

    [한 번에 하는 일]
    1) 파일 저장
    2) PDF 파싱 → 전체 텍스트 + 페이지 수
    3) user.documents 메타 생성 (status='processing')
    4) user.document_pages 생성 (page_no만 기록, text는 chunk 기준으로 관리)
    5) 텍스트 chunk 분할
    6) 임베딩 생성(OpenAI, texts_to_vectors)
    7) user.document_chunks 저장 + vector_memory 저장
    8) 토큰/비용 집계 (api_cost 로그)
    9) document.status = 'active', chunk_count 업데이트
       실패 시 'error'

    DocumentProcessingJob(stage='parse'/'embed') 도 함께 기록.
    """

    def __init__(self, db: Session, owner_id: int):
        self.db = db
        self.owner_id = owner_id
        self.file_path: Optional[str] = None
        self.knowledge_id: Optional[int] = None

    # -----------------------
    # 1) 파일 저장
    # -----------------------
    def save_file(self, file: UploadFile) -> str:
        base_dir = config.UPLOAD_FOLDER
        user_dir = os.path.join(base_dir, str(self.owner_id), "documents")
        os.makedirs(user_dir, exist_ok=True)

        origin = file.filename or "uploaded"
        fname = f"{self.owner_id}_{uuid4().hex[:8]}_{origin}"
        fpath = os.path.join(user_dir, fname)

        file.file.seek(0)
        with open(fpath, "wb") as f:
            shutil.copyfileobj(file.file, f, length=1024 * 1024)  # 1MB 버퍼

        self.file_path = fpath
        return fpath

    # -----------------------
    # 2) 문서 로딩 / 텍스트 추출
    # -----------------------
    def _load_docs(self, file_path: str):
        """
        현재는 PDF(PyMuPDFLoader)만 지원.
        필요 시 파일 확장자에 따라 분기 추가 가능.
        """
        return PyMuPDFLoader(file_path).load()

    def extract_text(self, file_path: str) -> Tuple[str, int]:
        docs = self._load_docs(file_path)
        text = "\n".join(
            d.page_content for d in docs if getattr(d, "page_content", "")
        ).strip()
        num_pages = len(docs)
        return text, num_pages

    # -----------------------
    # 3) Document 메타 생성
    # -----------------------
    def create_document(self, file: UploadFile) -> int:
        file_size = os.path.getsize(self.file_path or "")
        name = file.filename or "uploaded"
        ext = (name.rsplit(".", 1)[-1] if "." in name else "").lower() or "bin"

        doc = document_crud.create(
            self.db,
            DocumentCreate(
                owner_id=self.owner_id,
                name=name,
                file_format=ext,
                file_size_bytes=file_size,
                folder_path=None,         # UI 상 가상 폴더가 생기면 거기서 세팅
                status="processing",
                chunk_count=0,
            ),
        )
        self.knowledge_id = doc.knowledge_id
        return doc.knowledge_id

    # -----------------------
    # 4) 페이지 저장
    # -----------------------
    def store_pages(
        self,
        knowledge_id: int,
        num_pages: int,
        image_urls: Optional[List[str]] = None,
    ) -> None:
        """
        현재는 page_no와 image_url만 저장.
        페이지별 텍스트는 chunk 레벨에서 관리.
        """
        pages: List[DocumentPageCreate] = []
        for i in range(1, num_pages + 1):
            image_url = (
                image_urls[i - 1]
                if image_urls and i - 1 < len(image_urls)
                else None
            )
            pages.append(
                DocumentPageCreate(
                    knowledge_id=knowledge_id,
                    page_no=i,
                    image_url=image_url,
                )
            )
        document_page_crud.bulk_create(self.db, pages)

    # -----------------------
    # 5) 텍스트 chunk 분할
    # -----------------------
    def chunk_text(self, text: str) -> List[str]:
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=900,
            chunk_overlap=150,
            length_function=_tok_len,
            separators=["\n\n", "\n", " ", ""],
        )
        return splitter.split_text(text)

    # -----------------------
    # 6) 임베딩 생성
    # -----------------------
    def embed_chunks(
        self,
        chunks: List[str],
    ) -> Tuple[List[str], List[List[float]]]:
        cleaned = [c for c in chunks if c and c.strip()]
        if not cleaned:
            return [], []
        vectors = texts_to_vectors(cleaned)  # OpenAI 기반 batch 임베딩
        return cleaned, vectors

    # -----------------------
    # 7) 청크 저장
    # -----------------------
    def store_chunks(
        self,
        knowledge_id: int,
        chunks: List[str],
        vectors: List[List[float]],
    ) -> None:
        """
        현재는 page_id 매핑 없이 저장.
        (추후 page_no → page_id 매핑 로직을 추가하면 page_id도 채울 수 있음.)
        """
        # DocumentChunkCRUD.bulk_create 는 DocumentChunk 인스턴스를 받도록 설계해둔 상태라면
        # 여기서 models.user.document.DocumentChunk 를 직접 생성해도 되고,
        # 단건 insert 루프를 돌려도 된다. 우선은 단순 루프로 처리.
        from models.user.document import DocumentChunk  # 지연 import

        chunk_models: List[DocumentChunk] = []
        for idx, (text, vec) in enumerate(zip(chunks, vectors), start=1):
            chunk_models.append(
                DocumentChunk(
                    knowledge_id=knowledge_id,
                    page_id=None,          # page 매핑 필요 시 추후 확장
                    chunk_index=idx,
                    chunk_text=text,
                    vector_memory=vec,     # pgvector에 그대로 들어감
                )
            )

        document_chunk_crud.bulk_create(self.db, chunk_models)

    # -----------------------
    # 8) Document 상태 / chunk_count / cost 업데이트
    # -----------------------
    def _set_document_status(
        self,
        knowledge_id: int,
        status: str,
        chunk_count: Optional[int] = None,
    ) -> None:
        data = {"status": status}
        if chunk_count is not None:
            data["chunk_count"] = chunk_count
        document_crud.update(
            self.db,
            knowledge_id=knowledge_id,
            data=DocumentUpdate(**data),
        )

    def _record_embedding_cost(self, chunks: List[str]) -> None:
        try:
            model = getattr(
                config,
                "DEFAULT_EMBEDDING_MODEL",
                "text-embedding-3-small",
            )
            total_tokens = sum(_tok_len(c or "") for c in chunks)
            usage = normalize_usage_embedding(total_tokens)
            usd = estimate_embedding_cost_usd(
                model=model,
                total_tokens=usage["embedding_tokens"],
            )
            log.info(
                "api-cost: will record embedding tokens=%d usd=%s",
                usage["embedding_tokens"],
                usd,
            )
            api_usage.add_event(
                self.db,
                ts_utc=datetime.now(timezone.utc),
                product="embedding",
                model=model,
                llm_tokens=0,
                embedding_tokens=usage["embedding_tokens"],
                audio_seconds=0,
                cost_usd=usd,
            )
            log.info(
                "api-cost: recorded embedding tokens=%d usd=%s",
                usage["embedding_tokens"],
                usd,
            )
        except Exception as e:
            log.exception("api-cost embedding record failed: %s", e)

    # -----------------------
    # 9) DocumentProcessingJob 헬퍼
    # -----------------------
    def _create_job(self, knowledge_id: int, stage: str) -> int:
        job = document_job_crud.create(
            self.db,
            DocumentProcessingJobCreate(
                knowledge_id=knowledge_id,
                stage=stage,
                status="queued",
            ),
        )
        return job.job_id

    def _update_job(
        self,
        job_id: int,
        *,
        status: str,
        message: Optional[str] = None,
    ) -> None:
        document_job_crud.update(
            self.db,
            job_id=job_id,
            data=DocumentProcessingJobUpdate(
                status=status,
                message=message,
                completed_at=(
                    datetime.now(timezone.utc)
                    if status in ("completed", "failed")
                    else None
                ),
            ),
        )

    # -----------------------
    # 메인 엔트리: 전체 파이프라인 실행
    # -----------------------
    def run(self, file: UploadFile):
        """
        업로드된 파일 1개에 대해
        전체 인제스트 파이프라인을 실행하고 Document 객체를 반환.
        """
        document = None
        parse_job_id: Optional[int] = None
        embed_job_id: Optional[int] = None

        try:
            # 1) 파일 저장
            path = self.save_file(file)

            # 2) 문서 메타 생성(user.documents)
            doc_id = self.create_document(file)

            # 3) stage=parse
            parse_job_id = self._create_job(doc_id, stage="parse")

            # 4) 텍스트/페이지 추출
            text, num_pages = self.extract_text(path)

            # 5) 페이지 저장
            self.store_pages(doc_id, num_pages=num_pages)

            # parse 완료
            self._update_job(parse_job_id, status="completed")

            # 6) stage=embed
            embed_job_id = self._create_job(doc_id, stage="embed")

            # 7) chunk 분할
            chunks = self.chunk_text(text)

            # 8) 임베딩
            chunks, vectors = self.embed_chunks(chunks)
            if vectors:
                # 9) 청크+벡터 저장
                self.store_chunks(doc_id, chunks, vectors)

                # 10) 비용 기록
                self._record_embedding_cost(chunks)

            # embed 완료
            self._update_job(embed_job_id, status="completed")

            # 11) Document 상태/청크수 업데이트
            self._set_document_status(
                doc_id,
                status="active",
                chunk_count=len(chunks),
            )

            document = document_crud.get(self.db, knowledge_id=doc_id)
            return document

        except Exception as e:
            log.exception("Document ingest failed: %s", e)
            # 실패 시 상태 error 처리
            if self.knowledge_id:
                try:
                    self._set_document_status(
                        self.knowledge_id,
                        status="error",
                    )
                except Exception:
                    pass
            if parse_job_id is not None:
                self._update_job(
                    parse_job_id,
                    status="failed",
                    message=str(e),
                )
            if embed_job_id is not None:
                self._update_job(
                    embed_job_id,
                    status="failed",
                    message=str(e),
                )
            raise
