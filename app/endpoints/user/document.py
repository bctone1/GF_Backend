# app/endpoints/user/document.py
from __future__ import annotations

import json, os
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
from models.user.account import AppUser
from models.user.document import DocumentPage  # reindex 시 pages 정리용

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

router = APIRouter()

_EMBEDDING_DIM_FIXED = 1536
_SCORE_TYPE_FIXED = "cosine_similarity"


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


def _approx_tokens(text: str) -> int:
    # 프리뷰용 저비용 추정치(대략 4 chars ~= 1 token)
    n = max(1, len(text) // 4)
    return n


def run_document_pipeline_background(user_id: int, knowledge_id: int) -> None:
    """
    BackgroundTasks에서 호출할 실제 작업 함수.
    - 새로운 DB 세션을 열어서 사용 후 닫는다.
    """
    db = SessionLocal()
    try:
        pipeline = UploadPipeline(db, user_id=user_id)
        pipeline.process_document(knowledge_id=knowledge_id)
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
    """
    문서 메타데이터만 직접 생성하는 예약 엔드포인트.
    실제 파일 업로드/파싱/임베딩은 /user/upload 사용.
    """
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
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="file required",
        )

    # 1) 파일 사이즈 체크
    max_bytes = config.DOCUMENT_MAX_SIZE_BYTES
    file.file.seek(0, 2)
    size = file.file.tell()
    file.file.seek(0)
    if size > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"파일 최대용량 도달. 최대 {config.DOCUMENT_MAX_SIZE_MB}MB 까지만 업로드할 수 있음",
        )

    # 2) 파일 저장 + Document row + settings 2row 생성(UploadPipeline에서 보장)
    pipeline = UploadPipeline(db, user_id=me.user_id)
    doc = pipeline.init_document(file)

    # 3) 커밋
    db.commit()
    db.refresh(doc)

    # 4) 백그라운드 처리
    background_tasks.add_task(
        run_document_pipeline_background,
        me.user_id,
        doc.knowledge_id,
    )

    return DocumentResponse.model_validate(doc)


# =========================================================
# Upload (Advanced)
# =========================================================
@router.post(
    "/upload/advanced",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="upload_document_advanced",
    summary="지식베이스 파일 업로드(고급)-비동기 ",
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
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="file required",
        )

    # 1) 파일 사이즈 체크
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

    # 2) 파일 저장 + Document row + settings 2row 생성(override 반영)
    pipeline = UploadPipeline(db, user_id=me.user_id)
    doc = pipeline.init_document(
        file,
        ingestion_override=ingestion_override,
        search_override=search_override,
    )

    # 3) 커밋
    db.commit()
    db.refresh(doc)

    # 4) 백그라운드 처리
    background_tasks.add_task(
        run_document_pipeline_background,
        me.user_id,
        doc.knowledge_id,
    )

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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="document not found",
        )
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
    summary="임베딩 파라미터 불러오기"
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
    summary="임베딩 파라미터 수정"
)
def patch_document_ingestion_settings(
    knowledge_id: int = Path(..., ge=1),
    data: DocumentIngestionSettingUpdate = ...,
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    _ensure_my_document(db, knowledge_id=knowledge_id, me=me)

    # row 존재 보장
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
    summary="RAG 검색 파라미터 튜닝"
)
def patch_document_search_settings(
    knowledge_id: int = Path(..., ge=1),
    data: DocumentSearchSettingUpdate = ...,
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    """
    - "top_k": 상위 청크 개수,
    - "min_score": 0~1 , 높을수록 까다로움 `0.1=` 좀만 비슷해도 통과,
    - "score_type": "cosine_similarity" (고정)
    - "reranker_enabled": `true` 면 후보 K 청크를 재정렬 함
    - "reranker_model": `bge-reranker-base` 리랭커 실제 모델
    - "reranker_top_n": 최종 청크 갯수, `top_k=10, reranker_top_n=3` : 10개 뽑고 rerank후 최종 3개 사용
    """
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
# Chunk Preview (저장 안 함)
# =========================================================
@router.post(
    "/document/{knowledge_id}/chunks/preview",
    response_model=ChunkPreviewResponse,
    operation_id="preview_document_chunks",
    summary="청크 프리뷰(저장 x)",
)
def preview_document_chunks(
    knowledge_id: int = Path(..., ge=1),
    body: ChunkPreviewRequest = ...,
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    doc = _ensure_my_document(db, knowledge_id=knowledge_id, me=me)

    # 파일 경로 복원
    base_dir = getattr(config, "UPLOAD_FOLDER", "./uploads")
    folder_path = doc.folder_path or os.path.join(str(me.user_id), "document")
    file_path = os.path.join(base_dir, folder_path, doc.name)

    pipeline = UploadPipeline(db, user_id=me.user_id)

    text, _ = pipeline.extract_text(file_path)
    chunks = pipeline.chunk_text(
        text,
        chunk_size=body.chunk_size,
        chunk_overlap=body.chunk_overlap,
        max_chunks=body.max_chunks,
        chunk_strategy=body.chunk_strategy,
    )

    items: List[ChunkPreviewItem] = []
    total_chars = 0
    total_tokens = 0

    for idx, ch in enumerate(chunks, start=1):
        cc = len(ch)
        tk = _approx_tokens(ch)
        total_chars += cc
        total_tokens += tk
        items.append(
            ChunkPreviewItem(
                chunk_index=idx,
                text=ch,
                char_count=cc,
                approx_tokens=tk,
            )
        )

    stats = ChunkPreviewStats(
        total_chunks=len(items),
        total_chars=total_chars,
        approx_total_tokens=total_tokens,
    )
    return ChunkPreviewResponse(items=items, stats=stats)


# =========================================================
# Reindex Trigger (단순 교체)
# =========================================================
@router.post(
    "/document/{knowledge_id}/reindex",
    status_code=status.HTTP_202_ACCEPTED,
    operation_id="reindex_document",
    summary="재인덱싱 트리거 버튼(백그라운드)",
)
def reindex_document(
    background_tasks: BackgroundTasks,
    knowledge_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
):
    _ensure_my_document(db, knowledge_id=knowledge_id, me=me)

    # 단순 방식: 기존 chunks/pages 정리 후 재실행
    # chunks 먼저 지우고(페이지 FK set null 이슈 회피) -> pages 삭제
    document_chunk_crud.delete_by_document(db, knowledge_id=knowledge_id)
    db.execute(sa_delete(DocumentPage).where(DocumentPage.knowledge_id == knowledge_id))

    # 문서 상태 리셋(진행률/카운트)
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

    background_tasks.add_task(
        run_document_pipeline_background,
        me.user_id,
        knowledge_id,
    )
    return None


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

    chunks = document_chunk_crud.list_by_document_page(
        db,
        knowledge_id=knowledge_id,
        page_id=page_id,
    )
    return [DocumentChunkResponse.model_validate(c) for c in chunks]
