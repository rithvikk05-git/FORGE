"""Aggregate-only client dashboard with a local, deterministic help chatbot."""
from __future__ import annotations

import os
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
import json

import streamlit as st

API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")

STAGES = ("Identified", "Noticed", "Qualified", "Validated", "Won", "Stretch")
PRIORITIES = ("P1", "P2", "P3", "HOLD")
RISKS = ("LOW", "MEDIUM", "HIGH", "CRITICAL")


def fetch_metrics() -> dict:
    """Fetch aggregates only; this client never requests individual opportunities."""
    request = Request(API_BASE_URL + "/api/metrics", headers={"Accept": "application/json"})
    try:
        with urlopen(request, timeout=10) as response:
            result = json.load(response)
    except HTTPError as exc:
        raise RuntimeError(f"Metrics API returned HTTP {exc.code}") from exc
    except (URLError, TimeoutError) as exc:
        raise RuntimeError("Cannot reach the local FORGE metrics API") from exc
    if not isinstance(result, dict):
        raise RuntimeError("The metrics API returned an invalid response")
    return result


def count(values: dict | None, key: str) -> int:
    value = (values or {}).get(key, 0)
    return max(0, int(value)) if isinstance(value, (int, float)) and not isinstance(value, bool) else 0


def answer_question(question: str, metrics: dict) -> str:
    """Answer aggregate and workflow questions without reading case-level data."""
    q = question.strip().lower()
    statuses = metrics.get("review_statuses") or {}
    stages = metrics.get("source_sales_stages") or {}
    risks = metrics.get("risk_bands") or {}
    priorities = metrics.get("priorities") or {}
    total = count(metrics, "total")
    assessed = max(0, total - count(statuses, "not_evaluated"))

    if re.search(r"\b(customer|account|individual|opportunity id|case id|names?|ids?)\b", q) or \
            "which opportunit" in q or "list of opportunit" in q or "case detail" in q:
        return "This client view shows aggregate metrics only. Individual opportunity records and identifiers are not available here."
    if any(word in q for word in ("saving", "revenue", "value", "amount")):
        return "I do not show portfolio savings or revenue totals. The current POC uses synthetic financial evidence, so those figures must not be presented as customer results."
    if "risk" in q:
        return (f"Risk bands among {assessed} assessed opportunities: " +
                ", ".join(f"{label} {count(risks, label)}" for label in RISKS) +
                ". Unevaluated opportunities have no risk score yet.")
    if any(word in q for word in ("priority", "queue", "p1", "p2", "p3", "hold")):
        return ("Current priority queue: " +
                ", ".join(f"{label} {count(priorities, label)}" for label in PRIORITIES) +
                ". These counts include evaluated opportunities only.")
    if any(word in q for word in ("review", "pending", "approv", "reject", "sme")):
        return (f"Reviews: {count(statuses, 'pending')} pending, {count(statuses, 'approved')} approved internally, "
                f"{count(statuses, 'changes_requested')} awaiting changes, and {count(statuses, 'rejected')} rejected. "
                "A human reviewer makes every decision.")
    if any(word in q for word in ("stage", "won", "identified", "noticed", "qualified", "validated", "stretch")):
        return "Source sales stages: " + ", ".join(f"{label} {count(stages, label)}" for label in STAGES if count(stages, label)) + ". These are not FORGE review decisions."
    if any(word in q for word in ("total", "many", "count", "portfolio", "opportunit", "assess")):
        return f"The portfolio has {total} opportunities. {assessed} have been assessed and {max(0, total - assessed)} have not yet been assessed."
    if any(word in q for word in ("how", "works", "forge", "help")):
        return "FORGE checks evidence, contract scope, duplicates, feasibility, risk, and SME availability. A human review follows. This dashboard shares only aggregate POC metrics."
    return "Ask me about portfolio totals, source stages, risk bands, priority, review status, or how FORGE works. I cannot show individual records."


