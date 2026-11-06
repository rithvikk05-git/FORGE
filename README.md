# FORGE

FORGE is a local FinOps opportunity assessment proof of concept. Its active source is the **final 60-opportunity SOC workbook**, joined with the separate **60-person synthetic SME CSV**. LangGraph runs SME Matching, Feasibility, Risk, and Consolidation after intake and policy checks. Human review remains explicit. The client dashboard shows aggregate counts and a simple local chatbot.

## Quick run (PowerShell)

Run from the inner `FORGE-` folder with the project's Python 3.12 virtual environment:

```powershell
.\.venv\Scripts\python.exe scripts\check_data.py
.\.venv\Scripts\python.exe scripts\build_summary.py
.\.venv\Scripts\python.exe scripts\seed_db.py --source workbook
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts\trace_flow.py SOC-1F91OWU
.\.venv\Scripts\python.exe scripts\export_draft.py SOC-1F91OWU
```

The data check should report **60 opportunities**, **60 synthetic SMEs**, and **0 cases without current blockers**. The importer should report `"imported": 60`; the suite passes **65 tests**. The private workbook, SME CSV, and full `opportunity_details.csv` stay under ignored `data/private/`. `data/opportunity_summary.csv` contains six aggregate practice rows. `trace_flow.py` prints each agent step and why the sample case needs human review.

Start the API in terminal 1. The example `SOC-1F91OWU` currently matches `SME-003`. Its stale evidence and unverified contract scope keep it on HOLD; do not treat the output as an approval.

```powershell
$env:FORGE_SME_TOKEN = "choose-a-long-local-test-secret"
$env:FORGE_SME_REVIEWER_ID = "SME-003"
.\.venv\Scripts\python.exe -m uvicorn app.api:app --host 127.0.0.1 --port 8000
```

Start the dashboard in terminal 2:

```powershell
.\.venv\Scripts\python.exe -m streamlit run dashboard\streamlit_app.py --server.address 127.0.0.1 --server.port 8501
```

Open `http://127.0.0.1:8000/health`, `http://127.0.0.1:8000/docs`, and `http://127.0.0.1:8501`. In `/docs`, run `POST /api/opportunities/SOC-1F91OWU/evaluate`, then inspect its `trace`, four agent results, `consolidation`, and `review_status`. Qdrant is optional. The API is for local internal use; the client dashboard does not request case or SME rows.

New form opportunities can be submitted through `POST /api/opportunities/form` in `/docs` using the existing Opportunity JSON schema. They are stored in the opportunity list, reflected in aggregate dashboard metrics, and available as context to later agent runs. The graph intake validates and carries JSON-compatible case data with `prompt_template: null`. Four empty local reference files in `data/reference/` are ready for successful projects, cost impact, technical impact, and compliance; see [reference data guide](data/reference/README.md). Agents expose matching source records as evidence without changing their numeric rules. Source-stage `Won` opportunities remain in the intake list and do not enter the successful-project repository automatically. Sales-template email delivery is deferred until a recipient and sending process are defined.

Read [the final source and flow guide](docs/FINAL_SOURCE_AND_FLOW.md) for the current data, policy limits, visual checks, and output path. [The codebase guide](docs/CODEBASE_GUIDE.md) explains file purposes; its earlier dataset counts are historical. No GTM or external handoff runs in this POC.
