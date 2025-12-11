# crud/user/project.py
from typing import List, Optional, Dict, Any

from sqlalchemy.orm import Session
from sqlalchemy import select, func, delete

from crud.base import CRUDBase
from models.user.project import (
    UserProject,
    ProjectMember,
    ProjectTag,
    ProjectTagAssignment,
    ProjectMetric,
    ProjectActivity,
)
from models.user.practice import (
    PracticeSession,
    PracticeSessionModel,
    PracticeResponse,
)
from schemas.user.project import (
    UserProjectCreate,
    UserProjectUpdate,
    ProjectMemberCreate,
    ProjectMemberUpdate,
    ProjectTagCreate,
    ProjectTagUpdate,
    ProjectTagAssignmentCreate,
    ProjectTagAssignmentUpdate,
    ProjectMetricCreate,
    ProjectMetricUpdate,
    ProjectActivityCreate,
    ProjectActivityUpdate,
)


# =========================================================
# user.projects
# =========================================================
class CRUDUserProject(CRUDBase[UserProject, UserProjectCreate, UserProjectUpdate]):
    """
    user.projects 전용 CRUD.
    - 생성 시 owner_id는 항상 서버에서(me.user_id) 주입.
    """

    def create(
        self,
        db: Session,
        *,
        obj_in: UserProjectCreate,
        owner_id: int,
    ) -> UserProject:
        """
        owner_id 는 API에서 현재 로그인 유저 기준으로 넘겨준다.
        project_type/status/progress 등은 DB server_default 를 그대로 사용.
        """
        data = obj_in.model_dump(exclude_unset=True)
        data["owner_id"] = owner_id

        db_obj = self.model(**data)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def get_multi_by_owner(
        self,
        db: Session,
        *,
        owner_id: int,
        class_id: Optional[int] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[UserProject]:
        """
        내 프로젝트 목록 조회 (옵션: 특정 class 안의 프로젝트만).
        """
        stmt = (
            select(self.model)
            .where(self.model.owner_id == owner_id)
        )

        if class_id is not None:
            stmt = stmt.where(self.model.class_id == class_id)

        stmt = (
            stmt.order_by(
                self.model.last_activity_at.desc().nullslast(),
                self.model.created_at.desc(),
            )
            .offset(skip)
            .limit(limit)
        )

        return db.execute(stmt).scalars().all()

    def list_session_summaries(
            self,
            db: Session,
            *,
            project_id: int,
            user_id: int,  # owner_id → user_id 로 통일
            skip: int = 0,
            limit: int = 50,
            preview_length: int = 80,
    ) -> List[Dict[str, Any]]:
        """
        특정 프로젝트에 속한 practice_session 들을 카드용 요약 형태로 조회.
        - 세션 제목
        - 마지막 메시지 일부(preview)
        - 해당 메시지를 생성한 모델 이름
        - 마지막 활동 시각

        리턴 값은 service 레이어에서 ProjectSessionSummaryResponse 로 매핑해서 사용.
        """

        # 세션별 마지막 응답 시각 서브쿼리
        last_resp_subq = (
            select(
                PracticeResponse.session_id.label("session_id"),
                func.max(PracticeResponse.created_at).label("max_created_at"),
            )
            .group_by(PracticeResponse.session_id)
            .subquery()
        )

        preview_expr = func.substr(
            PracticeResponse.response_text, 1, preview_length
        )

        stmt = (
            select(
                PracticeSession.session_id,
                PracticeSession.project_id,
                PracticeSession.class_id,
                PracticeSession.title,
                preview_expr.label("preview_text"),
                PracticeSessionModel.model_name,
                last_resp_subq.c.max_created_at.label("last_activity_at"),
            )
            .join(
                last_resp_subq,
                last_resp_subq.c.session_id == PracticeSession.session_id,
            )
            .join(
                PracticeResponse,
                (PracticeResponse.session_id == last_resp_subq.c.session_id)
                & (PracticeResponse.created_at == last_resp_subq.c.max_created_at),
            )
            .join(
                PracticeSessionModel,
                PracticeSessionModel.session_model_id
                == PracticeResponse.session_model_id,
            )
            .where(
                PracticeSession.project_id == project_id,
                PracticeSession.user_id == user_id,  # ← 실제 컬럼 이름
            )
            .order_by(last_resp_subq.c.max_created_at.desc())
            .offset(skip)
            .limit(limit)
        )

        rows = db.execute(stmt).all()

        return [
            {
                "session_id": r.session_id,
                "project_id": r.project_id,
                "class_id": r.class_id,
                "title": r.title or "",
                "preview_text": r.preview_text or "",
                "model_name": r.model_name,
                "last_activity_at": r.last_activity_at,
            }
            for r in rows
        ]

    # 프로젝트 삭제
    def remove(self, db: Session, *, id: int) -> None:
        """
        UserProject 삭제.
        - 실제 commit 은 서비스/엔드포인트 단에서 처리.
        """
        obj = db.get(self.model, id)
        if obj is None:
            return

        db.delete(obj)
        db.flush()

user_project_crud = CRUDUserProject(UserProject)


# =========================================================
# user.project_members
# =========================================================
class CRUDProjectMember(
    CRUDBase[ProjectMember, ProjectMemberCreate, ProjectMemberUpdate]
):
    def get_multi_by_project(
        self,
        db: Session,
        *,
        project_id: int,
        skip: int = 0,
        limit: int = 100,
    ) -> List[ProjectMember]:
        stmt = (
            select(self.model)
            .where(self.model.project_id == project_id)
            .order_by(self.model.project_member_id.asc())
            .offset(skip)
            .limit(limit)
        )
        return db.execute(stmt).scalars().all()


project_member_crud = CRUDProjectMember(ProjectMember)


# =========================================================
# user.project_tags
# =========================================================
class CRUDProjectTag(
    CRUDBase[ProjectTag, ProjectTagCreate, ProjectTagUpdate]
):
    def get_by_name(
        self,
        db: Session,
        *,
        name: str,
    ) -> Optional[ProjectTag]:
        stmt = select(self.model).where(self.model.name == name)
        return db.execute(stmt).scalar_one_or_none()


project_tag_crud = CRUDProjectTag(ProjectTag)


# =========================================================
# user.project_tag_assignments
# =========================================================
class CRUDProjectTagAssignment(
    CRUDBase[
        ProjectTagAssignment,
        ProjectTagAssignmentCreate,
        ProjectTagAssignmentUpdate,
    ]
):
    def get_multi_by_project(
        self,
        db: Session,
        *,
        project_id: int,
    ) -> List[ProjectTagAssignment]:
        stmt = select(self.model).where(self.model.project_id == project_id)
        return db.execute(stmt).scalars().all()


project_tag_assignment_crud = CRUDProjectTagAssignment(ProjectTagAssignment)


# =========================================================
# user.project_metrics
# =========================================================
class CRUDProjectMetric(
    CRUDBase[ProjectMetric, ProjectMetricCreate, ProjectMetricUpdate]
):
    def get_recent_by_project(
        self,
        db: Session,
        *,
        project_id: int,
        limit: int = 100,
    ) -> List[ProjectMetric]:
        stmt = (
            select(self.model)
            .where(self.model.project_id == project_id)
            .order_by(self.model.recorded_at.desc())
            .limit(limit)
        )
        return db.execute(stmt).scalars().all()


project_metric_crud = CRUDProjectMetric(ProjectMetric)


# =========================================================
# user.project_activity
# =========================================================
class CRUDProjectActivity(
    CRUDBase[ProjectActivity, ProjectActivityCreate, ProjectActivityUpdate]
):
    def get_recent_by_project(
        self,
        db: Session,
        *,
        project_id: int,
        limit: int = 100,
    ) -> List[ProjectActivity]:
        stmt = (
            select(self.model)
            .where(self.model.project_id == project_id)
            .order_by(self.model.occurred_at.desc())
            .limit(limit)
        )
        return db.execute(stmt).scalars().all()


project_activity_crud = CRUDProjectActivity(ProjectActivity)
