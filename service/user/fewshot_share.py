# service/user/fewshot_share.py
from __future__ import annotations

from typing import Iterable, List, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from models.partner.course import Class
from models.user.account import AppUser
from models.user.fewshot import UserFewShotExample, FewShotShare
from crud.user.fewshot import few_shot_share_crud, user_few_shot_example_crud
from schemas.user.fewshot import FewShotShareCreate
from service.user.fewshot import ensure_my_few_shot_example
from service.user.prompt import ensure_enrolled_in_class
from service.user.prompt_share import ensure_my_class_as_teacher


def _attach_shared_class_ids(
    db: Session,
    *,
    examples: Iterable[UserFewShotExample],
    active_only: bool = True,
    class_id: Optional[int] = None,
) -> None:
    """예제 목록에 공유된 class_id 리스트를 ``class_ids`` 속성으로 부착한다.

    Args:
        db: SQLAlchemy 세션.
        examples: class_ids를 부착할 few-shot 예제 이터러블.
        active_only: ``True``이면 활성 공유만 조회.
        class_id: 특정 class로 필터링할 경우 지정.
    """
    example_list = list(examples)
    if not example_list:
        return

    example_ids = [example.example_id for example in example_list]
    query = (
        db.query(FewShotShare.example_id, FewShotShare.class_id)
        .filter(FewShotShare.example_id.in_(example_ids))
    )
    if active_only:
        query = query.filter(FewShotShare.is_active.is_(True))
    if class_id is not None:
        query = query.filter(FewShotShare.class_id == class_id)

    class_map: dict[int, list[int]] = {eid: [] for eid in example_ids}
    for example_id, class_id_row in query.all():
        class_map.setdefault(example_id, []).append(class_id_row)

    for example in example_list:
        setattr(example, "class_ids", class_map.get(example.example_id, []))


def share_few_shot_example_to_class(
    db: Session,
    *,
    example_id: int,
    class_id: int,
    me: AppUser,
) -> FewShotShare:
    """내 few-shot 예제를 특정 class에 공유한다.

    Args:
        db: SQLAlchemy 세션.
        example_id: 공유할 few-shot 예제 PK.
        class_id: 공유 대상 강의실 PK.
        me: 현재 인증된 사용자 (강사).

    Returns:
        생성 또는 재활성화된 ``FewShotShare`` 인스턴스.

    Raises:
        HTTPException: 소유권·강사 권한 실패(404/403) 또는 비활성 예제(400).
    """
    example = ensure_my_few_shot_example(db, example_id=example_id, me=me)
    ensure_my_class_as_teacher(db, class_id=class_id, me=me)

    if not bool(example.is_active):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="비활성 few-shot은 공유할 수 없습니다.",
        )

    share_in = FewShotShareCreate(
        example_id=example_id,
        class_id=class_id,
        is_active=None,
    )
    return few_shot_share_crud.get_or_create(
        db,
        obj_in=share_in,
        shared_by_user_id=me.user_id,
    )


def deactivate_few_shot_share(
    db: Session,
    *,
    example_id: int,
    class_id: int,
    me: AppUser,
) -> FewShotShare:
    """특정 class에 공유된 few-shot 공유를 비활성화한다.

    Args:
        db: SQLAlchemy 세션.
        example_id: 공유 해제할 few-shot 예제 PK.
        class_id: 공유 해제 대상 강의실 PK.
        me: 현재 인증된 사용자 (강사).

    Returns:
        비활성화된 ``FewShotShare`` 인스턴스.

    Raises:
        HTTPException: 소유권·강사 권한 실패 또는 공유 미존재(404).
    """
    ensure_my_few_shot_example(db, example_id=example_id, me=me)
    ensure_my_class_as_teacher(db, class_id=class_id, me=me)

    share = few_shot_share_crud.get_by_example_and_class(
        db,
        example_id=example_id,
        class_id=class_id,
    )
    if share is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="해당 강의에 공유된 few-shot을 찾을 수 없습니다.",
        )

    if not share.is_active:
        return share

    return few_shot_share_crud.set_active(db, share=share, is_active=False)


