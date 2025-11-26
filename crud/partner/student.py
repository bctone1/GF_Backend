# crud/partner/student.py
from __future__ import annotations
from typing import Optional, Sequence, Tuple,Any
from datetime import datetime, timezone

from sqlalchemy import select, update, delete, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from models.partner.student import Student, Enrollment


# ========= Exceptions =========
class StudentError(Exception): ...
class StudentNotFound(StudentError): ...
class StudentConflict(StudentError): ...

class EnrollmentError(Exception): ...
class EnrollmentNotFound(EnrollmentError): ...
class EnrollmentConflict(EnrollmentError): ...


# ========= Helpers =========
def _utcnow() -> datetime:
    return datetime.now(timezone.utc)

# ========= Student CRUD =========
def create_student(
    db: Session,
    *,
    org_id: int,
    full_name: str,
    email: Optional[str] = None,
    status: str = "active",
    primary_contact: Optional[str] = None,
    notes: Optional[str] = None,
) -> Student:
    """
    org 내 email이 not null이면 유일.
    """
    obj = Student(
        org_id=org_id,
        full_name=full_name,
        email=email,
        status=status,
        primary_contact=primary_contact,
        notes=notes,
    )
    db.add(obj)
    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        # UNIQUE (org_id, email) 위반 등
        raise StudentConflict("duplicate email within org") from e
    db.refresh(obj)
    return obj


def get_student(db: Session, student_id: int) -> Optional[Student]:
    return db.get(Student, student_id)


def get_student_by_email(
    db: Session,
    *,
    org_id: int,
    email: str,
) -> Optional[Student]:
    stmt = (
        select(Student)
        .where(
            Student.org_id == org_id,
            func.lower(Student.email) == func.lower(email),
        )
        .limit(1)
    )
    return db.execute(stmt).scalar_one_or_none()



