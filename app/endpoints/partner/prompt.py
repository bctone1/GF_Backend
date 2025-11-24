# app/endpoints/partner/prompt.py
from __future__ import annotations

from typing import Optional, Any

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.orm import Session

from core.deps import get_db, get_current_partner_user
from crud.partner import prompt as prompt_crud
from schemas.partner.prompt import (
    TemplateScope,
    BindingScope,
    PromptTemplateCreate,
    PromptTemplateUpdate,
    PromptTemplateResponse,
    PromptTemplatePage,
    PromptTemplateVersionCreate,
    PromptTemplateVersionUpdate,
    PromptTemplateVersionResponse,
    PromptTemplateVersionPage,
    PromptBindingCreate,
    PromptBindingUpdate,
    PromptBindingResponse,
    PromptBindingPage,
)

router = APIRouter()  # prefix는 routers.py에서 설정


# ==============================
# helpers
# ==============================

def _ensure_template_readable(template: Any, partner_id: int) -> None:
    # partner 템플릿인데 다른 파트너 것이면 404
    if template.scope == "partner" and template.partner_id != partner_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="template not found")


def _ensure_template_writable(template: Any, partner_id: int) -> None:
    # partner 자기 것만 수정 가능, global 은 파트너 엔드포인트에서 수정 불가
    if template.scope != "partner" or template.partner_id != partner_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="template not found")


# ==============================
# prompt_templates
# ==============================

@router.get("/templates", response_model=PromptTemplatePage)
def list_prompt_templates(
    partner_id: int = Path(..., ge=1),
    scope: Optional[TemplateScope] = Query(None, description="'partner' 또는 'global'"),
    include_global: bool = Query(
        True,
        description="partner 템플릿 조회 시 글로벌 템플릿도 함께 포함할지 여부",
    ),
    name: Optional[str] = Query(None),
    is_archived: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_user),
):
    rows, total = prompt_crud.list_prompt_templates(
        db,
        partner_id=partner_id,
        scope=scope,
        include_global=include_global,
        name=name,
        is_archived=is_archived,
        page=page,
        size=size,
    )
    items = [PromptTemplateResponse.model_validate(r) for r in rows]
    return {"items": items, "total": total, "page": page, "size": size}


@router.get("/templates/{template_id}", response_model=PromptTemplateResponse)
def get_prompt_template(
    partner_id: int = Path(..., ge=1),
    template_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_user),
):
    obj = prompt_crud.get_prompt_template(db, template_id=template_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="template not found")

    _ensure_template_readable(obj, partner_id)
    return PromptTemplateResponse.model_validate(obj)


@router.post("/templates", response_model=PromptTemplateResponse, status_code=status.HTTP_201_CREATED)
def create_prompt_template(
    partner_id: int = Path(..., ge=1),
    payload: PromptTemplateCreate = ...,
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_user),
):
    data = payload.model_dump(exclude_unset=True)
    # 파트너 엔드포인트에서는 항상 partner scope 로 고정
    data["partner_id"] = partner_id
    data["scope"] = "partner"
    obj = prompt_crud.create_prompt_template(db, data=data)
    return PromptTemplateResponse.model_validate(obj)


@router.patch("/templates/{template_id}", response_model=PromptTemplateResponse)
def update_prompt_template(
    partner_id: int = Path(..., ge=1),
    template_id: int = Path(..., ge=1),
    payload: PromptTemplateUpdate = ...,
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_user),
):
    obj = prompt_crud.get_prompt_template(db, template_id=template_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="template not found")

    _ensure_template_writable(obj, partner_id)

    data = payload.model_dump(exclude_unset=True)
    # 파트너 엔드포인트에서는 partner_id/scope 변경 불가
    data.pop("partner_id", None)
    data.pop("scope", None)

    obj = prompt_crud.update_prompt_template(db, template=obj, data=data)
    return PromptTemplateResponse.model_validate(obj)


@router.delete("/templates/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_prompt_template(
    partner_id: int = Path(..., ge=1),
    template_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_user),
):
    obj = prompt_crud.get_prompt_template(db, template_id=template_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="template not found")

    _ensure_template_writable(obj, partner_id)

    prompt_crud.delete_prompt_template(db, template=obj)
    return None


