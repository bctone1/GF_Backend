# app/endpoints/user/document.py
from __future__ import annotations

import json
import os
from typing import Optional, List, Any, Dict

from database.session import SessionLocal
from fastapi import (
    APIRouter,
    File,
    Form,
    Depends,
    HTTPException,
    Query,
    Path,
    status,
    UploadFile,
    BackgroundTasks,
)
from sqlalchemy.orm import Session
from sqlalchemy import delete as sa_delete

from core import config
from core.deps import get_db, get_current_user
from core.pricing import tokens_for_texts

from models.user.account import AppUser
from models.user.document import DocumentPage

from crud.user.document import (
    document_crud,
    document_usage_crud,
    document_page_crud,
    document_chunk_crud,
    document_ingestion_setting_crud,
    document_search_setting_crud,
)

from schemas.base import Page
from schemas.user.document import (
    DocumentCreate,
    DocumentUpdate,
    DocumentResponse,
    DocumentUsageResponse,
    DocumentPageResponse,
    DocumentChunkResponse,
    DocumentIngestionSettingResponse,
    DocumentIngestionSettingUpdate,
    DocumentSearchSettingResponse,
    DocumentSearchSettingUpdate,
    ChunkPreviewRequest,
    ChunkPreviewItem,
    ChunkPreviewStats,
    ChunkPreviewResponse,
)

from service.user.upload_pipeline import UploadPipeline
from langchain_text_splitters import RecursiveCharacterTextSplitter

from service.user.document_chunking import (
    build_splitter,
    split_segments,
    clean_texts,
)

router = APIRouter()

_EMBEDDING_DIM_FIXED = 1536
_SCORE_TYPE_FIXED = "cosine_similarity"

_PARENT_PREFIX = "[PARENT]"
_CHILD_PREFIX = "[CHILD]"
_CHUNK_PREFIX = "[CHUNK]"


def _ensure_my_document(db: Session, *, knowledge_id: int, me: AppUser):
    doc = document_crud.get(db, knowledge_id=knowledge_id)
    if not doc or doc.owner_id != me.user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="document not found",
        )
    return doc


def _safe_parse_json_dict(raw: Optional[str], *, field_name: str) -> Optional[Dict[str, Any]]:
    if raw is None:
        return None
    raw = raw.strip()
    if not raw:
        return None
    try:
        obj = json.loads(raw)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"invalid json in '{field_name}'",
        )
    if not isinstance(obj, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"'{field_name}' must be a JSON object",
        )
    return obj


def _resolve_document_file_path(*, doc, user_id: int) -> str:
    base_dir = getattr(config, "UPLOAD_FOLDER", "./uploads")
    folder_path = doc.folder_path or os.path.join(str(user_id), "document")
    return os.path.join(base_dir, folder_path, doc.name)


