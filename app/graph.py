
"""LangGraph workflow with durable local SQLite checkpoints."""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

from .agents import (assessment, consolidation, feasibility, intake, result,
                     review, risk, sme_matching)
from .config import settings
from .models import GraphState
from .policy_engine import assess
from .repositories import get_approval, get_case


def final_validation(state: GraphState) -> dict:
    current = get_case(state["opportunity_id"])
    if current is None or current[1] != state["case_version"]:
        return {"review_status": "stale", "trace": state.get("trace", []) + ["final: case version changed"]}
    assessment = assess(current[0], evidence_max_age_days=settings.evidence_max_age_days)
    approval = get_approval(state["opportunity_id"])
    approved = bool(approval and approval["case_version"] == state["case_version"] and approval["decision"] == "approve")
    status = "approved" if approved and not assessment["blockers"] else "hold" if approved else state.get("review_status", "pending")
    return {"case": current[0].model_dump(mode="json"), "assessment": assessment,
            "approval": approval, "review_status": status,
            "trace": state.get("trace", []) + ["final: current approval and all gates rechecked"]}


def route_final(state: GraphState) -> str:
    return "approved_result" if state.get("review_status") == "approved" else "finish"


def checked_agent(name: str, runner, output_key: str):
    """Report agent failures and reject missing or mismatched state updates."""
    def node(state: GraphState) -> dict:
        try:
            update = runner(state)
        except Exception as exc:
            raise ValueError(f"{name} failed: {exc}") from exc
        output = update.get(output_key) if isinstance(update, dict) else None
        if not isinstance(output, dict) or output.get("opportunity_id") != state["opportunity_id"]:
            raise ValueError(f"{name} did not return {output_key} for {state['opportunity_id']}")
        return update
    return node


def build_analysis_graph():
    """Run one opportunity through the four analysis agents, then stop."""
    g = StateGraph(GraphState)
    g.add_node("sme_matching", checked_agent("SME Matching", sme_matching.run, "sme_matching"))
    g.add_node("feasibility", checked_agent("Feasibility", feasibility.run, "feasibility"))
    g.add_node("risk", checked_agent("Risk", risk.run, "risk_assessment"))
    g.add_node("consolidation", checked_agent("Consolidation", consolidation.run, "consolidation"))
    g.add_edge(START, "sme_matching")
    g.add_edge("sme_matching", "feasibility")
    g.add_edge("feasibility", "risk")
    g.add_edge("risk", "consolidation")
    g.add_edge("consolidation", END)
    return g.compile()


def build_graph(checkpointer):
    """Keep the existing durable policy and review steps around analysis."""
    g = StateGraph(GraphState)
    g.add_node("intake", intake.run)
    g.add_node("assessment", assessment.run)
    g.add_node("analysis", build_analysis_graph())
    g.add_node("review", review.run)
    g.add_node("final_validation", final_validation)
    g.add_node("approved_result", result.run)
    g.add_edge(START, "intake")
    g.add_edge("intake", "assessment")
    g.add_edge("assessment", "analysis")
    g.add_edge("analysis", "review")
    g.add_edge("review", "final_validation")
    g.add_conditional_edges("final_validation", route_final,
                            {"approved_result": "approved_result", "finish": END})
    g.add_edge("approved_result", END)
    return g.compile(checkpointer=checkpointer)


@contextmanager
def graph_session():
    settings.checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(settings.checkpoint_path, check_same_thread=False)
    try:
        yield build_graph(SqliteSaver(connection))
    finally:
        connection.close()


def thread_config(opportunity_id: str, version: str) -> dict:
    return {"configurable": {"thread_id": f"{opportunity_id}:{version}"}}


def evaluate_graph(case: dict, version: str) -> dict:
    with graph_session() as graph:
        return graph.invoke({"opportunity_id": case["opportunity_id"], "case": case,
                             "case_version": version, "review_status": "pending",
                             "approval": None, "approved_summary": None, "trace": []},
                            thread_config(case["opportunity_id"], version))


def resume_graph(opportunity_id: str, version: str, decision: str) -> dict:
    with graph_session() as graph:
        return graph.invoke(Command(resume={"decision": decision}), thread_config(opportunity_id, version))
