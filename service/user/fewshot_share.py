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
    me: AppUser,
) -> UserFewShotExample:
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
        title=src_example.title,
        input_text=src_example.input_text,
        output_text=src_example.output_text,
        template_source="class_shared",
        meta=src_example.meta or {},
        is_active=True,
    )
    db.add(new_example)
    db.commit()
    db.refresh(new_example)
    return new_example


def attach_class_ids_to_examples(
    db: Session,
    *,
    examples: Iterable[UserFewShotExample],
    active_only: bool = True,
) -> None:
    _attach_shared_class_ids(
        db,
        examples=examples,
        active_only=active_only,
    )
