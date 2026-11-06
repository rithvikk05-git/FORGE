# FORGE implementation plan

> Historical implementation snapshot for the earlier `FORGE-POC-...` catalog. See [Final source and flow](FINAL_SOURCE_AND_FLOW.md) for the active `SOC-...` data and current behavior.

FORGE is a local FinOps opportunity assessment POC. It uses the supplied 60-case fictional workbook and 60-person synthetic SME CSV, deterministic checks, LangGraph orchestration, SQLite persistence, and human review. The client Streamlit page shows aggregate metrics and a rules-based chatbot. It does not show opportunity rows or send data to GTM, CRM, email, or customer systems.

## Current state — 4 November 2026

- The active sources are `data/private/FORGE_60_Opportunities_26_Column_Agent_Input.xlsx` and `data/private/Kyndryl_Synthetic_SME_Directory_60.csv`. They hold 60 fictional opportunities and 60 fictional SMEs. `data/private/opportunity_details.csv` is a matching full-row copy for internal inspection. All three are ignored by Git. `data/opportunity_summary.csv` contains only six aggregate rows.
- The importer validates 60 unique IDs, six practices, source stages, contracts, evidence, pipeline references, SME directory, costs, and date integrity. Intentional blockers are retained. See [validation](UPDATED_WORKBOOK_VALIDATION.md).
- The default business and LangGraph SQLite files end in `_26.sqlite`, keeping the new `FORGE-...` IDs apart from the earlier catalog. `scripts/seed_db.py --source workbook` successfully imported all 60.
- `.venv` uses Python 3.12.16. The cleaned suite passed 37 tests. Git executable is unavailable in this shell, so staging status has not been verified here.
- Qdrant remains optional. The template-based Excel exporter remains internal, outside the client dashboard.

## Local run order (PowerShell, from inner `FORGE-`)

```powershell
.\.venv\Scripts\python.exe scripts\build_summary.py
.\.venv\Scripts\python.exe scripts\check_data.py
.\.venv\Scripts\python.exe scripts\seed_db.py --source workbook
.\.venv\Scripts\python.exe -m pytest -q
```

Set reviewer credentials in the terminal where the API will run. `.env.example` lists variable names but is not loaded automatically.

```powershell
$env:FORGE_SME_TOKEN = "choose-a-long-local-test-secret"
$env:FORGE_SME_REVIEWER_ID = "SME-010"
$env:FORGE_GOVERNANCE_TOKEN = "choose-a-different-local-test-secret"
$env:FORGE_GOVERNANCE_REVIEWER_ID = "demo-governance"
.\.venv\Scripts\python.exe -m uvicorn app.api:app --host 127.0.0.1 --port 8000
```

In a second terminal:

```powershell
.\.venv\Scripts\python.exe -m streamlit run dashboard\streamlit_app.py --server.address 127.0.0.1 --server.port 8501
```

Open `http://127.0.0.1:8501` for the aggregate client dashboard, `http://127.0.0.1:8000/health` for API health, and `http://127.0.0.1:8000/docs` for internal API work. Restart previously running servers after changing the source or configuration. The dashboard's lack of row-level controls is a presentation boundary; a remote deployment would need API authentication and authorization.

## Remaining verification

Manually inspect the Streamlit page and a generated internal Excel file in Excel. Rehearse normal, blocked, and request-changes decisions with the current case IDs. Inspect VS Code Source Control before any commit to confirm the private workbook, SME CSV, SQLite files, and secrets are excluded. Optional vector search and Azure deployment are later work.