def list_students(
    db: Session,
    *,
    org_id: int,
    status: Optional[str] = None,
    q: Optional[str] = None,  # name/email/연락처 검색
    limit: int = 200,
    offset: int = 0,
) -> Sequence[Student]:
    stmt = select(Student).where(Student.org_id == org_id)

    if status:
        stmt = stmt.where(Student.status == status)

    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            Student.full_name.ilike(like)
            | (Student.email.isnot(None) & Student.email.ilike(like))
            | (Student.primary_contact.isnot(None) & Student.primary_contact.ilike(like))
        )

    stmt = (
        stmt.order_by(Student.joined_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return db.execute(stmt).scalars().all()


def update_student(db: Session, student_id: int, **fields) -> Optional[Student]:
    stmt = (
        update(Student)
        .where(Student.id == student_id)
        .values(**fields)
        .returning(Student)
    )
    try:
        row = db.execute(stmt).fetchone()
        if not row:
            db.rollback()
            return None
        db.commit()
        return row[0]
    except IntegrityError as e:
        db.rollback()
        raise StudentConflict("email conflict within partner") from e


def deactivate_student(db: Session, student_id: int) -> Optional[Student]:
    return update_student(db, student_id, status="inactive")


def archive_student(db: Session, student_id: int) -> Optional[Student]:
    return update_student(db, student_id, status="archived")


def delete_student(db: Session, student_id: int) -> bool:
    res = db.execute(delete(Student).where(Student.id == student_id))
    db.commit()
    return res.rowcount > 0


def ensure_student(
    db: Session,
    *,
    org_id: int,
    email: Optional[str],
    full_name: str,
    primary_contact: Optional[str] = None,
) -> Student:
    """
    email이 있으면 org 내 멱등 생성/조회. 없으면 무조건 생성.
    """
    if email:
        found = get_student_by_email(db, org_id=org_id, email=email)
        if found:
            changed: dict[str, Any] = {}
            if not found.full_name and full_name:
                changed["full_name"] = full_name
            if primary_contact and found.primary_contact != primary_contact:
                changed["primary_contact"] = primary_contact
            if changed:
                return update_student(db, found.id, **changed) or found
            return found

    return create_student(
        db,
        org_id=org_id,
        full_name=full_name,
        email=email,
        primary_contact=primary_contact,
    )


# ========= Enrollment CRUD =========
def enroll_student(
    db: Session,
    *,
    class_id: int,
    student_id: int,
    invite_code_id: Optional[int] = None,
    status: str = "active",
) -> Enrollment:
    obj = Enrollment(
        class_id=class_id,
        student_id=student_id,
        invite_code_id=invite_code_id,
        status=status,
        enrolled_at=_utcnow(),
    )
    db.add(obj)
    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        raise EnrollmentConflict("already enrolled") from e
    db.refresh(obj)
    return obj


def get_enrollment(db: Session, enrollment_id: int) -> Optional[Enrollment]:
    return db.get(Enrollment, enrollment_id)


def find_enrollment(db: Session, *, class_id: int, student_id: int) -> Optional[Enrollment]:
    stmt = (
        select(Enrollment)
        .where(Enrollment.class_id == class_id, Enrollment.student_id == student_id)
        .limit(1)
    )
    return db.execute(stmt).scalar_one_or_none()


def list_enrollments_by_class(
    db: Session,
    *,
    class_id: int,
    status: Optional[str] = None,
    limit: int = 500,
    offset: int = 0,
) -> Sequence[Enrollment]:
    stmt = (
        select(Enrollment)
        .where(Enrollment.class_id == class_id)
        .order_by(Enrollment.enrolled_at.desc())
        .limit(limit)
        .offset(offset)
    )
    if status:
        stmt = stmt.where(Enrollment.status == status)
    return db.execute(stmt).scalars().all()


def list_enrollments_by_student(
    db: Session,
    *,
    student_id: int,
    status: Optional[str] = None,
    limit: int = 200,
    offset: int = 0,
) -> Sequence[Enrollment]:
    stmt = (
        select(Enrollment)
        .where(Enrollment.student_id == student_id)
        .order_by(Enrollment.enrolled_at.desc())
        .limit(limit)
        .offset(offset)
    )
    if status:
        stmt = stmt.where(Enrollment.status == status)
    return db.execute(stmt).scalars().all()


def update_enrollment(db: Session, enrollment_id: int, **fields) -> Optional[Enrollment]:
    stmt = (
        update(Enrollment)
        .where(Enrollment.id == enrollment_id)
        .values(**fields)
        .returning(Enrollment)
    )
    row = db.execute(stmt).fetchone()
    if not row:
        db.rollback()
        return None
    db.commit()
    return row[0]


def set_enrollment_status(db: Session, enrollment_id: int, status: str) -> Optional[Enrollment]:
    return update_enrollment(db, enrollment_id, status=status)


def mark_completed(
    db: Session,
    enrollment_id: int,
    *,
    completed_at: Optional[datetime] = None,
) -> Optional[Enrollment]:
    """
    final_grade / progress_percent 제거 → 단순 완료처리만 남음
    """
    fields = {
        "status": "completed",
        "completed_at": completed_at or _utcnow(),
    }
    return update_enrollment(db, enrollment_id, **fields)


def drop_enrollment(db: Session, enrollment_id: int) -> Optional[Enrollment]:
    return update_enrollment(db, enrollment_id, status="dropped")


def delete_enrollment(db: Session, enrollment_id: int) -> bool:
    res = db.execute(delete(Enrollment).where(Enrollment.id == enrollment_id))
    db.commit()
    return res.rowcount > 0


# ========= 편의: invite-based join =========
def ensure_enrollment_by_email(
    db: Session,
    *,
    partner_id: int,
    class_id: int,
    email: Optional[str],
    full_name: str,
    invite_code_id: Optional[int] = None,
) -> Tuple[Student, Enrollment]:
    student = ensure_student(db, partner_id=partner_id, email=email, full_name=full_name)
    existing = find_enrollment(db, class_id=class_id, student_id=student.id)

    if existing:
        return student, existing

    enr = enroll_student(
        db,
        class_id=class_id,
        student_id=student.id,
        invite_code_id=invite_code_id,
        status="active",
    )
    return student, enr


def ensure_enrollment_for_invite(
    db: Session,
    *,
    org_id: int,
    class_id: int,
    invite_code_id: int,
    email: Optional[str],
    full_name: str,
    primary_contact: Optional[str] = None,
) -> Tuple[Student, Enrollment]:
    """
    학생 초대코드 redeem 시에 사용하는 헬퍼.

    1) org_id + email 기준으로 Student 멱등 생성/조회
    2) 해당 학생을 class_id에 멱등 수강 등록
    3) Enrollment.invite_code_id 세팅 (기존 등록이 있으면 필요 시만 업데이트)
    """
    # 1) 학생 보장
    student = ensure_student(
        db,
        org_id=org_id,
        email=email,
        full_name=full_name,
        primary_contact=primary_contact,
    )

    # 2) 기존 수강 여부 확인
    existing = find_enrollment(db, class_id=class_id, student_id=student.id)
    if existing:
        updates = {}
        if existing.invite_code_id is None:
            updates["invite_code_id"] = invite_code_id

        if updates:
            existing = update_enrollment(db, existing.id, **updates) or existing

        return student, existing

    # 3) 새로 수강 등록
    enrollment = enroll_student(
        db,
        class_id=class_id,
        student_id=student.id,
        invite_code_id=invite_code_id,
        status="active",
    )
    return student, enrollment