def _estimate_tokens(text: str, *, model: str) -> int:
    # preview에서만 쓰는 토큰 추정(실제로는 tiktoken 기반일 가능성이 높아서 정확)
    try:
        return int(tokens_for_texts(model, [text]))
    except Exception:
        # 안전망(대략치)
        return max(1, len(text) // 4)



def _decorate_parent(seg_idx: int, parent_text: str) -> str:
    return f"{_PARENT_PREFIX} seg={seg_idx}\n{parent_text.strip()}".strip()


def _decorate_child(seg_idx: int, child_idx: int, global_idx: int, child_text: str) -> str:
    return f"{_CHILD_PREFIX} seg={seg_idx} child={child_idx} global={global_idx}\n{child_text.strip()}".strip()


def _decorate_chunk(global_idx: int, chunk_text: str) -> str:
    return f"{_CHUNK_PREFIX} global={global_idx}\n{chunk_text.strip()}".strip()


def run_document_pipeline_background(user_id: int, knowledge_id: int) -> None:
    """
    BackgroundTasks에서 호출할 실제 작업 함수.
    통일안:
    - 엔드포인트는 파이프라인 세부 로직을 직접 수행하지 않고
      UploadPipeline.process_document()에 위임한다.
    """
    db = SessionLocal()
    try:
        pipeline = UploadPipeline(db, user_id=user_id)
        pipeline.process_document(knowledge_id)
        # process_document 내부에서 status/progress/pages/chunks/cost까지 처리 및 commit
    finally:
        db.close()


# =========================================================
# Document (내 문서)
# =========================================================
@router.get(
    "/document",
    response_model=Page[DocumentResponse],
    operation_id="list_my_document",
    summary="내 문서 리스트 조회",
)
def list_my_document(
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    status_filter: Optional[str] = Query(None, alias="status"),
    q: Optional[str] = Query(None, description="문서명 검색어"),
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    rows, total = document_crud.get_by_owner(
        db,
        owner_id=me.user_id,
        status=status_filter,
        q=q,
        page=page,
        size=size,
    )
    items = [DocumentResponse.model_validate(r) for r in rows]
    return {"items": items, "total": total, "page": page, "size": size}


# =========================================================
# Document Usage (READ ONLY)
# =========================================================
@router.get(
    "/document/{knowledge_id}/usage",
    response_model=List[DocumentUsageResponse],
    operation_id="list_document_usage",
)
def list_document_usage(
    knowledge_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    _ensure_my_document(db, knowledge_id=knowledge_id, me=me)
    usages = document_usage_crud.list_by_document(db, knowledge_id=knowledge_id)
    return [DocumentUsageResponse.model_validate(u) for u in usages]


# =========================================================
# Document Pages / Chunks (조회 전용)
# =========================================================
@router.get(
    "/document/{knowledge_id}/pages",
    response_model=List[DocumentPageResponse],
    operation_id="list_document_pages",
)
def list_document_pages(
    knowledge_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    _ensure_my_document(db, knowledge_id=knowledge_id, me=me)
    pages = document_page_crud.list_by_document(db, knowledge_id=knowledge_id)
    return [DocumentPageResponse.model_validate(p) for p in pages]


@router.get(
    "/document/{knowledge_id}/chunks",
    response_model=List[DocumentChunkResponse],
    operation_id="list_document_chunks",
)
def list_document_chunks(
    knowledge_id: int = Path(..., ge=1),
    page_id: Optional[int] = Query(None, ge=1),
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    _ensure_my_document(db, knowledge_id=knowledge_id, me=me)

    if page_id is None:
        chunks = document_chunk_crud.list_by_document(db, knowledge_id=knowledge_id)
    else:
        chunks = document_chunk_crud.list_by_document_page(
            db,
            knowledge_id=knowledge_id,
            page_id=page_id,
        )
    return [DocumentChunkResponse.model_validate(c) for c in chunks]


@router.post(
    "/document",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="create_document",
)
def create_document(
    data: DocumentCreate,
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    data_for_create = data.model_copy(update={"owner_id": me.user_id})
    doc = document_crud.create(db, data_for_create)
    db.commit()
    return DocumentResponse.model_validate(doc)


# =========================================================
# Upload (Basic)
# =========================================================
@router.post(
    "/upload",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="upload_document",
    summary="지식베이스 파일 업로드 (비동기 처리)",
)
def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="file required")

    max_bytes = config.DOCUMENT_MAX_SIZE_BYTES
    file.file.seek(0, 2)
    size = file.file.tell()
    file.file.seek(0)
    if size > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"파일 최대용량 도달. 최대 {config.DOCUMENT_MAX_SIZE_MB}MB 까지만 업로드할 수 있음",
        )

    pipeline = UploadPipeline(db, user_id=me.user_id)
    doc = pipeline.init_document(file)

    db.commit()
    db.refresh(doc)

    background_tasks.add_task(run_document_pipeline_background, me.user_id, doc.knowledge_id)
    return DocumentResponse.model_validate(doc)


# =========================================================
# Upload (Advanced)
# =========================================================
@router.post(
    "/upload/advanced",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="upload_document_advanced",
    summary="지식베이스 파일 업로드(고급)-비동기",
)
def upload_document_advanced(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    ingestion_settings: Optional[str] = Form(None),
    search_settings: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="file required")

    max_bytes = config.DOCUMENT_MAX_SIZE_BYTES
    file.file.seek(0, 2)
    size = file.file.tell()
    file.file.seek(0)
    if size > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"파일 최대용량 도달. 최대 {config.DOCUMENT_MAX_SIZE_MB}MB 까지만 업로드할 수 있음",
        )

    ingestion_override = _safe_parse_json_dict(ingestion_settings, field_name="ingestion_settings")
    search_override = _safe_parse_json_dict(search_settings, field_name="search_settings")

    pipeline = UploadPipeline(db, user_id=me.user_id)
    doc = pipeline.init_document(
        file,
        ingestion_override=ingestion_override,
        search_override=search_override,
    )

    db.commit()
    db.refresh(doc)

    background_tasks.add_task(run_document_pipeline_background, me.user_id, doc.knowledge_id)
    return DocumentResponse.model_validate(doc)


@router.get(
    "/document/{knowledge_id}",
    response_model=DocumentResponse,
    operation_id="get_document_detail",
)
def get_document_detail(
    knowledge_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    doc = _ensure_my_document(db, knowledge_id=knowledge_id, me=me)
    return DocumentResponse.model_validate(doc)


@router.patch(
    "/document/{knowledge_id}",
    response_model=DocumentResponse,
    operation_id="update_document",
)
def update_document(
    knowledge_id: int = Path(..., ge=1),
    data: DocumentUpdate = ...,
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    _ensure_my_document(db, knowledge_id=knowledge_id, me=me)

    updated = document_crud.update(db, knowledge_id=knowledge_id, data=data)
    db.commit()
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="document not found")
    return DocumentResponse.model_validate(updated)


@router.delete(
    "/document/{knowledge_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="delete_document",
)
def delete_document(
    knowledge_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    _ensure_my_document(db, knowledge_id=knowledge_id, me=me)
    document_crud.delete(db, knowledge_id=knowledge_id)
    db.commit()
    return None


# =========================================================
# Document Settings (ingestion/search)
# =========================================================
@router.get(
    "/document/{knowledge_id}/settings/ingestion",
    response_model=DocumentIngestionSettingResponse,
    operation_id="get_document_ingestion_settings",
    summary="임베딩 파라미터 불러오기",
)
def get_document_ingestion_settings(
    knowledge_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    _ensure_my_document(db, knowledge_id=knowledge_id, me=me)

    defaults = dict(getattr(config, "DEFAULT_INGESTION"))
    defaults["embedding_dim"] = _EMBEDDING_DIM_FIXED

    setting = document_ingestion_setting_crud.ensure_default(
        db,
        knowledge_id=knowledge_id,
        defaults=defaults,
    )
    db.commit()
    return DocumentIngestionSettingResponse.model_validate(setting)


@router.patch(
    "/document/{knowledge_id}/settings/ingestion",
    response_model=DocumentIngestionSettingResponse,
    operation_id="patch_document_ingestion_settings",
    summary="청킹 설정",
    description="**chunking_mode** : `general`(일반) | `parent_child` (부모자식)",
)
def patch_document_ingestion_settings(
    knowledge_id: int = Path(..., ge=1),
    data: DocumentIngestionSettingUpdate = ...,
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    _ensure_my_document(db, knowledge_id=knowledge_id, me=me)

    defaults = dict(getattr(config, "DEFAULT_INGESTION"))
    defaults["embedding_dim"] = _EMBEDDING_DIM_FIXED
    document_ingestion_setting_crud.ensure_default(db, knowledge_id=knowledge_id, defaults=defaults)

    updated = document_ingestion_setting_crud.update_by_knowledge_id(
        db,
        knowledge_id=knowledge_id,
        data=data,
    )
    db.commit()
    return DocumentIngestionSettingResponse.model_validate(updated)


# =========================================================
# Chunk Preview (저장 안 함)
# - general / parent-child 둘 다 지원
# - prefix는 프리뷰에서만 붙인다(DB에는 raw 유지)
# =========================================================
@router.post(
    "/document/{knowledge_id}/chunks/preview",
    response_model=ChunkPreviewResponse,
    operation_id="preview_document_chunks",
    summary="청크 프리뷰-미리보기 새로고침(저장 x)",
    description="저장되지 않고 미리보기 새로고침을 통하여 볼수 있음 확정되면,\n 청킹 설정 patch 통하여 확정",
)
def preview_document_chunks(
    knowledge_id: int = Path(..., ge=1),
    body: ChunkPreviewRequest = ...,
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    doc = _ensure_my_document(db, knowledge_id=knowledge_id, me=me)

    file_path = _resolve_document_file_path(doc=doc, user_id=me.user_id)
    pipeline = UploadPipeline(db, user_id=me.user_id)
    text, _ = pipeline.extract_text(file_path)

    # embed model은 현재 문서 ingestion setting 기준(없으면 default)
    ing = document_ingestion_setting_crud.get(db, knowledge_id)
    embed_model = (
        getattr(ing, "embedding_model", None)
        or getattr(config, "DEFAULT_EMBEDDING_MODEL", "text-embedding-3-small")
    )

    # preview에서만 쓰는 length_function
    def _tok_len(s: str) -> int:
        return _estimate_tokens(s or "", model=embed_model)

    # splitter는 ingest와 동일하게 build_splitter 사용
    child_splitter = build_splitter(
        chunk_size=int(body.chunk_size),
        chunk_overlap=int(body.chunk_overlap),
        strategy=str(body.chunk_strategy),
        length_function=_tok_len,
    )

    # max_chunks는 "child 기준"으로 제한 (ingest와 동일 컨셉)
    max_chunks = int(getattr(body, "max_chunks", 0) or 0)
    remaining = max_chunks if max_chunks > 0 else None

    items: List[ChunkPreviewItem] = []
    total_chars = 0
    total_tokens = 0

    def _push(idx: int, t: str):
        nonlocal total_chars, total_tokens
        cc = len(t)
        tk = _estimate_tokens(t, model=embed_model)
        total_chars += cc
        total_tokens += tk
        items.append(
            ChunkPreviewItem(
                chunk_index=idx,
                text=t,
                char_count=cc,
                approx_tokens=tk,
            )
        )

    flat_index = 1

    # -------------------------
    # GENERAL
    # -------------------------
    if body.chunking_mode == "general":
        chunks = clean_texts(child_splitter.split_text(text or ""))
        if remaining is not None:
            chunks = chunks[:remaining]

        for gi, ch in enumerate(chunks, start=1):
            _push(flat_index, _decorate_chunk(gi, ch))
            flat_index += 1

    # -------------------------
    # PARENT_CHILD
    # -------------------------
    else:
        # separator: 요청에서 안 오면(혹은 None이면) 디폴트로 보강
        separator = body.segment_separator or "\n\n"

        # parent chunking 옵션 (프리뷰도 ingest와 동일하게 반영)
        parent_chunk_size = getattr(body, "parent_chunk_size", None)
        parent_chunk_overlap = getattr(body, "parent_chunk_overlap", None)

        parent_splitter = None
        if parent_chunk_size:
            parent_splitter = build_splitter(
                chunk_size=int(parent_chunk_size),
                chunk_overlap=int(parent_chunk_overlap or 0),
                strategy=str(body.chunk_strategy),
                length_function=_tok_len,
            )

        segments = split_segments(text=text or "", separator=separator)

        global_child_idx = 1

        for seg_idx, segment_text in enumerate(segments, start=1):
            if remaining is not None and remaining <= 0:
                break

            # segment -> parent 단위(옵션)
            if parent_splitter is not None:
                parent_texts = clean_texts(parent_splitter.split_text(segment_text))
            else:
                st = (segment_text or "").strip()
                parent_texts = [st] if st else []

            if not parent_texts:
                continue

            child_in_segment = 1

            for parent_idx, parent_text in enumerate(parent_texts, start=1):
                if remaining is not None and remaining <= 0:
                    break

                parent_text = (parent_text or "").strip()
                if not parent_text:
                    continue

                # child 먼저 만들어보고(없으면 parent도 표시 안 함) -> ingest와 동일
                child_chunks = clean_texts(child_splitter.split_text(parent_text))
                if remaining is not None:
                    child_chunks = child_chunks[:remaining]
                if not child_chunks:
                    continue

                # parent 표시 (프리뷰용 prefix)
                _push(flat_index, f"{_PARENT_PREFIX} seg={seg_idx} parent={parent_idx}\n{parent_text}".strip())
                flat_index += 1

                for ch in child_chunks:
                    decorated = f"{_CHILD_PREFIX} seg={seg_idx} child={child_in_segment} global={global_child_idx}\n{ch.strip()}".strip()
                    _push(flat_index, decorated)
                    flat_index += 1

                    child_in_segment += 1
                    global_child_idx += 1

                    if remaining is not None:
                        remaining -= 1
                        if remaining <= 0:
                            break

    stats = ChunkPreviewStats(
        total_chunks=len(items),
        total_chars=total_chars,
        approx_total_tokens=total_tokens,
    )
    return ChunkPreviewResponse(items=items, stats=stats)


@router.get(
    "/document/{knowledge_id}/settings/search",
    response_model=DocumentSearchSettingResponse,
    operation_id="get_document_search_settings",
)
def get_document_search_settings(
    knowledge_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    _ensure_my_document(db, knowledge_id=knowledge_id, me=me)

    defaults = dict(getattr(config, "DEFAULT_SEARCH"))
    defaults["score_type"] = _SCORE_TYPE_FIXED

    setting = document_search_setting_crud.ensure_default(
        db,
        knowledge_id=knowledge_id,
        defaults=defaults,
    )
    db.commit()
    return DocumentSearchSettingResponse.model_validate(setting)


@router.patch(
    "/document/{knowledge_id}/settings/search",
    response_model=DocumentSearchSettingResponse,
    operation_id="patch_document_search_settings",
    summary="검색설정 : rerank 파라미터 튜닝",
)
def patch_document_search_settings(
    knowledge_id: int = Path(..., ge=1),
    data: DocumentSearchSettingUpdate = ...,
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    _ensure_my_document(db, knowledge_id=knowledge_id, me=me)

    defaults = dict(getattr(config, "DEFAULT_SEARCH"))
    defaults["score_type"] = _SCORE_TYPE_FIXED
    document_search_setting_crud.ensure_default(db, knowledge_id=knowledge_id, defaults=defaults)

    updated = document_search_setting_crud.update_by_knowledge_id(
        db,
        knowledge_id=knowledge_id,
        data=data,
    )
    db.commit()
    return DocumentSearchSettingResponse.model_validate(updated)


# =========================================================
# Reindex Trigger (단순 교체)
# =========================================================
@router.post(
    "/document/{knowledge_id}/reindex",
    status_code=status.HTTP_202_ACCEPTED,
    operation_id="reindex_document",
    summary="지식베이스 생성(백그라운드)",
)
def reindex_document(
    background_tasks: BackgroundTasks,
    knowledge_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    _ensure_my_document(db, knowledge_id=knowledge_id, me=me)

    document_chunk_crud.delete_by_document(db, knowledge_id=knowledge_id)
    db.execute(sa_delete(DocumentPage).where(DocumentPage.knowledge_id == knowledge_id))

    document_crud.update(
        db,
        knowledge_id=knowledge_id,
        data=DocumentUpdate(
            status="uploading",
            progress=0,
            chunk_count=0,
            error_message=None,
        ),
    )
    db.commit()

    background_tasks.add_task(run_document_pipeline_background, me.user_id, knowledge_id)
    return None
