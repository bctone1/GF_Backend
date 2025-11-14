# crud/supervisor/api_usage.py
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional, Tuple, List

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from models.supervisor.api_usage import ApiUsage
from schemas.supervisor.api_usage import (
    ApiUsageCreate,
    ApiUsageUpdate,
)
from core import config
import logging
log = logging.getLogger("api_usage")

class ApiUsageCRUD:
    """
    supervisor.api_usage 원장 테이블 CRUD
    - create: 호출 시점에 1행 기록
    - get: usage_id 단건 조회
    - list: 필터 + 페이징
    - update: 원장 수정이 꼭 필요할 때만 사용
    - delete: 보통은 잘 안 쓰지만 테스트/정리용
    """

    def __init__(self, model=ApiUsage):
        self.model = model

    # ------------------
    # 생성
    # ------------------
    def create(self, db: Session, data: ApiUsageCreate) -> ApiUsage:
        obj = self.model(**data.model_dump(exclude_unset=True))
        db.add(obj)
        db.commit()
        db.refresh(obj)
        return obj

    # ------------------
    # 단건 조회
    # ------------------
    def get(self, db: Session, usage_id: int) -> Optional[ApiUsage]:
        # PK는 (usage_id, requested_at)이지만, usage_id는 autoincrement라
        # usage_id 기준 최신 1건만 가져오면 대부분 충분함.
        stmt = (
            select(self.model)
            .where(self.model.usage_id == usage_id)
            .order_by(self.model.requested_at.desc())
            .limit(1)
        )
        return db.execute(stmt).scalars().first()

    # ------------------
    # 목록 조회 + 페이징
    # ------------------
    def list(
        self,
        db: Session,
        *,
        organization_id: Optional[int] = None,
        user_id: Optional[int] = None,
        provider: Optional[str] = None,
        endpoint: Optional[str] = None,
        status: Optional[str] = None,
        start_at: Optional[datetime] = None,
        end_at: Optional[datetime] = None,
        page: int = 1,
        size: int = 50,
    ) -> Tuple[List[ApiUsage], int]:
        """
        기본 필터 + 페이징 조회
        - 시간 필터는 requested_at 기준
        - 반환: (rows, total)
        """
        stmt = select(self.model)
        count_stmt = select(func.count())

        conditions = []

        if organization_id is not None:
            conditions.append(self.model.organization_id == organization_id)
        if user_id is not None:
            conditions.append(self.model.user_id == user_id)
        if provider:
            conditions.append(self.model.provider == provider)
        if endpoint:
            conditions.append(self.model.endpoint == endpoint)
        if status:
            conditions.append(self.model.status == status)
        if start_at is not None:
            conditions.append(self.model.requested_at >= start_at)
        if end_at is not None:
            conditions.append(self.model.requested_at <= end_at)

        if conditions:
            stmt = stmt.where(*conditions)
            count_stmt = count_stmt.select_from(self.model).where(*conditions)
        else:
            count_stmt = count_stmt.select_from(self.model)

        # 총 개수
        total = db.execute(count_stmt).scalar_one()

        # 정렬 + 페이징
        stmt = (
            stmt.order_by(self.model.requested_at.desc())
            .offset((page - 1) * size)
            .limit(size)
        )

        rows = db.execute(stmt).scalars().all()
        return rows, total

    # ------------------
    # 수정
    # ------------------
    def update(
        self,
        db: Session,
        *,
        usage_id: int,
        data: ApiUsageUpdate,
    ) -> Optional[ApiUsage]:
        obj = self.get(db, usage_id)
        if not obj:
            return None

        payload = data.model_dump(exclude_unset=True)
        for k, v in payload.items():
            setattr(obj, k, v)

        db.add(obj)
        db.commit()
        db.refresh(obj)
        return obj

    # ------------------
    # 삭제
    # ------------------
    def delete(self, db: Session, usage_id: int) -> bool:
        obj = self.get(db, usage_id)
        if not obj:
            return False
        db.delete(obj)
        db.commit()
        return True


api_usage_crud = ApiUsageCRUD()


# ============================================================
# 편의 함수: add_event (UploadPipeline 등에서 사용)
# ============================================================
def add_event(
    db: Session,
    *,
    ts_utc: datetime,
    product: str,
    model: str,
    llm_tokens: int,
    embedding_tokens: int,
    audio_seconds: int,  # 현재는 사용 안 하지만 시그니처 호환용
    cost_usd: float | Decimal,
    organization_id: Optional[int] = None,
    user_id: Optional[int] = None,
    status: str = "success",
    response_time_ms: Optional[int] = None,
) -> Optional[ApiUsage]:
    """
    UploadPipeline 등에서 쓰는 간단 로깅 헬퍼.

    - 기존 호출 시그니처를 그대로 받되
      supervisor.api_usage 모델에 맞춰 필드를 매핑해서 저장
    - organization_id 가 None 이면 config.DEFAULT_ORGANIZATION_ID 를 사용
    - 최종적으로 org_id 를 알 수 없으면 조용히 넘어감 (None 반환)
    """
    if not getattr(config, "ENABLE_API_USAGE_LOG", False):
        return None

    # NOTE 추후에 SQL 토큰값 집계 설정 후에 다시 시도
    # # 조직 ID 결정 (없으면 기본값 시도)
    # org_id = organization_id or getattr(config, "DEFAULT_ORGANIZATION_ID", None)
    # if org_id is None:
    #     # 아직 조직 컨텍스트를 안 붙였으면 기록 스킵
    #     return None
    #
    # # 토큰 합산 (chat + embedding 등)
    # total_tokens = int((llm_tokens or 0) + (embedding_tokens or 0))
    #
    # # 단순 매핑: product → provider, model → endpoint
    # provider = product              # 예: "embedding", "chat", "stt"
    # endpoint = model                # 예: "text-embedding-3-small", "gpt-4o-mini"
    #
    # payload = ApiUsageCreate(
    #     organization_id=org_id,
    #     user_id=user_id,
    #     provider=provider,
    #     endpoint=endpoint,
    #     tokens=total_tokens,
    #     cost=Decimal(str(cost_usd)),
    #     status=status,
    #     response_time_ms=response_time_ms,
    #     # requested_at 은 DB default (NOW()) 사용
    # )
    #
    # return api_usage_crud.create(db, payload)
