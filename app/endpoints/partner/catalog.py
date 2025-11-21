# app/endpoints/partner/catalog.py
from __future__ import annotations
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Path, Body, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from core.deps import get_db, get_current_partner_admin
from crud.partner.catalog import provider_credential, model_catalog, org_llm_setting
from schemas.partner.catalog import (
    ProviderCredentialCreate, ProviderCredentialUpdate,
    ProviderCredentialResponse, ProviderCredentialPage,
    ModelCatalogCreate, ModelCatalogUpdate,
    ModelCatalogResponse, ModelCatalogPage,
    OrgLlmSettingUpdate, OrgLlmSettingResponse,
)


router = APIRouter()

# ==============================
# Provider Credentials
# ==============================
@router.get("/provider-credentials", response_model=ProviderCredentialPage)
def list_provider_credentials(
    partner_id: int = Path(..., ge=1),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    provider: Optional[str] = Query(None, description="openai, anthropic, google"),
    is_active: Optional[bool] = Query(None),
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_admin),
):
    rows, total = provider_credential.list(
        db,
        partner_id=partner_id,
        provider=provider,
        is_active=is_active,
        page=page,
        size=size,
    )
    items = [ProviderCredentialResponse.model_validate(r) for r in rows]
    return {"items": items, "total": total, "page": page, "size": size}


@router.post(
    "/provider-credentials",
    response_model=ProviderCredentialResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_provider_credential(
    partner_id: int = Path(..., ge=1),
    data: ProviderCredentialCreate = Body(...),
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_admin),
):
    if data.partner_id != partner_id:
        raise HTTPException(status_code=400, detail="partner_id mismatch")

    try:
        obj = provider_credential.create(
            db,
            data=data,
        )
    except IntegrityError:
        raise HTTPException(status_code=409, detail="credential for provider already exists")

    return ProviderCredentialResponse.model_validate(obj)


@router.patch(
    "/provider-credentials/{cred_id}",
    response_model=ProviderCredentialResponse,
)
def update_provider_credential(
    partner_id: int = Path(..., ge=1),
    cred_id: int = Path(..., ge=1),
    data: ProviderCredentialUpdate = Body(...),
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_admin),
):
    obj = provider_credential.get(db, cred_id)
    if not obj or obj.partner_id != partner_id:
        raise HTTPException(status_code=404, detail="provider credential not found")

    obj = provider_credential.update(
        db,
        id=cred_id,
        data=data,
    )
    return ProviderCredentialResponse.model_validate(obj)


@router.post(
    "/provider-credentials/{cred_id}/mark-validated",
    status_code=status.HTTP_204_NO_CONTENT,
)
def mark_provider_credential_validated(
    partner_id: int = Path(..., ge=1),
    cred_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_admin),
):
    obj = provider_credential.get(db, cred_id)
    if not obj or obj.partner_id != partner_id:
        raise HTTPException(status_code=404, detail="provider credential not found")

    provider_credential.mark_validated(db, id=cred_id)
    return


@router.delete(
    "/provider-credentials/{cred_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_provider_credential(
    partner_id: int = Path(..., ge=1),
    cred_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_admin),
):
    obj = provider_credential.get(db, cred_id)
    if not obj or obj.partner_id != partner_id:
        raise HTTPException(status_code=404, detail="provider credential not found")
    provider_credential.delete(db, id=cred_id)
    return


# ==============================
# Model Catalog
# ==============================
@router.get("/models", response_model=ModelCatalogPage)
def list_models(
    partner_id: int = Path(..., ge=1),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    provider: Optional[str] = Query(None),
    modality: Optional[str] = Query("chat", description="chat | embedding | stt | image "),
    q: Optional[str] = Query(None, description="모델이름 포함"),
    only_available: bool = Query(False, description="파트너가 키를 가진 모델만"),
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_admin),
):
    if only_available:
        rows, total = model_catalog.list_available_for_partner(
            db,
            partner_id=partner_id,
            modality=modality,
            only_active=True,
            page=page,
            size=size,
        )
    else:
        rows, total = model_catalog.list(
            db,
            provider=provider,
            modality=modality,
            is_active=True,
            q=q,
            page=page,
            size=size,
        )
    items = [ModelCatalogResponse.model_validate(r) for r in rows]
    return {"items": items, "total": total, "page": page, "size": size}


@router.post("/models", response_model=ModelCatalogResponse, status_code=status.HTTP_201_CREATED)
def create_model(
    partner_id: int = Path(..., ge=1),
    data: ModelCatalogCreate = Body(...),
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_admin),
):
    try:
        obj = model_catalog.create(
            db,
            data=data,
        )
    except IntegrityError:
        raise HTTPException(status_code=409, detail="model already exists for provider")
    return ModelCatalogResponse.model_validate(obj)


@router.patch("/models/{model_id}", response_model=ModelCatalogResponse)
def update_model(
    partner_id: int = Path(..., ge=1),
    model_id: int = Path(..., ge=1),
    data: ModelCatalogUpdate = Body(...),
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_admin),
):
    obj = model_catalog.get(db, model_id)
    if not obj:
        raise HTTPException(status_code=404, detail="model not found")

    obj = model_catalog.update(
        db,
        id=model_id,
        data=data,
    )
    return ModelCatalogResponse.model_validate(obj)


@router.delete("/models/{model_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_model(
    partner_id: int = Path(..., ge=1),
    model_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_admin),
):
    obj = model_catalog.get(db, model_id)
    if not obj:
        raise HTTPException(status_code=404, detail="model not found")
    model_catalog.delete(db, id=model_id)
    return


# ==============================
# Org LLM Setting
# ==============================
@router.get("/org-llm-setting", response_model=OrgLlmSettingResponse | None)
def get_org_llm_setting(
    partner_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_admin),
):
    obj = org_llm_setting.get_by_partner(db, partner_id=partner_id)
    return None if not obj else OrgLlmSettingResponse.model_validate(obj)


@router.put("/org-llm-setting", response_model=OrgLlmSettingResponse)
def upsert_org_llm_setting(
    partner_id: int = Path(..., ge=1),
    data: OrgLlmSettingUpdate = Body(...),
    db: Session = Depends(get_db),
    me=Depends(get_current_partner_admin),
):
    # updated_by는 항상 현재 파트너 관리자 기준으로 강제 세팅
    data.updated_by = getattr(me, "user_id", None)

    obj = org_llm_setting.upsert_by_partner(
        db,
        partner_id=partner_id,
        data=data,
    )
    return OrgLlmSettingResponse.model_validate(obj)