def _card(label: str, value: int, detail: str, accent: bool = False) -> None:
    style = " forge-card-accent" if accent else ""
    st.markdown(
        f'<div class="forge-card{style}"><div class="forge-card-label">{label}</div>'
        f'<div class="forge-card-value">{value}</div><div class="forge-card-detail">{detail}</div></div>',
        unsafe_allow_html=True,
    )


def _bars(title: str, subtitle: str, values: dict, labels: tuple[str, ...], color: str) -> None:
    maximum = max((count(values, label) for label in labels), default=0)
    rows = []
    for label in labels:
        value = count(values, label)
        width = round(100 * value / maximum) if maximum else 0
        rows.append(
            f'<div class="forge-bar-row"><span>{label}</span><strong>{value}</strong></div>'
            f'<div class="forge-track"><div style="width:{width}%;background:{color}"></div></div>'
        )
    st.markdown(
        f'<section class="forge-panel"><div class="forge-panel-title">{title}</div>'
        f'<div class="forge-panel-subtitle">{subtitle}</div>{"".join(rows)}</section>',
        unsafe_allow_html=True,
    )


def _theme() -> None:
    st.markdown("""
    <style>
      :root { --forge-bg:#07111f; --forge-panel:#0d1b30; --forge-line:#253650;
              --forge-orange:#f66b12; --forge-text:#f5f7fc; --forge-muted:#a9b8cf; }
      [data-testid="stAppViewContainer"] { background:radial-gradient(circle at 88% 4%, #172848 0, #07111f 43%); color:var(--forge-text); }
      [data-testid="stHeader"] { background:transparent; }
      .block-container { max-width:1240px; padding-top:2.2rem; padding-bottom:3rem; }
      #MainMenu, footer { visibility:hidden; }
      .forge-hero { padding:1.7rem 2rem; border-radius:20px; border:1px solid #35425a;
                    background:linear-gradient(120deg,#0a1730 0%,#111f39 72%,#302119 100%);
                    box-shadow:0 18px 45px rgba(0,0,0,.18); margin-bottom:1.25rem; }
      .forge-eyebrow { color:var(--forge-orange); font-size:.76rem; font-weight:800; letter-spacing:.18em; text-transform:uppercase; }
      .forge-hero h1 { color:#fff; font-size:2.55rem; line-height:1.05; margin:.5rem 0; font-weight:850; }
      .forge-hero p { color:#c9d4e6; font-size:1rem; margin:0; max-width:760px; }
      .forge-divider { width:74px; height:4px; border-radius:8px; background:var(--forge-orange); margin:.9rem 0 0; }
      .forge-section { color:#f6f8fd; font-size:1.25rem; font-weight:750; margin:.5rem 0 .75rem; }
      .forge-card { min-height:136px; padding:1.1rem 1.2rem; border-radius:17px; border:1px solid var(--forge-line);
                    background:linear-gradient(145deg,#11223a,#0c192c); margin-bottom:.55rem; }
      .forge-card-accent { border-color:#8b4a23; background:linear-gradient(145deg,#30251f,#1c1c29); }
      .forge-card-label { color:#bfcbdd; font-size:.81rem; font-weight:700; }
      .forge-card-value { color:#fff; font-size:2.45rem; line-height:1.2; font-weight:850; margin:.35rem 0; }
      .forge-card-accent .forge-card-value { color:#ff8a38; }
      .forge-card-detail { color:#93a5bf; font-size:.74rem; }
      .forge-panel { min-height:305px; padding:1.3rem 1.5rem; border:1px solid var(--forge-line);
                     border-radius:18px; background:linear-gradient(155deg,#0f213a,#0b182b); margin-bottom:1rem; }
      .forge-panel-title { color:#f5f7fc; font-size:1.08rem; font-weight:750; }
      .forge-panel-subtitle { color:#9eafc7; font-size:.78rem; margin:.2rem 0 1.1rem; }
      .forge-bar-row { display:flex; justify-content:space-between; color:#dbe4f1; font-size:.82rem; margin:.68rem 0 .28rem; }
      .forge-bar-row strong { color:#fff; }
      .forge-track { height:7px; background:#253650; border-radius:9px; overflow:hidden; }
      .forge-track div { height:100%; border-radius:9px; }
      [data-testid="stChatMessage"] { background:#0d1b30; border:1px solid #253650; border-radius:14px; }
      [data-testid="stChatInput"] { border-color:#99501c; }
      [data-testid="stMarkdownContainer"] p { color:#d6e0ee; }
    </style>
    """, unsafe_allow_html=True)


