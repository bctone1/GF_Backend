# crud/partner/prompt.py
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

from models.partner.prompt import (
    PromptTemplate,
    PromptTemplateVersion,
    PromptBinding,
)


# =============================================================================
# PromptTemplate
# =============================================================================

def get_prompt_template(db: Session, template_id: int) -> Optional[PromptTemplate]:
    """
    ID 기준 단건 조회.
    """
    return db.get(PromptTemplate, template_id)


def list_prompt_templates(
    db: Session,
    *,
    partner_id: Optional[int] = None,
    scope: Optional[str] = None,          # 'partner' | 'global'
    include_global: bool = False,         # partner 템플릿 + 글로벌 템플릿 같이 보기
    name: Optional[str] = None,           # 부분 검색
    is_archived: Optional[bool] = None,
    page: int = 1,
    size: int = 50,
) -> Tuple[List[PromptTemplate], int]:
    """
    프롬프트 템플릿 목록 조회.

    - partner_id만 주면: 해당 파트너의 템플릿만
    - partner_id + include_global=True: 파트너 템플릿 + 글로벌 템플릿
    - scope='global': 글로벌만
    """
    if page < 1:
        page = 1
    if size < 1:
        size = 50

    filters = []

    if scope is not None:
        # 스코프가 명시되면 그 범위로만 필터링
        filters.append(PromptTemplate.scope == scope)
        if partner_id is not None and scope == "partner":
            filters.append(PromptTemplate.partner_id == partner_id)
    else:
        if partner_id is not None:
            if include_global:
                filters.append(
                    or_(
                        PromptTemplate.partner_id == partner_id,
                        PromptTemplate.scope == "global",
                    )
                )
            else:
                filters.append(PromptTemplate.partner_id == partner_id)

    if name:
        filters.append(PromptTemplate.name.ilike(f"%{name}%"))
    if is_archived is not None:
        filters.append(PromptTemplate.is_archived == is_archived)

    base_stmt: Select[PromptTemplate] = select(PromptTemplate)
    if filters:
        base_stmt = base_stmt.where(*filters)

    count_stmt = base_stmt.with_only_columns(func.count()).order_by(None)
    total = db.execute(count_stmt).scalar_one()

    stmt = (
        base_stmt
        .order_by(
            PromptTemplate.is_archived.asc(),   # 활성 먼저
            PromptTemplate.created_at.desc(),
            PromptTemplate.id.desc(),
        )
        .offset((page - 1) * size)
        .limit(size)
    )
    rows = db.execute(stmt).scalars().all()
    return rows, total


def create_prompt_template(
    db: Session,
    *,
    data: Dict[str, Any],
) -> PromptTemplate:
    """
    프롬프트 템플릿 생성.
    - PromptTemplateCreate.model_dump(exclude_unset=True) 사용.
    """
    obj = PromptTemplate(**data)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def update_prompt_template(
    db: Session,
    *,
    template: PromptTemplate,
    data: Dict[str, Any],
) -> PromptTemplate:
    """
    프롬프트 템플릿 수정.
    """
    for key, value in data.items():
        setattr(template, key, value)
    db.add(template)
    db.commit()
    db.refresh(template)
    return template


def delete_prompt_template(
    db: Session,
    *,
    template: PromptTemplate,
) -> None:
    """
    프롬프트 템플릿 삭제.
    - versions, bindings 는 CASCADE 로 정리됨.
    """
    db.delete(template)
    db.commit()


# -----------------------------------------------------------------------------
# NOTE (service/partner/prompt.py 에서 구현하기 좋은 헬퍼 예시)
#
# def create_template_with_first_version(...):
#     """
#     1) PromptTemplate 생성
#     2) PromptTemplateVersion(version=1) 생성
#     를 하나의 트랜잭션에서 처리하는 비즈니스 로직.
#     """
#     ...
# -----------------------------------------------------------------------------


# =============================================================================
# PromptTemplateVersion
# =============================================================================

def get_prompt_template_version(
    db: Session,
    version_id: int,
) -> Optional[PromptTemplateVersion]:
    return db.get(PromptTemplateVersion, version_id)


def list_prompt_template_versions(
    db: Session,
    *,
    template_id: Optional[int] = None,
    created_by: Optional[int] = None,
    page: int = 1,
    size: int = 50,
) -> Tuple[List[PromptTemplateVersion], int]:
    """
    템플릿 버전 목록.
    - template_id 기준으로 조회하는 것이 일반적.
    """
    if page < 1:
        page = 1
    if size < 1:
        size = 50

    filters = []
    if template_id is not None:
        filters.append(PromptTemplateVersion.template_id == template_id)
    if created_by is not None:
        filters.append(PromptTemplateVersion.created_by == created_by)

    base_stmt: Select[PromptTemplateVersion] = select(PromptTemplateVersion)
    if filters:
        base_stmt = base_stmt.where(*filters)

    count_stmt = base_stmt.with_only_columns(func.count()).order_by(None)
    total = db.execute(count_stmt).scalar_one()

    stmt = (
        base_stmt
        .order_by(
            PromptTemplateVersion.template_id.asc(),
            PromptTemplateVersion.version.desc(),
        )
        .offset((page - 1) * size)
        .limit(size)
    )
    rows = db.execute(stmt).scalars().all()
    return rows, total


