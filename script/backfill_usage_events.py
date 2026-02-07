"""
Backfill partner.usage_events from user.practice_responses.

Join path:
  practice_responses (pr)
    -> practice_sessions (ps)  ON pr.session_id = ps.session_id
    -> classes (cl)            ON ps.class_id = cl.id
    -> partners (pt)           ON cl.partner_id = pt.id
    -> students (st)           ON ps.user_id = st.user_id AND st.partner_id = pt.id
    -> enrollments (en)        ON en.class_id = cl.id AND en.student_id = st.id

Skips rows where ps.class_id IS NULL (personal practice, no partner context).

Idempotent: uses upsert on request_id = "backfill-resp-{response_id}".

Usage:
    python -m scripts.backfill_usage_events
"""
from __future__ import annotations

import logging
import sys
from decimal import Decimal
from typing import Any, Dict, List, Optional

from sqlalchemy import text as sa_text

from core import config
from core.pricing import estimate_llm_cost_usd
from database.session import SessionLocal

log = logging.getLogger(__name__)

BATCH_SIZE = 100

# ── SQL: fetch all practice_responses with partner context ──
_FETCH_SQL = sa_text("""
    SELECT
        pr.response_id,
        pr.created_at       AS occurred_at,
        pr.model_name,
        pr.token_usage,
        pr.latency_ms,
        ps.session_id       AS practice_session_id,
        ps.class_id,
        cl.partner_id       AS instructor_partner_id,
        pt.org_id,
        st.id               AS student_id,
        en.id               AS enrollment_id
    FROM "user".practice_responses pr
    JOIN "user".practice_sessions ps
        ON pr.session_id = ps.session_id
    JOIN partner.classes cl
        ON ps.class_id = cl.id
    JOIN partner.partners pt
        ON cl.partner_id = pt.id
    LEFT JOIN partner.students st
        ON ps.user_id = st.user_id
       AND st.partner_id = pt.id
    LEFT JOIN partner.enrollments en
        ON en.class_id  = cl.id
       AND en.student_id = st.id
    WHERE ps.class_id IS NOT NULL
    ORDER BY pr.response_id
""")


def _resolve_provider(model_name: str) -> str:
    """Resolve provider from PRACTICE_MODELS config; fallback 'unknown'."""
    practice_models: Dict[str, Any] = getattr(config, "PRACTICE_MODELS", {}) or {}
    conf = practice_models.get(model_name)
    if isinstance(conf, dict):
        return conf.get("provider") or "unknown"
    return "unknown"


def _extract_token_fields(token_usage: Any) -> Dict[str, int]:
    """Extract prompt/completion/total tokens from JSONB token_usage."""
    if not isinstance(token_usage, dict):
        return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    prompt = int(token_usage.get("prompt_tokens") or 0)
    completion = int(token_usage.get("completion_tokens") or 0)
    total = int(token_usage.get("total_tokens") or 0)
    if total == 0 and (prompt or completion):
        total = prompt + completion
    return {"prompt_tokens": prompt, "completion_tokens": completion, "total_tokens": total}


def _estimate_cost(model_name: str, tokens: Dict[str, int]) -> Decimal:
    """Estimate USD cost; return 0 on pricing miss."""
    try:
        return estimate_llm_cost_usd(
            model_name,
            prompt_tokens=tokens["prompt_tokens"],
            completion_tokens=tokens["completion_tokens"],
            total_tokens=tokens["total_tokens"] or None,
        )
    except (ValueError, KeyError):
        return Decimal("0")


def backfill() -> int:
    """Run backfill. Returns number of rows inserted (new, not duplicates)."""
    db = SessionLocal()
    try:
        rows = db.execute(_FETCH_SQL).mappings().all()
        log.info("Fetched %d practice_responses with partner context", len(rows))

        if not rows:
            log.info("Nothing to backfill.")
            return 0

        from crud.partner.usage import upsert_usage_event_idempotent

        inserted = 0
        for i in range(0, len(rows), BATCH_SIZE):
            batch = rows[i : i + BATCH_SIZE]
            for r in batch:
                model_name: str = r["model_name"] or ""
                provider = _resolve_provider(model_name)
                tokens = _extract_token_fields(r["token_usage"])
                cost = _estimate_cost(model_name, tokens)

                meta: Dict[str, Any] = {
                    "tokens_prompt": tokens["prompt_tokens"],
                    "tokens_completion": tokens["completion_tokens"],
                    "response_id": int(r["response_id"]),
                    "backfill": True,
                }

                request_id = f"backfill-resp-{r['response_id']}"

                evt = upsert_usage_event_idempotent(
                    db,
                    request_id=request_id,
                    occurred_at=r["occurred_at"],
                    partner_id=int(r["org_id"]),
                    class_id=int(r["class_id"]),
                    student_id=int(r["student_id"]) if r["student_id"] else None,
                    enrollment_id=int(r["enrollment_id"]) if r["enrollment_id"] else None,
                    session_id=None,  # partner.ai_sessions FK — no matching row
                    request_type="llm_chat",
                    provider=provider,
                    model_name=model_name,
                    total_tokens=tokens["total_tokens"],
                    latency_ms=int(r["latency_ms"]) if r["latency_ms"] is not None else None,
                    total_cost_usd=cost,
                    success=True,
                    meta=meta,
                )
                inserted += 1

            db.commit()
            log.info("Committed batch %d–%d (%d/%d)", i, i + len(batch), i + len(batch), len(rows))

        log.info("Backfill complete. %d rows processed.", inserted)
        return inserted

    except Exception:
        db.rollback()
        log.exception("Backfill failed")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    count = backfill()
    print(f"\nDone — {count} usage_events processed.")
    sys.exit(0)