def render() -> None:
    st.set_page_config(page_title="FORGE | Portfolio overview", page_icon="🔶", layout="wide",
                       initial_sidebar_state="collapsed")
    _theme()
    st.markdown(
        '<div class="forge-hero"><div class="forge-eyebrow">FORGE / INTERNAL POC</div>'
        '<h1>Opportunity intelligence</h1>'
        '<p>Portfolio health, risk and review progress at a glance. Individual opportunity records stay off this client dashboard.</p>'
        '<div class="forge-divider"></div></div>', unsafe_allow_html=True,
    )
    if urlsplit(API_BASE_URL).hostname not in {"127.0.0.1", "localhost"}:
        st.error("This POC dashboard requires a local API address.")
        st.stop()
    try:
        metrics = fetch_metrics()
    except RuntimeError as exc:
        st.error(str(exc))
        st.stop()

    statuses = metrics.get("review_statuses") or {}
    total = count(metrics, "total")
    assessed = max(0, total - count(statuses, "not_evaluated"))
    st.markdown('<div class="forge-section">Portfolio overview</div>', unsafe_allow_html=True)
    cards = st.columns(5, gap="small")
    with cards[0]: _card("Total opportunities", total, "Aggregate count only", accent=True)
    with cards[1]: _card("Assessed", assessed, "Policy evaluation complete")
    with cards[2]: _card("Awaiting review", count(statuses, "pending"), "Human decision pending")
    with cards[3]: _card("Approved internally", count(statuses, "approved"), "Local POC decision")
    with cards[4]: _card("On hold", count(statuses, "hold"), "Policy blockers remain")

    left, right = st.columns([1.1, 1], gap="large")
    with left:
        _bars("Source stage mix", "Original workbook stages; separate from FORGE review status",
              metrics.get("source_sales_stages") or {}, tuple(label for label in STAGES if count(metrics.get("source_sales_stages"), label)), "#f66b12")
        _bars("Priority queue", "Evaluated opportunities only",
              metrics.get("priorities") or {}, PRIORITIES, "#f39742")
    with right:
        _bars("Risk distribution", "Evaluated opportunities only",
              metrics.get("risk_bands") or {}, RISKS, "#7594d4")
        st.markdown('<div class="forge-section">Ask FORGE</div>', unsafe_allow_html=True)
        st.caption("Local rules-based assistant · aggregate metrics only · no external AI service")
        if "forge_chat" not in st.session_state:
            st.session_state.forge_chat = [{"role": "assistant", "content":
                "Hi. Ask about totals, source stages, risk, priority or review progress. I cannot show individual records."}]
        with st.container(height=250, border=False):
            for message in st.session_state.forge_chat[-10:]:
                with st.chat_message(message["role"]):
                    st.write(message["content"])
        question = st.chat_input("Ask about portfolio metrics")
        if question:
            st.session_state.forge_chat.append({"role": "user", "content": question[:500]})
            st.session_state.forge_chat.append({"role": "assistant", "content": answer_question(question[:500], metrics)})
            st.rerun()
    st.caption("Synthetic proof-of-concept data. Counts are local aggregates; financial results are not customer claims.")


if __name__ == "__main__":
    render()
