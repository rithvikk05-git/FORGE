
"""Workflow adapter shared by API and future UI."""
from __future__ import annotations

from collections import Counter

from .graph import evaluate_graph, resume_graph
from .config import settings
from .policy_engine import assess
from .repositories import (add_outcome, audit_events, get_approval, get_case, get_evaluation,
                           get_outcomes, list_cases, record_decision, save_case, save_evaluation)
from .schemas import Decision, Opportunity, Outcome


def _evaluation_result(state: dict, opportunity_id: str, version: str,
                       previous: dict | None = None) -> dict:
    """Keep new agent findings and tolerate older review checkpoints."""
    result = {**(previous or {}), **state["assessment"]}
    for name in ("sme_matching", "feasibility", "risk_assessment", "consolidation"):
        if name in state:
            result[name] = state[name]
    result.update(trace=state.get("trace", []), opportunity_id=opportunity_id,
                  case_version=version, review_status=state["review_status"],
                  approved_summary=state.get("approved_summary"),
                  prompt_template=state.get("prompt_template"),
                  reference_counts={name: len(rows) for name, rows in state.get("reference_data", {}).items()})
    return result


def put_opportunity(case: Opportunity) -> dict:
    version = save_case(case)
    return {"opportunity_id": case.opportunity_id, "case_version": version}


def evaluate(opportunity_id: str) -> dict:
    current = get_case(opportunity_id)
    if not current:
        raise KeyError(opportunity_id)
    case, version = current
    old = get_evaluation(opportunity_id)
    if old and old["case_version"] == version:
        return old
    state = evaluate_graph(case.model_dump(mode="json"), version)
    result = _evaluation_result(state, opportunity_id, version)
    save_evaluation(opportunity_id, version, result)
    return get_evaluation(opportunity_id)


def decide(opportunity_id: str, decision: Decision) -> dict:
    current = get_case(opportunity_id)
    if not current:
        raise KeyError(opportunity_id)
    if current[1] != decision.case_version:
        raise ValueError("Stale case version")
    evaluation = get_evaluation(opportunity_id)
    if not evaluation:
        raise ValueError("Case must be evaluated first")
    if decision.decision == "approve" and (decision.reviewer_role != "sme" or
                                            evaluation["result"].get("assigned_sme") != decision.reviewer_id):
        raise ValueError("Approval requires the assigned SME identity")
    recorded = get_approval(opportunity_id)
    if recorded:
        if (recorded["case_version"], recorded["decision"], recorded["reviewer_id"]) != (decision.case_version, decision.decision, decision.reviewer_id):
            raise ValueError("Review already decided")
        completed = get_evaluation(opportunity_id)
        if completed and completed["review_status"] != "pending":
            return completed
    else:
        record_decision(opportunity_id, decision)
    state = resume_graph(opportunity_id, decision.case_version, decision.decision)
    result = _evaluation_result(state, opportunity_id, decision.case_version, evaluation["result"])
    save_evaluation(opportunity_id, decision.case_version, result, state["review_status"])
    return get_evaluation(opportunity_id)


def detail(opportunity_id: str) -> dict:
    current = get_case(opportunity_id)
    if not current:
        raise KeyError(opportunity_id)
    case, version = current
    return {"case": case.model_dump(mode="json"), "case_version": version,
            "evaluation": get_evaluation(opportunity_id),
            "approval": get_approval(opportunity_id), "audit_events": audit_events(opportunity_id),
            "outcomes": get_outcomes(opportunity_id)}


def record_outcome(opportunity_id: str, outcome: Outcome) -> dict:
    add_outcome(opportunity_id, outcome)
    return {"opportunity_id": opportunity_id, "recorded": True}


def approved_summary(opportunity_id: str) -> dict:
    current = get_case(opportunity_id)
    if not current:
        raise KeyError(opportunity_id)
    case, version = current
    evaluation = get_evaluation(opportunity_id)
    approval = get_approval(opportunity_id)
    fresh = assess(case, evidence_max_age_days=settings.evidence_max_age_days)
    if not evaluation or evaluation["case_version"] != version or evaluation["review_status"] != "approved":
        raise ValueError("No current approved evaluation")
    if not approval or approval["case_version"] != version or approval["decision"] != "approve":
        raise ValueError("No current human approval")
    if fresh["blockers"]:
        raise ValueError("Policy blockers: " + ", ".join(fresh["blockers"]))
    summary = evaluation["result"].get("approved_summary")
    if not summary:
        raise ValueError("Approved internal summary is missing")
    return summary


def metrics() -> dict:
    rows = list_cases()
    return {"total": len(rows),
            "source_sales_stages": dict(Counter(r["case"]["source_sales_stage"] for r in rows)),
            "practices": dict(Counter(r["case"]["practice"] for r in rows)),
            "review_statuses": dict(Counter(r["review_status"] for r in rows)),
            "risk_bands": dict(Counter(r["evaluation"]["risk_band"] for r in rows if r["evaluation"])),
            "priorities": dict(Counter(r["evaluation"]["priority"] for r in rows if r["evaluation"])),
            "note": "Savings are case-level, evidence-bound estimates; synthetic data is labeled per case."}
