# crud/partner/classes.py
from __future__ import annotations

from datetime import datetime
from typing import List, Optional, Tuple

from sqlalchemy import select, delete, func, and_, desc
from sqlalchemy.orm import Session, selectinload

from models.partner.course import Class, InviteCode
from models.partner.catalog import ModelCatalog


# ==============================
# 내부 헬퍼: LLM 모델 검증/정규화
# ==============================
def _validate_models_for_class(
    db: Session,
    *,
    primary_model_id: Optional[int],
    allowed_model_ids: Optional[List[int]],
) -> tuple[Optional[int], List[int]]:
    """
    Class 에 설정할 LLM 모델들을 검증하고 정규화한다.

    규칙:
    - primary_model_id / allowed_model_ids 에 있는 모든 id 는
      반드시 partner.model_catalog 에 존재해야 함.
    - primary_model_id 가 None 이고 allowed_model_ids 가 있으면,
      allowed_model_ids[0] 를 primary 로 자동 설정.
    - primary_model_id 가 allowed_model_ids 안에 없으면 자동으로 포함시킴.
    """
    # 아무 설정도 안 한 경우: 그냥 비워둠
    if primary_model_id is None and not allowed_model_ids:
        return None, []

    # 리스트 정리
    allowed_list: List[int] = list(allowed_model_ids or [])

    # primary 없고 allowed만 있으면, 첫 번째를 기본 모델로 사용
    if primary_model_id is None and allowed_list:
        primary_model_id = allowed_list[0]

    # primary 가 allowed 리스트에 없으면 추가
    if primary_model_id is not None and primary_model_id not in allowed_list:
        allowed_list.append(primary_model_id)

    # 실제로 존재하는 model_catalog.id 인지 검증
    model_ids = set(allowed_list)
    if primary_model_id is not None:
        model_ids.add(primary_model_id)

    if model_ids:
        rows = (
            db.execute(
                select(ModelCatalog.id).where(
                    ModelCatalog.id.in_(model_ids)
                )
            )
            .scalars()
            .all()
        )
        found_ids = set(rows)
        missing = model_ids - found_ids
        if missing:
            # 여기서 ValueError 를 던지면 엔드포인트 쪽에서 HTTPException 으로 변환해서 써주면 됨
            raise ValueError(
                f"model_catalog 에 존재하지 않는 모델 id 가 포함되어 있습니다: {sorted(missing)}"
            )

    return primary_model_id, allowed_list


# ==============================
# Class
# ==============================
def get_class(db: Session, class_id: int) -> Class | None:
    stmt = (
        select(Class)
        .options(selectinload(Class.invite_codes))  # 초대코드 같이 로드
        .where(Class.id == class_id)
    )
    return db.execute(stmt).scalars().first()


def list_classes(
    db: Session,
    course_id: int,
    *,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    order_desc: bool = True,
) -> Tuple[List[Class], int]:
    """
    특정 course 에 속한 class 목록.
    (course 에 속하지 않는 class 는 별도 쿼리 필요)
    """
    conds = [Class.course_id == course_id]
    if status:
        conds.append(Class.status == status)

    base = (
        select(Class)
        .options(selectinload(Class.invite_codes))  # 목록에서도 초대코드 같이 로드 (필요 없으면 제거해도 됨)
        .where(and_(*conds))
    )
    total = db.execute(
        select(func.count()).select_from(base.subquery())
    ).scalar() or 0

    base = base.order_by(desc(Class.created_at) if order_desc else Class.created_at)
    rows = db.execute(base.limit(limit).offset(offset)).scalars().all()
    return rows, total


