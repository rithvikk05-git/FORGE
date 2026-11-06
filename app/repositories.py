
"""Case persistence. Mutations are explicit and audit events are append-only."""
from __future__ import annotations

import hashlib
import json
from contextlib import closing
from datetime import datetime, timezone

from .db import connect, initialize, transaction
from .schemas import Decision, Opportunity, Outcome


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def version_of(case: Opportunity) -> str:
    content = case.model_dump(mode="json", exclude={"ingested_at"})
    return hashlib.sha256(json.dumps(content, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:16]


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _audit(db, opportunity_id: str, event_type: str, actor: str, version: str, payload: dict) -> None:
    db.execute("INSERT INTO audit_events (opportunity_id,event_type,actor,case_version,payload_json,created_at) VALUES (?,?,?,?,?,?)",
               (opportunity_id, event_type, actor, version, _json(payload), utc_now()))


def save_case(case: Opportunity) -> str:
    initialize()
    version = version_of(case)
    with transaction() as db:
        previous = db.execute("SELECT case_version FROM opportunities WHERE opportunity_id=?", (case.opportunity_id,)).fetchone()
        if previous and previous["case_version"] == version:
            return version
        db.execute("INSERT INTO opportunities VALUES (?,?,?,?) ON CONFLICT(opportunity_id) DO UPDATE SET case_json=excluded.case_json,case_version=excluded.case_version,updated_at=excluded.updated_at",
                   (case.opportunity_id, case.model_dump_json(), version, utc_now()))
        db.execute("DELETE FROM evaluations WHERE opportunity_id=?", (case.opportunity_id,))
        db.execute("DELETE FROM approvals WHERE opportunity_id=?", (case.opportunity_id,))
        db.execute("DELETE FROM idempotency WHERE opportunity_id=?", (case.opportunity_id,))
        _audit(db, case.opportunity_id, "CASE_CREATED" if not previous else "CASE_REVISED", "local_user", version, {})
    return version


def get_case(opportunity_id: str) -> tuple[Opportunity, str] | None:
    initialize()
    with closing(connect()) as db:
        row = db.execute("SELECT case_json,case_version FROM opportunities WHERE opportunity_id=?", (opportunity_id,)).fetchone()
    return (Opportunity.model_validate_json(row["case_json"]), row["case_version"]) if row else None


def list_cases() -> list[dict]:
    initialize()
    with closing(connect()) as db:
        rows = db.execute("SELECT o.case_json,o.case_version,e.result_json,e.review_status FROM opportunities o LEFT JOIN evaluations e ON e.opportunity_id=o.opportunity_id ORDER BY o.opportunity_id").fetchall()
    return [{"case": json.loads(r["case_json"]), "case_version": r["case_version"],
             "evaluation": json.loads(r["result_json"]) if r["result_json"] else None,
             "review_status": r["review_status"] or "not_evaluated"} for r in rows]


def save_evaluation(opportunity_id: str, version: str, result: dict, status: str = "pending") -> None:
    with transaction() as db:
        row = db.execute("SELECT case_version FROM opportunities WHERE opportunity_id=?", (opportunity_id,)).fetchone()
        if not row or row["case_version"] != version:
            raise ValueError("Case changed during evaluation")
        db.execute("INSERT INTO evaluations VALUES (?,?,?,?,?) ON CONFLICT(opportunity_id) DO UPDATE SET case_version=excluded.case_version,result_json=excluded.result_json,review_status=excluded.review_status,updated_at=excluded.updated_at",
                   (opportunity_id, version, _json(result), status, utc_now()))
        _audit(db, opportunity_id, "EVALUATED", "system", version, {"blockers": result.get("blockers", [])})


def get_evaluation(opportunity_id: str) -> dict | None:
    initialize()
    with closing(connect()) as db:
        row = db.execute("SELECT result_json,review_status,case_version FROM evaluations WHERE opportunity_id=?", (opportunity_id,)).fetchone()
    return {"result": json.loads(row["result_json"]), "review_status": row["review_status"], "case_version": row["case_version"]} if row else None


def get_approval(opportunity_id: str) -> dict | None:
    initialize()
    with closing(connect()) as db:
        row = db.execute("SELECT * FROM approvals WHERE opportunity_id=?", (opportunity_id,)).fetchone()
    return dict(row) if row else None


def record_decision(opportunity_id: str, decision: Decision) -> dict:
    initialize()
    with transaction() as db:
        current = db.execute("SELECT case_version FROM opportunities WHERE opportunity_id=?", (opportunity_id,)).fetchone()
        evaluation = db.execute("SELECT review_status FROM evaluations WHERE opportunity_id=?", (opportunity_id,)).fetchone()
        if not current or not evaluation:
            raise ValueError("Case must be evaluated first")
        if current["case_version"] != decision.case_version:
            raise ValueError("Stale case version")
        if evaluation["review_status"] != "pending":
            raise ValueError("Review already decided")
        record = {**decision.model_dump(), "decided_at": utc_now()}
        db.execute("INSERT INTO approvals VALUES (?,?,?,?,?,?,?)",
                   (opportunity_id, decision.case_version, decision.decision, decision.reviewer_id,
                    decision.reviewer_role, decision.comments, record["decided_at"]))
        status = {"approve": "approved", "reject": "rejected", "request_changes": "changes_requested"}[decision.decision]
        db.execute("UPDATE evaluations SET review_status=?,updated_at=? WHERE opportunity_id=?", (status, utc_now(), opportunity_id))
        _audit(db, opportunity_id, "REVIEW_DECISION", decision.reviewer_id, decision.case_version, record)
    return record


def audit_events(opportunity_id: str) -> list[dict]:
    initialize()
    with closing(connect()) as db:
        rows = db.execute("SELECT * FROM audit_events WHERE opportunity_id=? ORDER BY event_id", (opportunity_id,)).fetchall()
    return [{**dict(r), "payload": json.loads(r["payload_json"])} for r in rows]


def add_outcome(opportunity_id: str, outcome: Outcome) -> None:
    current = get_case(opportunity_id)
    if current is None:
        raise KeyError(opportunity_id)
    with transaction() as db:
        db.execute("INSERT INTO outcomes (opportunity_id,outcome_json,created_at) VALUES (?,?,?)",
                   (opportunity_id, outcome.model_dump_json(), utc_now()))
        _audit(db, opportunity_id, "OUTCOME_RECORDED", "local_user", current[1], outcome.model_dump(mode="json"))


def get_outcomes(opportunity_id: str) -> list[dict]:
    initialize()
    with closing(connect()) as db:
        rows = db.execute("SELECT outcome_json,created_at FROM outcomes WHERE opportunity_id=? ORDER BY event_id", (opportunity_id,)).fetchall()
    return [{"outcome": json.loads(row["outcome_json"]), "created_at": row["created_at"]} for row in rows]
