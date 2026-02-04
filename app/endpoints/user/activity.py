# app/endpoints/user/activity.py
"""읽기 전용 엔드포인트: 활동 이벤트 & 기능 사용 통계."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Path, status
from sqlalchemy.orm import Session

from core.deps import get_db, get_current_user
from crud.user.activity import activity_event_crud, practice_feature_stat_crud
from models.user.account import AppUser
from schemas.base import Page
from schemas.user.activity import (
    UserActivityEventResponse,
    PracticeFeatureStatResponse,
)

router = APIRouter()


@router.get(
    "/events",
    response_model=Page[UserActivityEventResponse],
    operation_id="list_my_activity_events",
    summary="내활동이벤트목록",
    description=(
        "내 활동 이벤트를 페이지네이션으로 조회. response body:\n\n"
        "- items: 활동 이벤트 배열\n"
        "  - event_id: 이벤트 고유 ID\n"
        "  - user_id: 이벤트 주체 사용자 ID(항상 현재 로그인 사용자)\n"
        "  - event_type: 이벤트 유형 문자열\n"
        "    - session_created: 실습 세션 생성\n"
        "    - message_sent: 실습/비교 대화 메시지 전송\n"
        "    - prompt_created: 프롬프트 카드 생성\n"
        "    - project_created: 프로젝트 생성\n"
        "    - comparison_executed: 비교 실행\n"
        "    - fewshot_created: few-shot 예시 생성\n"
        "    - document_uploaded: 문서 업로드\n"
        "  - related_type: 관련 리소스 유형\n"
        "    - practice_session: 실습/비교 세션\n"
        "    - ai_prompt: 프롬프트 카드\n"
        "    - user_project: 프로젝트\n"
        "    - document: 문서(지식베이스)\n"
        "    - fewshot_example: few-shot 예시\n"
        "  - related_id: related_type에 해당하는 리소스 ID\n"
        "  - metadata: 이벤트별 부가 정보(JSON). 예) {\"model\": \"gpt-4o\", \"latency_ms\": 1200}\n"
        "  - occurred_at: 이벤트 발생 시각(UTC ISO-8601)\n"
        "- total: 전체 이벤트 수\n"
        "- page: 현재 페이지(1부터)\n"
        "- size: 페이지당 항목 수\n\n"
        "운영 관점에서 이벤트 유형/메타데이터 키는 사전 정의하고, 클라이언트와\n"
        "허용된 키만 사용하도록 합의하는 것을 권장."
    ),
    response_description="페이지네이션된 활동 이벤트 목록",
)
def list_my_activity_events(
    event_type: Optional[str] = Query(
        None,
        description=(
            "event_type 필터: `session_created`, `message_sent`, `prompt_created`, "
            "`project_created`, `comparison_executed`, `fewshot_created`, `document_uploaded`"
        ),
    ),
    related_type: Optional[str] = Query(
        None,
        description=(
            "related_type 필터: `practice_session`, `ai_prompt`, `user_project`, "
            "`document`, `fewshot_example`"
        ),
    ),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
) -> dict:
    """내 활동 이벤트를 페이지네이션으로 조회합니다."""
    rows, total = activity_event_crud.list_by_user(
        db,
        user_id=me.user_id,
        event_type=event_type,
        related_type=related_type,
        page=page,
        size=size,
    )
    items = [UserActivityEventResponse.model_validate(r) for r in rows]
    return {"items": items, "total": total, "page": page, "size": size}


@router.get(
    "/events/{event_id}",
    response_model=UserActivityEventResponse,
    operation_id="get_my_activity_event",
    summary="활동이벤트단건조회",
    description=(
        "활동 이벤트 단건을 조회. 응답 body는 다음 필드를 포함:\n\n"
        "- event_id: 이벤트 고유 ID\n"
        "- user_id: 이벤트 주체 사용자 ID(본인)\n"
        "- event_type: 이벤트 유형 문자열\n"
        "  - `session_created`, `message_sent`, `prompt_created`, `project_created`,\n"
        "    `comparison_executed`, `fewshot_created`, `document_uploaded`\n"
        "- related_type: 관련 리소스 유형\n"
        "  - `practice_session`, `ai_prompt`, `user_project`, `document`, `fewshot_example`\n"
        "- related_id: 관련 리소스 ID\n"
        "- metadata: 이벤트별 부가 정보(JSON)\n"
        "- occurred_at: 이벤트 발생 시각(UTC ISO-8601)\n\n"
        "존재하지 않거나 본인 소유가 아닌 경우 404를 반환."
    ),
    response_description="활동 이벤트 단건",
)
def get_my_activity_event(
    event_id: int = Path(..., description="조회할 이벤트 ID"),
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
) -> UserActivityEventResponse:
    """활동 이벤트 단건을 조회합니다. 본인 소유만 허용."""
    row = activity_event_crud.get(db, event_id)
    if row is None or row.user_id != me.user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="이벤트를 찾을 수 없습니다.",
        )
    return UserActivityEventResponse.model_validate(row)


@router.get(
    "/feature-stats",
    response_model=list[PracticeFeatureStatResponse],
    operation_id="list_my_feature_stats",
    summary="내기능사용통계",
    description=(
        "내 실습 기능 사용 통계를 조회합니다. response body는 LIST 필드내용:\n\n"
        "- stat_id: 통계 고유 ID\n"
        "- user_id: 통계 대상 사용자 ID(본인)\n"
        "- class_id: 강의 ID(없으면 전체 집계)\n"
        "- feature_type: 기능 유형\n"
        "  - `fewshot_used`: few-shot 예시 사용\n"
        "  - `parameter_tuned`: 생성 파라미터 튜닝\n"
        "  - `kb_connected`: 지식베이스 연결/사용\n"
        "  - `file_attached`: 문서(파일) 첨부\n"
        "- usage_count: 누적 사용 횟수\n"
        "- last_used_at: 마지막 사용 시각(UTC ISO-8601, 없을 수 있음)\n\n"
        "운영 환경에서는 feature_type을 고정된 enum으로 관리하고, 수집 지표/집계 주기를\n"
        "모니터링 대시보드와 연동하는 것을 권장"
    ),
    response_description="기능 사용 통계 목록",
)
def list_my_feature_stats(
    class_id: Optional[int] = Query(None, description="강의 ID 필터(없으면 전체)"),
    db: Session = Depends(get_db),
    me: AppUser = Depends(get_current_user),
) -> list[PracticeFeatureStatResponse]:
    """내 실습 기능 사용 통계를 조회합니다."""
    rows = practice_feature_stat_crud.list_by_user(
        db,
        user_id=me.user_id,
        class_id=class_id,
    )
    return [PracticeFeatureStatResponse.model_validate(r) for r in rows]
