# crud/partner/compare.py
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from models.partner.compare import ComparisonRun, ComparisonRunItem


# =============================================================================
# ComparisonRun CRUD
# =============================================================================

def get_run(db: Session, run_id: int) -> Optional[ComparisonRun]:
    """
    단일 비교 실행(run) 조회.
    """
    return db.get(ComparisonRun, run_id)


def list_runs(
    db: Session,
    *,
    student_id: Optional[int] = None,
    initiated_by: Optional[int] = None,
    status: Optional[str] = None,
    started_from: Optional[datetime] = None,
    started_to: Optional[datetime] = None,
    page: int = 1,
    size: int = 50,
) -> Tuple[List[ComparisonRun], int]:
    """
    비교 실행 목록 조회 (페이지네이션).
    - partner_id FK는 없어서, 호출하는 쪽에서 학생/강사 범위 검증이 필요.
    """
    if page < 1:
        page = 1
    if size < 1:
        size = 50

    filters = []

    if student_id is not None:
        filters.append(ComparisonRun.student_id == student_id)
    if initiated_by is not None:
        filters.append(ComparisonRun.initiated_by == initiated_by)
    if status is not None:
        filters.append(ComparisonRun.status == status)
    if started_from is not None:
        filters.append(ComparisonRun.started_at >= started_from)
    if started_to is not None:
        filters.append(ComparisonRun.started_at <= started_to)

    base_stmt: Select[ComparisonRun] = select(ComparisonRun)
    if filters:
        base_stmt = base_stmt.where(*filters)

    # total count
    count_stmt = base_stmt.with_only_columns(func.count()).order_by(None)
    total = db.execute(count_stmt).scalar_one()

    # page
    stmt = (
        base_stmt.order_by(ComparisonRun.started_at.desc())
        .offset((page - 1) * size)
        .limit(size)
    )
    rows = db.execute(stmt).scalars().all()

    return rows, total


def create_run(
    db: Session,
    *,
    data: Dict[str, Any],
) -> ComparisonRun:
    """
    비교 실행 생성.
    - endpoint/service: ComparisonRunCreate.model_dump(exclude_unset=True) 를 data 로 전달.
    - started_at 은 DB default 로 채우는 것이 일반적.
    """
    obj = ComparisonRun(**data)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def update_run(
    db: Session,
    *,
    run: ComparisonRun,
    data: Dict[str, Any],
) -> ComparisonRun:
    """
    비교 실행 메타 정보 수정.
    - status/notes/config/completed_at 등의 변경에 사용.
    """
    for key, value in data.items():
        setattr(run, key, value)
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def mark_run_completed(
    db: Session,
    *,
    run: ComparisonRun,
    completed_at: Optional[datetime] = None,
    status: str = "completed",
) -> ComparisonRun:
    """
    비교 실행 완료 처리 헬퍼.
    - service 레이어에서 모든 item 처리 후 호출하는 용도.
    """
    run.status = status
    if completed_at is not None:
        run.completed_at = completed_at
    else:
        run.completed_at = datetime.utcnow()
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def delete_run(
    db: Session,
    *,
    run: ComparisonRun,
) -> None:
    """
    비교 실행 삭제.
    - ComparisonRunItem 은 CASCADE 로 함께 삭제된다.
    """
    db.delete(run)
    db.commit()


# -----------------------------------------------------------------------------
# NOTE (service 레이어 예시 – 실제 구현은 service/partner/compare.py 에서):
#
# def start_comparison_run(
#     db: Session,
#     run_in: ComparisonRunCreate,
#     items_in: list[ComparisonRunItemCreate],
# ) -> ComparisonRun:
#     """
#     1) ComparisonRun 생성
#     2) ComparisonRunItem 여러 개 생성
#     3) 백그라운드에서 LLM 호출/비교 작업 enqueue
#     """
#     ...
# -----------------------------------------------------------------------------


# =============================================================================
# ComparisonRunItem CRUD
# =============================================================================

def get_run_item(db: Session, item_id: int) -> Optional[ComparisonRunItem]:
    """
    단일 비교 아이템 조회.
    """
    return db.get(ComparisonRunItem, item_id)


def list_run_items(
    db: Session,
    *,
    run_id: Optional[int] = None,
    status: Optional[str] = None,
    model_name: Optional[str] = None,
    page: int = 1,
    size: int = 50,
) -> Tuple[List[ComparisonRunItem], int]:
    """
    비교 아이템 목록 조회.
    - 주로 run_id 기준으로 조회.
    """
    if page < 1:
        page = 1
    if size < 1:
        size = 50

    filters = []
    if run_id is not None:
        filters.append(ComparisonRunItem.run_id == run_id)
    if status is not None:
        filters.append(ComparisonRunItem.status == status)
    if model_name is not None:
        filters.append(ComparisonRunItem.model_name == model_name)

    base_stmt: Select[ComparisonRunItem] = select(ComparisonRunItem)
    if filters:
        base_stmt = base_stmt.where(*filters)

    count_stmt = base_stmt.with_only_columns(func.count()).order_by(None)
    total = db.execute(count_stmt).scalar_one()

    stmt = (
        base_stmt.order_by(ComparisonRunItem.id.asc())
        .offset((page - 1) * size)
        .limit(size)
    )
    rows = db.execute(stmt).scalars().all()

    return rows, total


def create_run_item(
    db: Session,
    *,
    data: Dict[str, Any],
) -> ComparisonRunItem:
    """
    비교 아이템 생성.
    - ComparisonRunItemCreate.model_dump(exclude_unset=True) 를 data 로 전달.
    """
    obj = ComparisonRunItem(**data)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def update_run_item(
    db: Session,
    *,
    item: ComparisonRunItem,
    data: Dict[str, Any],
) -> ComparisonRunItem:
    """
    비교 아이템 수정.
    - status, total_tokens, average_latency_ms, total_cost 등의 갱신에 사용.
    """
    for key, value in data.items():
        setattr(item, key, value)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def delete_run_item(
    db: Session,
    *,
    item: ComparisonRunItem,
) -> None:
    """
    비교 아이템 삭제.
    """
    db.delete(item)
    db.commit()


# -----------------------------------------------------------------------------
# NOTE (service 레이어에서 사용할만한 헬퍼 인터페이스 예시):
#
# # 모든 item 이 success/error 상태가 되었는지 체크 후 run 상태 갱신
# def refresh_run_status_from_items(db: Session, run: ComparisonRun) -> ComparisonRun:
#     """
#     1) run.items 의 status 집계
#     2) 모두 success → run.status='completed'
#        하나라도 error → run.status='failed'
#        아직 pending/running 남아있으면 그대로 유지
#     3) completed 로 바뀌면 completed_at 설정
#     """
#
# -----------------------------------------------------------------------------
