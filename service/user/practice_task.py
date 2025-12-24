# service/user/practice_task.py
import logging
from database.session import SessionLocal
from models.user.practice import PracticeSession
from langchain_service.llm.runner import generate_session_title_llm

from sqlalchemy import update, or_

logger = logging.getLogger(__name__)

def generate_session_title_task(*, session_id: int, question: str, answer: str, max_chars: int = 30) -> None:
    db = SessionLocal()
    try:
        title = generate_session_title_llm(question=question, answer=answer, max_chars=max_chars)
        if not title:
            return

        stmt = (
            update(PracticeSession)
            .where(PracticeSession.session_id == session_id)
            .where(or_(PracticeSession.title.is_(None), PracticeSession.title == ""))
            .values(title=title)
        )
        db.execute(stmt)
        db.commit()

    except Exception:
        db.rollback()
        logger.exception("generate_session_title_task failed: session_id=%s", session_id)
    finally:
        db.close()