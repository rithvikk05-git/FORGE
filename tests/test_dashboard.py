from dashboard.streamlit_app import answer_question


METRICS = {
    "total": 60,
    "review_statuses": {"not_evaluated": 52, "pending": 3, "approved": 2, "hold": 3},
    "source_sales_stages": {"Identified": 10, "Noticed": 13, "Qualified": 7,
                            "Validated": 13, "Won": 17},
    "risk_bands": {"LOW": 4, "MEDIUM": 3, "HIGH": 1},
    "priorities": {"P1": 2, "P2": 3, "HOLD": 3},
}


def test_chatbot_reports_aggregates_without_case_details():
    assert "60 opportunities" in answer_question("How many opportunities?", METRICS)
    assert "P1 2" in answer_question("What is the priority queue?", METRICS)
    assert "individual opportunity records" in answer_question("List the opportunity names", METRICS).lower()
    assert "SOC-SECRET" not in answer_question("Tell me about case ID SOC-SECRET", METRICS)


def test_chatbot_does_not_invent_financial_totals():
    assert "do not show portfolio savings" in answer_question("What are total savings?", METRICS)