def list_shared_few_shot_examples_for_class(
    db: Session,
    *,
    class_id: int,
    me: AppUser,
    active_only: bool = True,
) -> List[UserFewShotExample]:
    """특정 class에 공유된 few-shot 예제 목록을 조회한다.

    Args:
        db: SQLAlchemy 세션.
        class_id: 조회 대상 강의실 PK.
        me: 현재 인증된 사용자 (수강생).
        active_only: ``True``이면 활성 공유·활성 예제만 반환.

    Returns:
        ``class_ids`` 속성이 부착된 ``UserFewShotExample`` 리스트.

    Raises:
        HTTPException: 강의 미존재(404) 또는 수강 미등록.
    """
    exists = db.query(Class.id).filter(Class.id == class_id).first()
    if exists is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="강의를 찾을 수 없음.",
        )

    ensure_enrolled_in_class(
        db=db,
        class_id=class_id,
        user_id=me.user_id,
    )

    query = (
        db.query(UserFewShotExample)
        .join(FewShotShare, FewShotShare.example_id == UserFewShotExample.example_id)
        .filter(FewShotShare.class_id == class_id)
    )

    if active_only:
        query = query.filter(
            FewShotShare.is_active.is_(True),
            UserFewShotExample.is_active.is_(True),
        )

    query = query.distinct(UserFewShotExample.example_id)
    examples = query.all()
    _attach_shared_class_ids(
        db,
        examples=examples,
        active_only=active_only,
        class_id=class_id,
    )
    return examples


def fork_shared_few_shot_example(
    db: Session,
    *,
    example_id: int,
    class_id: int,
    name: Optional[str] = None,
    me: AppUser,
) -> UserFewShotExample:
    """공유된 few-shot 예제를 내 라이브러리로 복제(fork)한다.

    Args:
        db: SQLAlchemy 세션.
        example_id: 원본 few-shot 예제 PK.
        class_id: 공유가 존재하는 강의실 PK.
        name: 새 few-shot 제목 (미지정 시 원본 제목 유지).
        me: 현재 인증된 사용자 (수강생).

    Returns:
        ``fewshot_source="class_shared"`` 로 생성된 새 ``UserFewShotExample``.

    Raises:
        HTTPException: 공유 미존재(404), 수강 미등록, 원본 비활성(400).
    """
    share: Optional[FewShotShare] = (
        db.query(FewShotShare)
        .filter(
            FewShotShare.example_id == example_id,
            FewShotShare.class_id == class_id,
            FewShotShare.is_active.is_(True),
        )
        .first()
    )
    if share is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="해당 강의에 공유된 few-shot을 찾을 수 없음.",
        )

    ensure_enrolled_in_class(
        db=db,
        class_id=class_id,
        user_id=me.user_id,
    )

    src_example = user_few_shot_example_crud.get(db, example_id)
    if src_example is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="원본 few-shot을 찾을 수 없음.",
        )

    if not bool(src_example.is_active):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="원본 few-shot이 비활성 상태라서 복제할 수 없음.",
        )

    new_example = UserFewShotExample(
        user_id=me.user_id,
        title=name if name is not None else src_example.title,
        input_text=src_example.input_text,
        output_text=src_example.output_text,
        fewshot_source="class_shared",
        meta=src_example.meta or {},
        is_active=True,
    )
    db.add(new_example)
    db.flush()
    db.refresh(new_example)
    return new_example


def attach_class_ids_to_examples(
    db: Session,
    *,
    examples: Iterable[UserFewShotExample],
    active_only: bool = True,
) -> None:
    """예제 목록에 공유된 class_id 리스트를 부착하는 퍼블릭 래퍼.

    Args:
        db: SQLAlchemy 세션.
        examples: class_ids를 부착할 few-shot 예제 이터러블.
        active_only: ``True``이면 활성 공유만 조회.
    """
    _attach_shared_class_ids(
        db,
        examples=examples,
        active_only=active_only,
    )
