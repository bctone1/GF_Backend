# app/endpoints/common/model.py
from __future__ import annotations

from typing import Optional

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Path,
    Body,
    status,
)
from sqlalchemy.orm import Session


from core.deps import get_db, get_current_partner_user  # 다른 엔드포인트에서 쓸 수 있으니 그대로 둠
from crud.partner.catalog import (
    provider_credential,
    model_catalog,
    org_llm_setting,
)
from schemas.partner.catalog import (
    ProviderCredentialCreate,
    ProviderCredentialUpdate,
    ProviderCredentialResponse,
    ProviderCredentialPage,
    ModelCatalogCreate,
    ModelCatalogUpdate,
    ModelCatalogResponse,
    ModelCatalogPage,
    OrgLlmSettingUpdate,
    OrgLlmSettingResponse,
)

router = APIRouter()


def _require_org_id(me) -> int:
    org_id = getattr(me, "org_id", None)
    if org_id is None:
        raise HTTPException(status_code=400, detail="org_id not found for current partner")
    return org_id


# ==============================
# Model Catalog (공용 조회용)
# ==============================
@router.get("", response_model=ModelCatalogPage, summary="AI 모델 불러오기")
def list_models(
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    provider: Optional[str] = Query(None),
    modality: Optional[str] = Query(
        "chat",
        description="chat | embedding | stt | image | tts | rerank",
    ),
    q: Optional[str] = Query(None, description="모델이름 포함 검색"),
    only_active: bool = Query(
        True,
        description="활성 모델만 필터링",
    ),
    db: Session = Depends(get_db),
):
    """
    파트너/조직 의존성 없이 전체 모델 카탈로그를 조회하는 엔드포인트.

    - provider, modality, q 로 필터링
    - only_active=True 이면 is_active=True 인 모델만
    """
    rows, total = model_catalog.list(
        db,
        provider=provider,
        modality=modality,
        is_active=only_active,
        q=q,
        page=page,
        size=size,
    )

    items = [ModelCatalogResponse.model_validate(r) for r in rows]
    return {"items": items, "total": total, "page": page, "size": size}
