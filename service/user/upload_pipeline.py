# service/user/upload_pipeline.py
import os
import shutil
from uuid import uuid4
from typing import List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor
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
    DocumentProcessingJobCreate,
    DocumentProcessingJobUpdate,
)
import crud.supervisor.api_usage as cost
from core import config
from core.pricing import (
    tokens_for_texts,               # tiktoken 기반 토큰 계산
    normalize_usage_embedding,
    estimate_embedding_cost_usd,
)

from langchain_community.document_loaders import PyMuPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

log = logging.getLogger("api_cost")

# 임베딩: 배치가 있으면 우선 사용, 없으면 단건 + 스레드풀
try:
    from langchain_service.embedding.get_vector import (
        text_to_vector,
        text_list_to_vectors,  # type: ignore
    )
    _HAS_BATCH = True
except Exception:
    from langchain_service.embedding.get_vector import text_to_vector  # type: ignore
    _HAS_BATCH = False

# 프리뷰 LLM 사용 여부(기본 비활성)
_USE_LLM_PREVIEW = getattr(config, "USE_LLM_PREVIEW", False)
if _USE_LLM_PREVIEW:
    from langchain_service.prompt.prompt import pdf_preview_prompt  # type: ignore


def _tok_len(s: str) -> int:
    model = getattr(config, "DEFAULT_EMBEDDING_MODEL", "text-embedding-3-small")
    return tokens_for_texts(model, [s])