# ==============================
# prompt_template_versions
# ==============================

@router.get(
    "/templates/{template_id}/versions",
    response_model=PromptTemplateVersionPage,
)
def list_prompt_template_versions(
    partner_id: int = Path(..., ge=1),
    template_id: int = Path(..., ge=1),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_user),
):
    template = prompt_crud.get_prompt_template(db, template_id=template_id)
    if not template:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="template not found")

    _ensure_template_readable(template, partner_id)

    rows, total = prompt_crud.list_prompt_template_versions(
        db,
        template_id=template_id,
        page=page,
        size=size,
    )
    items = [PromptTemplateVersionResponse.model_validate(r) for r in rows]
    return {"items": items, "total": total, "page": page, "size": size}


@router.post(
    "/templates/{template_id}/versions",
    response_model=PromptTemplateVersionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_prompt_template_version(
    partner_id: int = Path(..., ge=1),
    template_id: int = Path(..., ge=1),
    payload: PromptTemplateVersionCreate = ...,
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_user),
):
    template = prompt_crud.get_prompt_template(db, template_id=template_id)
    if not template:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="template not found")

    # 버전 생성은 자기 파트너 템플릿에 대해서만 허용
    _ensure_template_writable(template, partner_id)

    data = payload.model_dump(exclude_unset=True)
    data["template_id"] = template_id  # path 기반으로 고정
    obj = prompt_crud.create_prompt_template_version(db, data=data)
    return PromptTemplateVersionResponse.model_validate(obj)


@router.get(
    "/template-versions/{version_id}",
    response_model=PromptTemplateVersionResponse,
)
def get_prompt_template_version(
    partner_id: int = Path(..., ge=1),
    version_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_user),
):
    version = prompt_crud.get_prompt_template_version(db, version_id=version_id)
    if not version:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="template_version not found")

    template = prompt_crud.get_prompt_template(db, template_id=version.template_id)
    if not template:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="template_version not found")

    _ensure_template_readable(template, partner_id)
    return PromptTemplateVersionResponse.model_validate(version)


@router.patch(
    "/template-versions/{version_id}",
    response_model=PromptTemplateVersionResponse,
)
def update_prompt_template_version(
    partner_id: int = Path(..., ge=1),
    version_id: int = Path(..., ge=1),
    payload: PromptTemplateVersionUpdate = ...,
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_user),
):
    version = prompt_crud.get_prompt_template_version(db, version_id=version_id)
    if not version:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="template_version not found")

    template = prompt_crud.get_prompt_template(db, template_id=version.template_id)
    if not template:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="template_version not found")

    _ensure_template_writable(template, partner_id)

    data = payload.model_dump(exclude_unset=True)
    version = prompt_crud.update_prompt_template_version(db, version_obj=version, data=data)
    return PromptTemplateVersionResponse.model_validate(version)


@router.delete(
    "/template-versions/{version_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_prompt_template_version(
    partner_id: int = Path(..., ge=1),
    version_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_user),
):
    version = prompt_crud.get_prompt_template_version(db, version_id=version_id)
    if not version:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="template_version not found")

    template = prompt_crud.get_prompt_template(db, template_id=version.template_id)
    if not template:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="template_version not found")

    _ensure_template_writable(template, partner_id)

    prompt_crud.delete_prompt_template_version(db, version_obj=version)
    return None


# ==============================
# prompt_bindings
# ==============================