def create_prompt_template_version(
    db: Session,
    *,
    data: Dict[str, Any],
) -> PromptTemplateVersion:
    """
    템플릿 버전 생성.
    - PromptTemplateVersionCreate.model_dump(exclude_unset=True) 사용.
    - 버전 번호 증가/중복 체크는 service 레이어에서 처리하는 것을 권장.
    """
    obj = PromptTemplateVersion(**data)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def update_prompt_template_version(
    db: Session,
    *,
    version_obj: PromptTemplateVersion,
    data: Dict[str, Any],
) -> PromptTemplateVersion:
    for key, value in data.items():
        setattr(version_obj, key, value)
    db.add(version_obj)
    db.commit()
    db.refresh(version_obj)
    return version_obj


def delete_prompt_template_version(
    db: Session,
    *,
    version_obj: PromptTemplateVersion,
) -> None:
    db.delete(version_obj)
    db.commit()


# -----------------------------------------------------------------------------
# NOTE (service/partner/prompt.py 예시)
#
# def create_next_version(
#     db: Session,
#     template: PromptTemplate,
#     content: str,
#     meta: dict[str, Any] | None,
#     created_by: int | None,
# ) -> PromptTemplateVersion:
#     """
#     1) template_id 로 현재 max(version) 조회
#     2) version = max + 1 로 PromptTemplateVersion 생성
#     """
#     ...
# -----------------------------------------------------------------------------


# =============================================================================
# PromptBinding
# =============================================================================

def get_prompt_binding(db: Session, binding_id: int) -> Optional[PromptBinding]:
    return db.get(PromptBinding, binding_id)


def list_prompt_bindings(
    db: Session,
    *,
    scope_type: Optional[str] = None,          # 'class' | 'global'
    scope_id: Optional[int] = None,
    template_version_id: Optional[int] = None,
    is_active: Optional[bool] = None,
    page: int = 1,
    size: int = 50,
) -> Tuple[List[PromptBinding], int]:
    """
    프롬프트 바인딩 목록.
    - 특정 분반(class)에 바인딩된 템플릿 버전 조회 등에 사용.
    """
    if page < 1:
        page = 1
    if size < 1:
        size = 50

    filters = []
    if scope_type is not None:
        filters.append(PromptBinding.scope_type == scope_type)
    if scope_id is not None:
        filters.append(PromptBinding.scope_id == scope_id)
    if template_version_id is not None:
        filters.append(PromptBinding.template_version_id == template_version_id)
    if is_active is not None:
        filters.append(PromptBinding.is_active == is_active)

    base_stmt: Select[PromptBinding] = select(PromptBinding)
    if filters:
        base_stmt = base_stmt.where(*filters)

    count_stmt = base_stmt.with_only_columns(func.count()).order_by(None)
    total = db.execute(count_stmt).scalar_one()

    stmt = (
        base_stmt
        .order_by(
            PromptBinding.scope_type.asc(),
            PromptBinding.scope_id.asc().nullsfirst(),
            PromptBinding.created_at.desc(),
            PromptBinding.id.desc(),
        )
        .offset((page - 1) * size)
        .limit(size)
    )
    rows = db.execute(stmt).scalars().all()
    return rows, total


def create_prompt_binding(
    db: Session,
    *,
    data: Dict[str, Any],
) -> PromptBinding:
    """
    프롬프트 바인딩 생성.
    - PromptBindingCreate.model_dump(exclude_unset=True) 사용.
    """
    obj = PromptBinding(**data)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def update_prompt_binding(
    db: Session,
    *,
    binding: PromptBinding,
    data: Dict[str, Any],
) -> PromptBinding:
    for key, value in data.items():
        setattr(binding, key, value)
    db.add(binding)
    db.commit()
    db.refresh(binding)
    return binding


def delete_prompt_binding(
    db: Session,
    *,
    binding: PromptBinding,
) -> None:
    db.delete(binding)
    db.commit()


# -----------------------------------------------------------------------------
# NOTE (service/partner/prompt.py 예시)
#
# def set_active_binding_for_class(
#     db: Session,
#     *,
#     class_id: int,
#     template_version_id: int,
# ) -> PromptBinding:
#     """
#     1) 해당 class 의 기존 바인딩 is_active=False 처리
#     2) 새 PromptBinding 생성 또는 갱신(is_active=True)
#     """
#     ...
#
# def resolve_bound_template_for_class(
#     db: Session,
#     *,
#     class_id: int,
# ) -> PromptTemplateVersion | None:
#     """
#     1) class 스코프의 활성 바인딩 조회
#     2) 없으면 global 스코프의 활성 바인딩 조회
#     3) PromptTemplateVersion 로딩
#     """
#     ...
# -----------------------------------------------------------------------------