class UploadPipeline:
    """
    파일 저장 → 텍스트 추출 → 프리뷰 → Document 메타 생성(status=uploading)
    → 페이지 저장(user.document_pages)
    → 청크 + 임베딩(user.document_chunks.vector_memory)
    → Document.chunk_count 갱신 + 상태(ready)
    실패 시 상태(failed)

    + DocumentProcessingJob 추가:
      - stage/status/progress/step 을 단계별로 갱신
    """

    def __init__(self, db: Session, user_id: int):
        self.db = db
        self.user_id = int(user_id)
        # 업로드 루트 기준 상대 폴더 (예: "123/document")
        self.folder_rel = os.path.join(str(self.user_id), "document")
        self.file_path: Optional[str] = None
        self.saved_file_name: Optional[str] = None
        self.document: Optional[Document] = None
        self.job_id: Optional[int] = None

    # ---------------------------
    # Job 헬퍼
    # ---------------------------
    def _create_job(self, knowledge_id: int) -> None:
        """
        DocumentProcessingJob row 생성 (초기 상태: queued, progress=0)
        """
        job_in = DocumentProcessingJobCreate(
            knowledge_id=knowledge_id,
            stage="queued",
            status="queued",
            progress=0,
            step=None,
            message=None,
            error_message=None,
            started_at=None,
            completed_at=None,
        )
        job = doc_crud.document_job_crud.create(self.db, job_in)
        self.job_id = job.job_id
        # 여기서는 commit 하지 않고, run() 내의 흐름에서 함께 commit

    def _update_job(self, **fields) -> None:
        """
        Job 상태/진행률 업데이트.
        - 존재하는 필드만 DocumentProcessingJobUpdate 로 생성
        """
        if not self.job_id:
            return

        data = DocumentProcessingJobUpdate(**fields)
        doc_crud.document_job_crud.update(self.db, job_id=self.job_id, data=data)
        # Job 상태 변경은 바로바로 프론트에 보이도록 commit
        self.db.commit()

    # 1) 파일 저장
    def save_file(self, file: UploadFile) -> str:
        base_dir = getattr(config, "UPLOAD_FOLDER", "./uploads")
        user_dir = os.path.join(base_dir, self.folder_rel)
        os.makedirs(user_dir, exist_ok=True)

        origin = file.filename or "uploaded.pdf"
        fname = f"{self.user_id}_{uuid4().hex[:8]}_{origin}"
        fpath = os.path.join(user_dir, fname)

        file.file.seek(0)
        with open(fpath, "wb") as f:
            shutil.copyfileobj(file.file, f, length=1024 * 1024)  # 1MB 버퍼

        self.file_path = fpath
        self.saved_file_name = fname
        return fpath

    # 2) 로더 1회
    def _load_docs(self, file_path: str):
        return PyMuPDFLoader(file_path).load()

    # 3) 텍스트 추출
    def extract_text(self, file_path: str) -> Tuple[str, int]:
        docs = self._load_docs(file_path)
        text = "\n".join(
            d.page_content for d in docs if getattr(d, "page_content", "")
        ).strip()
        return text, len(docs)

    # 4) 프리뷰 (현재는 DB에 저장할 컬럼이 없어서 파이프라인 내부에서만 사용)
    def _build_preview(self, text: str, max_chars: int = 400) -> str:
        if _USE_LLM_PREVIEW and self.file_path:
            try:
                prev_obj = pdf_preview_prompt(self.file_path)  # type: ignore
                if isinstance(prev_obj, dict):
                    p = prev_obj.get("preview", "")
                    if isinstance(p, list):
                        p = " ".join(p[:3])
                    return str(p)[:max_chars]
                return str(prev_obj)[:max_chars]
            except Exception:
                pass
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        head = " ".join(lines[:5])
        return head[:max_chars]

    # 5) Document 메타 생성 (user.documents)
    def create_metadata(self, file: UploadFile, preview: str) -> Document:
        if not self.file_path:
            raise RuntimeError("file_path is not set")

        file_size = os.path.getsize(self.file_path)
        name = self.saved_file_name or file.filename or "uploaded.pdf"
        file_format = file.content_type or "application/octet-stream"

        # 서버 처리 단계이므로 status='uploading' 으로 시작
        doc_in = DocumentCreate(
            owner_id=self.user_id,
            name=name,
            file_format=file_format,
            file_size_bytes=file_size,
            folder_path=self.folder_rel,
            status="uploading",
            chunk_count=0,
        )
        doc = doc_crud.document_crud.create(self.db, doc_in)
        self.document = doc
        return doc

    # 6) 페이지 저장 (user.document_pages)
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

    # 7) 청크 텍스트 생성
    def chunk_text(self, text: str) -> List[str]:
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=900,
            chunk_overlap=150,
            length_function=_tok_len,
            separators=["\n\n", "\n", " ", ""],
        )
        return splitter.split_text(text)

    # 8) 임베딩
    def embed_chunks(self, chunks: List[str]) -> Tuple[List[str], List[List[float]]]:
        cleaned = [c for c in chunks if c and c.strip()]
        if not cleaned:
            return [], []
        if _HAS_BATCH:
            vecs = text_list_to_vectors(cleaned)  # type: ignore
        else:
            vecs: List[List[float]] = []
            max_workers = min(4, (os.cpu_count() or 4))
            with ThreadPoolExecutor(max_workers=max_workers) as ex:
                for v in ex.map(text_to_vector, cleaned):
                    vecs.append(v)
        return cleaned, vecs

    # 9) 청크 + 벡터 저장 (user.document_chunks)
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

        # Document.chunk_count 갱신
        update_in = DocumentUpdate(chunk_count=len(chunks))
        doc_crud.document_crud.update(self.db, knowledge_id=knowledge_id, data=update_in)

    # 10) Document 상태 변경
    def _set_status(self, knowledge_id: int, status: str):
        try:
            update_in = DocumentUpdate(status=status)
            doc_crud.document_crud.update(self.db, knowledge_id=knowledge_id, data=update_in)
        except Exception:
            # 상태 변경 실패는 치명적이지 않으므로 무시
            pass

    # 전체 파이프라인 실행
    def run(self, file: UploadFile) -> Document:
        """
        최종적으로 user.documents 레코드(Document)를 반환
        (status, chunk_count 등은 커밋 후 최신 상태)
        """
        try:
            # 1) 파일 저장 (여기까지는 Document/Job 미생성 상태)
            path = self.save_file(file)

            # 2) 텍스트 추출
            text, num_pages = self.extract_text(path)

            # 3) 프리뷰 생성
            preview = self._build_preview(text)

            # 4) Document 메타 생성 (status='uploading')
            doc = self.create_metadata(file, preview)

            # 5) Job 생성 + parse 단계 시작
            self._create_job(doc.knowledge_id)
            self._update_job(
                stage="parse",
                status="uploading",
                progress=10,
                step="텍스트 추출 중",
                started_at=datetime.now(timezone.utc),
            )

            # 6) 페이지 저장
            self.store_pages(doc.knowledge_id, num_pages)
            self._update_job(
                stage="chunk",
                progress=30,
                step=f"페이지 {num_pages}개 저장 완료, 청크 생성 중",
            )

            # 7) 청크 생성
            chunks = self.chunk_text(text)
            self._update_job(
                stage="chunk",
                progress=40,
                step=f"청크 {len(chunks)}개 생성됨",
            )

            # 8) 임베딩
            chunks, vectors = self.embed_chunks(chunks)

            if vectors:
                self._update_job(
                    stage="embed",
                    progress=70,
                    step="임베딩 계산 완료, DB 저장 중",
                )

                self.store_chunks(doc.knowledge_id, chunks, vectors)

                # ==== 비용 집계: 임베딩 ====
                try:
                    total_tokens = sum(_tok_len(c or "") for c in chunks)
                    usage = normalize_usage_embedding(total_tokens)
                    usd = estimate_embedding_cost_usd(
                        model=getattr(
                            config,
                            "DEFAULT_EMBEDDING_MODEL",
                            "text-embedding-3-small",
                        ),
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
                        model=getattr(
                            config,
                            "DEFAULT_EMBEDDING_MODEL",
                            "text-embedding-3-small",
                        ),
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

            # 성공: Document.status = ready, Job 완료
            self._set_status(doc.knowledge_id, "ready")
            self._update_job(
                status="completed",
                progress=100,
                step="completed",
                completed_at=datetime.now(timezone.utc),
            )

            # 나머지 변경사항 commit
            self.db.commit()

            # 최신 값으로 refresh
            self.db.refresh(doc)
            self.document = doc
            return doc

        except Exception as e:
            # 실패: Document.status = failed, Job 실패 처리
            if self.document:
                try:
                    self._set_status(self.document.knowledge_id, "failed")
                except Exception:
                    pass
            if self.job_id:
                try:
                    self._update_job(
                        status="failed",
                        step="failed",
                        error_message=str(e),
                        completed_at=datetime.now(timezone.utc),
                    )
                except Exception:
                    pass
            try:
                self.db.commit()
            except Exception:
                pass
            raise
