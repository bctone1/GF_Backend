import logging
from database.session import SessionLocal
from models.user.practice import PracticeSession
from schemas.user.practice import PracticeSessionUpdate
from crud.user.practice import practice_session_crud
from langchain_service.llm.runner import generate_session_title_llm

logger = logging.getLogger(__name__)

def generate_session_title_task(*, session_id: int, question: str, answer: str, max_chars: int = 30) -> None:
    db = SessionLocal()
    try:
        sess = db.get(PracticeSession, session_id)
        if not sess:
            return
        if getattr(sess, "title", None):
            return

        title = generate_session_title_llm(question=question, answer=answer, max_chars=max_chars)
        if not title:
            return

        practice_session_crud.update(
            db,
            session_id=session_id,
            data=PracticeSessionUpdate(title=title),
        )
        db.commit()

    except Exception:
        db.rollback()
        logger.exception("generate_session_title_task failed: session_id=%s", session_id)
    finally:
        db.close()