@router.get("/bindings", response_model=PromptBindingPage)
def list_prompt_bindings(
    partner_id: int = Path(..., ge=1),
    scope_type: Optional[BindingScope] = Query(None),
    scope_id: Optional[int] = Query(None),
    template_version_id: Optional[int] = Query(None),
    is_active: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_user),
):
    # template_version_id 로 필터링할 경우, 접근 가능한 템플릿인지 한 번 체크
    if template_version_id is not None:
        version = prompt_crud.get_prompt_template_version(db, version_id=template_version_id)
        if not version:
            # 접근 불가/존재하지 않으면 빈 결과 반환
            return {"items": [], "total": 0, "page": page, "size": size}
        template = prompt_crud.get_prompt_template(db, template_id=version.template_id)
        if not template:
            return {"items": [], "total": 0, "page": page, "size": size}
        _ensure_template_readable(template, partner_id)

    rows, total = prompt_crud.list_prompt_bindings(
        db,
        scope_type=scope_type,
        scope_id=scope_id,
        template_version_id=template_version_id,
        is_active=is_active,
        page=page,
        size=size,
    )
    items = [PromptBindingResponse.model_validate(r) for r in rows]
    return {"items": items, "total": total, "page": page, "size": size}


@router.get("/bindings/{binding_id}", response_model=PromptBindingResponse)
def get_prompt_binding(
    partner_id: int = Path(..., ge=1),
    binding_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_user),
):
    binding = prompt_crud.get_prompt_binding(db, binding_id=binding_id)
    if not binding:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="binding not found")

    version = prompt_crud.get_prompt_template_version(db, version_id=binding.template_version_id)
    if not version:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="binding not found")

    template = prompt_crud.get_prompt_template(db, template_id=version.template_id)
    if not template:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="binding not found")

    _ensure_template_readable(template, partner_id)
    return PromptBindingResponse.model_validate(binding)


@router.post("/bindings", response_model=PromptBindingResponse, status_code=status.HTTP_201_CREATED)
def create_prompt_binding(
    partner_id: int = Path(..., ge=1),
    payload: PromptBindingCreate = ...,
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_user),
):
    # 템플릿 버전 접근 가능 여부 체크
    version = prompt_crud.get_prompt_template_version(db, version_id=payload.template_version_id)
    if not version:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="template_version not found")

    template = prompt_crud.get_prompt_template(db, template_id=version.template_id)
    if not template:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="template_version not found")

    _ensure_template_readable(template, partner_id)

    data = payload.model_dump(exclude_unset=True)
    obj = prompt_crud.create_prompt_binding(db, data=data)
    return PromptBindingResponse.model_validate(obj)


@router.patch("/bindings/{binding_id}", response_model=PromptBindingResponse)
def update_prompt_binding(
    partner_id: int = Path(..., ge=1),
    binding_id: int = Path(..., ge=1),
    payload: PromptBindingUpdate = ...,
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_user),
):
    binding = prompt_crud.get_prompt_binding(db, binding_id=binding_id)
    if not binding:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="binding not found")

    version = prompt_crud.get_prompt_template_version(db, version_id=binding.template_version_id)
    if not version:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="binding not found")

    template = prompt_crud.get_prompt_template(db, template_id=version.template_id)
    if not template:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="binding not found")

    _ensure_template_readable(template, partner_id)

    data = payload.model_dump(exclude_unset=True)
    # template_version_id 를 변경하는 경우에도 동일한 체크가 필요할 수 있음.
    if "template_version_id" in data:
        new_version_id = data["template_version_id"]
        new_version = prompt_crud.get_prompt_template_version(db, version_id=new_version_id)
        if not new_version:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="template_version not found")
        new_template = prompt_crud.get_prompt_template(db, template_id=new_version.template_id)
        if not new_template:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="template_version not found")
        _ensure_template_readable(new_template, partner_id)

    binding = prompt_crud.update_prompt_binding(db, binding=binding, data=data)
    return PromptBindingResponse.model_validate(binding)


@router.delete("/bindings/{binding_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_prompt_binding(
    partner_id: int = Path(..., ge=1),
    binding_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_user),
):
    binding = prompt_crud.get_prompt_binding(db, binding_id=binding_id)
    if not binding:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="binding not found")

    version = prompt_crud.get_prompt_template_version(db, version_id=binding.template_version_id)
    if not version:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="binding not found")

    template = prompt_crud.get_prompt_template(db, template_id=version.template_id)
    if not template:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="binding not found")

    _ensure_template_readable(template, partner_id)

    prompt_crud.delete_prompt_binding(db, binding=binding)
    return None
