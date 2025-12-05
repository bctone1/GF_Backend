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

# 프리뷰 LLM 사용 여부(현재는 안 쓰지만 남겨둠)
_USE_LLM_PREVIEW = getattr(config, "USE_LLM_PREVIEW", False)
if _USE_LLM_PREVIEW:
    from langchain_service.prompt.prompt import pdf_preview_prompt  # type: ignore


def _tok_len(s: str) -> int:
    model = getattr(config, "DEFAULT_EMBEDDING_MODEL", "text-embedding-3-small")
    return tokens_for_texts(model, [s])


class UploadPipeline:
    """
    [단계 개요]

    1) init_document(file): 파일을 저장하고, user.documents row 생성
       - status='uploading', progress=0 으로 시작
       - 여기까지는 요청 핸들러(엔드포인트)에서 실행

    2) process_document(knowledge_id): 백그라운드에서 무거운 작업 수행
       - 텍스트 추출 → 페이지 저장 → 청크 생성 → 임베딩 저장
       - 중간중간 documents.progress / status / error_message 갱신
    """

    def __init__(self, db: Session, user_id: int):
        self.db = db
        self.user_id = int(user_id)
        self.folder_rel = os.path.join(str(self.user_id), "document")
        self.base_dir = getattr(config, "UPLOAD_FOLDER", "./uploads")

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

    def chunk_text(self, text: str) -> List[str]:
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=900,
            chunk_overlap=150,
            length_function=_tok_len,
            separators=["\n\n", "\n", " ", ""],
        )
        return splitter.split_text(text)

    def embed_chunks(self, chunks: List[str]) -> Tuple[List[str], List[List[float]]]:
        # 1) 빈 문자열/공백 제거
        cleaned = [c for c in chunks if c and c.strip()]
        if not cleaned:
            return [], []

        # 2) 임베딩 객체 한 번만 가져와서 재사용
        #    (get_embeddings 안에서 OpenAIEmbeddings 를 캐시하도록 구현해두면,
        #     업로드 한 번당 / 프로세스당 1개만 생성됨)
        embeddings = get_embeddings()  # provider/model 은 factory 내부에서 config 기반으로 선택

        # 3) 배치 임베딩: 한 번에 여러 문장을 벡터로 변환
        #    LangChain Embeddings: embed_documents(List[str]) -> List[List[float]]
        vectors: List[List[float]] = embeddings.embed_documents(cleaned)

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
    def init_document(self, file: UploadFile) -> Document:
        """
        - 파일을 디스크에 저장
        - user.documents row 생성 (status='uploading', progress=0)
        - 무거운 파싱/임베딩은 아직 안 함
        """
        fpath, fname = self._save_file(file)
        file_size = os.path.getsize(fpath)
        file_format = file.content_type or "application/octet-stream"

        doc_in = DocumentCreate(
            owner_id=self.user_id,
            name=fname,
            file_format=file_format,
            file_size_bytes=file_size,
            folder_path=self.folder_rel,
            status="uploading",
            chunk_count=0,
            progress=0,
            error_message=None,
        )
        doc = doc_crud.document_crud.create(self.db, doc_in)
        self.db.flush()
        self.db.refresh(doc)
        return doc

    # ---------------------------
    # 2) 백그라운드에서 돌릴 무거운 처리
    # ---------------------------
    def process_document(self, knowledge_id: int) -> None:
        """
        이미 생성된 Document(knowledge_id 기준)에 대해
        텍스트 추출 → 페이지/청크 생성 → 임베딩 저장을 수행.
        """
        doc = doc_crud.document_crud.get(self.db, knowledge_id)
        if not doc:
            return

        # 파일 경로 복원
        folder_path = doc.folder_path or self.folder_rel
        file_path = os.path.join(self.base_dir, folder_path, doc.name)

        try:
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

            # 4) 청크 생성
            chunks = self.chunk_text(text)
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