def create_class(
    db: Session,
    *,
    partner_id: int,
    course_id: Optional[int] = None,
    name: str,
    description: Optional[str] = None,
    status: Optional[str] = None,
    start_at: Optional[datetime] = None,
    end_at: Optional[datetime] = None,
    capacity: Optional[int] = None,
    timezone: Optional[str] = None,
    location: Optional[str] = None,
    online_url: Optional[str] = None,
    invite_only: Optional[bool] = None,
    # LLM 설정
    primary_model_id: Optional[int] = None,
    allowed_model_ids: Optional[List[int]] = None,
) -> Class:
    """
    - partner_id: 이 class 를 여는 강사(Partner.id) (필수)
    - course_id: course 에 소속되면 지정, 아니면 None
    - primary_model_id: 기본으로 사용할 LLM (partner.model_catalog.id)
    - allowed_model_ids: 허용 모델 목록 (JSONB; None 이면 [] 사용)

    모델 관련 규칙:
    - primary_model_id / allowed_model_ids 는 모두 model_catalog 에 존재해야 함.
    - primary_model_id 가 None 이고 allowed_model_ids 가 있으면,
      allowed_model_ids[0] 를 primary 로 사용.
    - primary_model_id 는 항상 allowed_model_ids 안에 포함되도록 정규화.
    """
    # ---- LLM 모델 검증/정규화 ----
    primary_model_id, normalized_allowed = _validate_models_for_class(
        db,
        primary_model_id=primary_model_id,
        allowed_model_ids=allowed_model_ids,
    )

    obj = Class(
        partner_id=partner_id,
        course_id=course_id,
        name=name,
        description=description,
        status=status or "planned",
        start_at=start_at,
        end_at=end_at,
        capacity=capacity,
        timezone=timezone or "UTC",
        location=location,
        online_url=online_url,
        invite_only=invite_only if invite_only is not None else False,
        primary_model_id=primary_model_id,
        allowed_model_ids=normalized_allowed,  # JSONB 컬럼에 리스트로 저장
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def update_class(
    db: Session,
    class_id: int,
    *,
    name: Optional[str] = None,
    description: Optional[str] = None,
    status: Optional[str] = None,
    start_at: Optional[datetime] = None,
    end_at: Optional[datetime] = None,
    capacity: Optional[int] = None,
    timezone: Optional[str] = None,
    location: Optional[str] = None,
    online_url: Optional[str] = None,
    invite_only: Optional[bool] = None,
    course_id: Optional[int] = None,
    # LLM 설정
    primary_model_id: Optional[int] = None,
    allowed_model_ids: Optional[List[int]] = None,
) -> Optional[Class]:
    obj = db.get(Class, class_id)
    if not obj:
        return None

    # 기본 정보 수정
    if name is not None:
        obj.name = name
    if description is not None:
        obj.description = description
    if status is not None:
        obj.status = status
    if start_at is not None:
        obj.start_at = start_at
    if end_at is not None:
        obj.end_at = end_at
    if capacity is not None:
        obj.capacity = capacity
    if timezone is not None:
        obj.timezone = timezone
    if location is not None:
        obj.location = location
    if online_url is not None:
        obj.online_url = online_url
    if invite_only is not None:
        obj.invite_only = invite_only
    if course_id is not None:
        obj.course_id = course_id

    # LLM 설정 변경이 들어온 경우만 검증/정규화
    if primary_model_id is not None or allowed_model_ids is not None:
        # 현재 값에 패치 형태로 적용
        new_primary = (
            primary_model_id if primary_model_id is not None else obj.primary_model_id
        )
        existing_allowed = obj.allowed_model_ids or []
        new_allowed = (
            allowed_model_ids
            if allowed_model_ids is not None
            else list(existing_allowed)
        )

        new_primary, new_allowed = _validate_models_for_class(
            db,
            primary_model_id=new_primary,
            allowed_model_ids=new_allowed,
        )

        obj.primary_model_id = new_primary
        obj.allowed_model_ids = new_allowed

    db.commit()
    db.refresh(obj)
    return obj


def delete_class(db: Session, class_id: int) -> bool:
    res = db.execute(delete(Class).where(Class.id == class_id))
    db.commit()
    return res.rowcount > 0


# ==============================
# InviteCode
# ==============================
def get_invite_code(db: Session, code: str) -> Optional[InviteCode]:
    """
    초대코드 문자열로 단일 InviteCode 조회.
    code 는 유니크 제약이 있으므로 0 또는 1개만 존재.
    """
    stmt = select(InviteCode).where(InviteCode.code == code)
    return db.execute(stmt).scalars().first()


def get_invite_by_id(db: Session, invite_id: int) -> Optional[InviteCode]:
    """
    PK 기준 InviteCode 조회.
    """
    return db.get(InviteCode, invite_id)


def create_invite_code(
    db: Session,
    *,
    partner_id: int,
    code: str,
    target_role: str,
    class_id: Optional[int],
    expires_at: Optional[datetime],
    max_uses: Optional[int],
    status: str,
    created_by: Optional[int],
) -> InviteCode:
    """
    partner.invite_codes 생성.
    - target_role 은 현재 'student' 만 허용
    - class_id 는 NOT NULL 이므로 None 이면 에러.
    """
    if target_role != "student":
        raise ValueError("InviteCode.target_role 은 'student'만 허용됩니다.")
    if class_id is None:
        raise ValueError("class 기반 초대코드이므로 class_id 는 필수입니다.")
    if status not in ("active", "expired", "disabled"):
        raise ValueError("InviteCode.status 값이 올바르지 않습니다.")

    obj = InviteCode(
        partner_id=partner_id,
        class_id=class_id,
        code=code,
        target_role=target_role,
        expires_at=expires_at,
        max_uses=max_uses,
        status=status,
        created_by=created_by,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def get_invite_for_redeem(db: Session, *, code: str) -> Optional[InviteCode]:
    """
    초대코드 입력 화면에서 사용할 수 있는 유효한 InviteCode 조회.

    조건:
    - code 일치
    - status = 'active'
    - (expires_at 가 있으면) 아직 만료 전
    - (max_uses 가 있으면) used_count < max_uses
    """
    invite = get_invite_code(db, code)
    if not invite:
        return None

    now = datetime.utcnow()

    # 상태 체크
    if getattr(invite, "status", None) != "active":
        return None

    # 만료일 체크
    expires_at = getattr(invite, "expires_at", None)
    if expires_at is not None and expires_at < now:
        return None

    # 사용 횟수 체크
    max_uses = getattr(invite, "max_uses", None)
    used_count = getattr(invite, "used_count", None)
    if max_uses is not None and used_count is not None and used_count >= max_uses:
        return None

    return invite


def mark_invite_used(
    db: Session,
    *,
    invite_id: int,
    student_id: Optional[int] = None,
) -> Optional[InviteCode]:
    """
    초대코드 사용 처리.
    - used_count 증가
    - used_at 또는 last_used_at 갱신
    - student_id 기록 가능하면 기록
    - max_uses 에 도달하면 status 를 'disabled' 로 변경
      (DB 제약: active | expired | disabled)
    """
    invite = db.get(InviteCode, invite_id)
    if not invite:
        return None

    now = datetime.utcnow()

    # used_count 증가
    if hasattr(invite, "used_count"):
        invite.used_count = (invite.used_count or 0) + 1

    # 사용 시각 기록
    if hasattr(invite, "used_at"):
        invite.used_at = now
    if hasattr(invite, "last_used_at"):
        invite.last_used_at = now

    # 마지막 사용 학생 기록
    if student_id is not None and hasattr(invite, "last_used_by_student_id"):
        invite.last_used_by_student_id = student_id

    # max_uses 도달 시 status 변경
    max_uses = getattr(invite, "max_uses", None)
    used_count = getattr(invite, "used_count", None)
    if max_uses is not None and used_count is not None and used_count >= max_uses:
        invite.status = "disabled"

    db.add(invite)
    db.commit()
    db.refresh(invite)
    return invite
