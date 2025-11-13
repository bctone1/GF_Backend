# app/endpoints/partner/compare.py
from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.orm import Session

from core.deps import get_db, get_current_partner_admin
from crud.partner import compare as compare_crud
from schemas.partner.compare import (
    ComparisonRunCreate,
    ComparisonRunUpdate,
    ComparisonRunResponse,
    ComparisonRunPage,
    ComparisonRunItemCreate,
    ComparisonRunItemUpdate,
    ComparisonRunItemResponse,
    ComparisonRunItemPage,
)
from schemas.enums import ComparisonRunStatus, ComparisonItemStatus

router = APIRouter()


# ==============================
# comparison_runs
# ==============================

@router.get("", response_model=ComparisonRunPage)
def list_comparison_runs(
    partner_id: int = Path(..., ge=1),
    student_id: Optional[int] = Query(None),
    initiated_by: Optional[int] = Query(None),
    status: Optional[ComparisonRunStatus] = Query(None),
    started_from: Optional[datetime] = Query(None),
    started_to: Optional[datetime] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_admin),
):
    rows, total = compare_crud.list_runs(
        db,
        student_id=student_id,
        initiated_by=initiated_by,
        status=status,
        started_from=started_from,
        started_to=started_to,
        page=page,
        size=size,
    )
    items = [ComparisonRunResponse.model_validate(r) for r in rows]
    return {"items": items, "total": total, "page": page, "size": size}


@router.get("/{run_id}", response_model=ComparisonRunResponse)
def get_comparison_run(
    partner_id: int = Path(..., ge=1),
    run_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_admin),
):
    obj = compare_crud.get_run(db, run_id=run_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="comparison_run not found")
    return ComparisonRunResponse.model_validate(obj)


@router.post("", response_model=ComparisonRunResponse, status_code=status.HTTP_201_CREATED)
def create_comparison_run(
    partner_id: int = Path(..., ge=1),
    payload: ComparisonRunCreate = ...,
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_admin),
):
    data = payload.model_dump(exclude_unset=True)
    obj = compare_crud.create_run(db, data=data)
    return ComparisonRunResponse.model_validate(obj)


@router.patch("/{run_id}", response_model=ComparisonRunResponse)
def update_comparison_run(
    partner_id: int = Path(..., ge=1),
    run_id: int = Path(..., ge=1),
    payload: ComparisonRunUpdate = ...,
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_admin),
):
    obj = compare_crud.get_run(db, run_id=run_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="comparison_run not found")

    data = payload.model_dump(exclude_unset=True)
    obj = compare_crud.update_run(db, run=obj, data=data)
    return ComparisonRunResponse.model_validate(obj)


@router.delete("/{run_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_comparison_run(
    partner_id: int = Path(..., ge=1),
    run_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_admin),
):
    obj = compare_crud.get_run(db, run_id=run_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="comparison_run not found")

    compare_crud.delete_run(db, run=obj)
    return None


# ==============================
# comparison_run_items
# ==============================

@router.get("/{run_id}/items", response_model=ComparisonRunItemPage)
def list_comparison_run_items(
    partner_id: int = Path(..., ge=1),
    run_id: int = Path(..., ge=1),
    status: Optional[ComparisonItemStatus] = Query(None),
    model_name: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_admin),
):
    run = compare_crud.get_run(db, run_id=run_id)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="comparison_run not found")

    rows, total = compare_crud.list_run_items(
        db,
        run_id=run_id,
        status=status,
        model_name=model_name,
        page=page,
        size=size,
    )
    items = [ComparisonRunItemResponse.model_validate(r) for r in rows]
    return {"items": items, "total": total, "page": page, "size": size}


@router.post(
    "/{run_id}/items",
    response_model=ComparisonRunItemResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_comparison_run_item(
    partner_id: int = Path(..., ge=1),
    run_id: int = Path(..., ge=1),
    payload: ComparisonRunItemCreate = ...,
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_admin),
):
    run = compare_crud.get_run(db, run_id=run_id)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="comparison_run not found")

    data = payload.model_dump(exclude_unset=True)
    data["run_id"] = run_id  # path 기준으로 고정

    obj = compare_crud.create_run_item(db, data=data)
    return ComparisonRunItemResponse.model_validate(obj)


@router.get(
    "/{run_id}/items/{item_id}",
    response_model=ComparisonRunItemResponse,
)
def get_comparison_run_item(
    partner_id: int = Path(..., ge=1),
    run_id: int = Path(..., ge=1),
    item_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_admin),
):
    item = compare_crud.get_run_item(db, item_id=item_id)
    if not item or item.run_id != run_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="comparison_run_item not found")
    return ComparisonRunItemResponse.model_validate(item)


@router.patch(
    "/{run_id}/items/{item_id}",
    response_model=ComparisonRunItemResponse,
)
def update_comparison_run_item(
    partner_id: int = Path(..., ge=1),
    run_id: int = Path(..., ge=1),
    item_id: int = Path(..., ge=1),
    payload: ComparisonRunItemUpdate = ...,
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_admin),
):
    item = compare_crud.get_run_item(db, item_id=item_id)
    if not item or item.run_id != run_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="comparison_run_item not found")

    data = payload.model_dump(exclude_unset=True)
    item = compare_crud.update_run_item(db, item=item, data=data)
    return ComparisonRunItemResponse.model_validate(item)


@router.delete(
    "/{run_id}/items/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_comparison_run_item(
    partner_id: int = Path(..., ge=1),
    run_id: int = Path(..., ge=1),
    item_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    _=Depends(get_current_partner_admin),
):
    item = compare_crud.get_run_item(db, item_id=item_id)
    if not item or item.run_id != run_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="comparison_run_item not found")

    compare_crud.delete_run_item(db, item=item)
    return None
