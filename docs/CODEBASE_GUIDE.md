# FORGE codebase guide

> File-purpose explanations remain useful, but earlier case IDs, counts, and sample outputs below describe the superseded catalog. Use [Final source and flow](FINAL_SOURCE_AND_FLOW.md) for current commands and expected results.

This guide is for a teammate learning Python. Start with `scripts/check_data.py`, then `app/workbook_26.py`, `app/sme_directory.py`, and `app/policy_engine.py`. The API and LangGraph files connect those pieces. The only active catalog is the fictional 60-opportunity workbook plus the separate fictional 60-person SME CSV.

## What happens when the project runs

```text
Private workbook + private SME CSV
        ↓ validate and join
60 opportunity cases in SQLite
        ↓ evaluate one case
LangGraph: intake → assessment → pause for human review
        ↓ reviewer decides
Recheck policy → approved internal result, HOLD, rejection, or change request

FastAPI /api/metrics → aggregate Streamlit dashboard + local chatbot
```

The client dashboard never requests opportunity rows or SME profiles. All data stays local. Qdrant is optional and is not needed for the workflow above.

## Files under `app/`

| File | What it does |
| --- | --- |
| `app/__init__.py` | Marks `app` as a Python package. |
| `app/config.py` | Reads local paths, policy age limit, optional Qdrant URL, and reviewer credentials from environment variables. |
| `app/schemas.py` | Defines the allowed shape of an opportunity, evidence, contract, SME, and review decision using Pydantic. Bad or missing values fail here. |
| `app/workbook_26.py` | Reads the 26-column workbook, checks its tabs and references, and turns each row into an `Opportunity`. |
| `app/sme_directory.py` | Reads and validates the 60-person CSV. Its `MATCHING_RULES` explicitly connect optimization codes to SME specializations. It filters by practice and service type, then ranks candidates. |
| `app/policy_engine.py` | Plain Python functions for savings, contract scope, exact duplicates, SME selection, risk score, priority, and blockers. `assess()` combines them. |
| `app/db.py` | Creates SQLite tables and provides database connections and transactions. |
| `app/repositories.py` | Saves and reads cases, evaluations, decisions, outcomes, and append-only audit events. Case versions prevent stale approvals. |
| `app/models.py` | Names the fields passed between LangGraph steps and the review-status constants. |
| `app/graph.py` | Connects intake, assessment, human review, final recheck, and approved result. Stores graph checkpoints in local SQLite. |
| `app/services.py` | Coordinates the graph and database for import, evaluation, decision, detail, metrics, outcomes, and approved summaries. |
| `app/api.py` | FastAPI entry point (`app.api:app`). Defines `/health`, `/api/metrics`, and the internal opportunity and review routes. |

### Files under `app/agents/`

These are small **workflow steps**, not LLMs. `app/agents/__init__.py` marks the package. `intake.py` validates the case, `assessment.py` calls the policy, `review.py` pauses for a human decision, and `result.py` formats an approved internal summary. `sme_matching.py` returns up to three scored recommendations from the synthetic directory. `feasibility.py` uses the existing policy factors to explain technical and delivery feasibility. `risk.py` and `consolidation.py` remain TODO stubs. `graph.py` does not call these new agent steps yet.

## Files under `dashboard/`

| File | What it does |
| --- | --- |
| `dashboard/streamlit_app.py` | Client page with total counts, stage/risk/priority charts, and a local rules-based chatbot. It requests only `/api/metrics`. |
| `dashboard/excel_export.py` | Creates an internal Excel assessment from a case detail record. It is not a client dashboard control. |
| `dashboard/templates/sales_opportunity_template.xlsx` | Blank styled Excel template used by the exporter. |
| `dashboard/exports/` | Local output folder created by `scripts/export_approved.py`; ignored by Git. |

## Data files

| File | What it contains |
| --- | --- |
| `data/private/FORGE_60_Opportunities_26_Column_Agent_Input.xlsx` | Active private workbook, copied unchanged from Downloads: 60 opportunities plus contract, evidence, pipeline, and reference tabs. |
| `data/private/Kyndryl_Synthetic_SME_Directory_60.csv` | Active private SME source, copied unchanged from Downloads: 60 fictional specialists. |
| `data/private/opportunity_details.csv` | Full 60-row, 26-column opportunity view for internal inspection; validated against the active workbook. The importer reads the workbook. |
| `data/opportunity_summary.csv` | Six safe aggregate rows by practice and stage, generated from the active workbook. No opportunity names or IDs. |
| `runtime/forge_26.sqlite`, `runtime/langgraph_26.sqlite` | Generated local business data and LangGraph checkpoints; ignored by Git. |

## Files under `scripts/`

| File | When to use it |
| --- | --- |
| `scripts/check_data.py` | First check. Validates both active source files, prints counts and blockers, and suggests one clear internal demo case and its SME reviewer ID. |
| `scripts/build_summary.py` | Rebuilds the six-row aggregate `data/opportunity_summary.csv`. |
| `scripts/seed_db.py` | Imports all 60 workbook cases and their SME matches into SQLite. Run after source or matching-rule changes. |
| `scripts/export_approved.py` | Saves one already-approved case as `dashboard/exports/<ID>.xlsx`. Refuses unapproved or blocked cases. |
| `scripts/index_vectors.py` | Optional local Qdrant precedent indexing; the core POC does not need it. |
| `scripts/sanitize_sales_template.ps1` | Historical PowerShell helper used to make the blank Excel template. Do not rerun for ordinary use. |

## Tests and project files

| File | Purpose |
| --- | --- |
| `tests/conftest.py` | Gives each integration test its own temporary SQLite files and synthetic case. |
| `tests/test_updated_workbook.py` | Verifies the active workbook and joins, plus a broken-reference rejection. |
| `tests/test_sme_directory.py` | Verifies 60 SME profiles, actual matching, and duplicate-ID rejection. |
| `tests/test_sme_matching_agent.py` | Verifies scored SME recommendations, missing fields, unavailable candidates, and technical skill evidence. |
| `tests/test_feasibility_agent.py` | Verifies policy-consistent feasibility scoring, delivery constraints, missing inputs, and no-SME handling. |
| `tests/test_schema.py` | Checks Pydantic input validation. |
| `tests/test_risk.py`, `tests/test_contract.py`, `tests/test_duplicates.py` | Check policy gates, scores, contracts, and exact duplicates. |
| `tests/test_graph.py`, `tests/test_handoff.py` | Check review pause/resume, decisions, and internal approved result. `test_handoff.py` is a historical filename; it does not send data to GTM. |
| `tests/test_api.py`, `tests/test_dashboard.py` | Check internal API and aggregate chatbot behavior. |
| `tests/test_excel_export.py` | Reads a generated Excel file back and checks mapped cells. |
| `requirements.txt` | Packages needed for API, graph, dashboard, Excel, and tests. |
| `requirements-vectors.txt`, `compose.yaml` | Optional vector packages and local Qdrant container setup. |
| `.env.example` | Names and example values for configuration; Python does not load it automatically. |
| `.gitignore` | Keeps private data, secrets, SQLite files, exports, and virtual environment out of Git. |
| `README.md` | Short setup and run instructions. |
| `LICENSE` | Repository license. |

The `docs/` folder contains this guide; `IMPLEMENTATION_PLAN.md` and `PROJECT_ROADMAP.md` explain run order and phases; `POLICY_SPEC.md` lists the exact POC rules; `DATA_DICTIONARY.md` defines fields; `UPDATED_WORKBOOK_VALIDATION.md` and `SME_DIRECTORY_VALIDATION.md` record source checks; `TEST_MATRIX.md` records verification; `AZURE_MIGRATION.md` is future planning only.

## Commands to run, in order

Open **PowerShell** in VS Code and enter the inner project folder:

```powershell
cd "C:\Users\PranavkrishnaKondapa\OneDrive - kyndryl\Desktop\FORGE\FORGE-"
```

If `.venv` already exists, use it. Otherwise create it with Python 3.12 and install packages:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Check data, build the safe summary, import cases, and run tests:

```powershell
.\.venv\Scripts\python.exe scripts\check_data.py
.\.venv\Scripts\python.exe scripts\build_summary.py
.\.venv\Scripts\python.exe scripts\seed_db.py --source workbook
.\.venv\Scripts\python.exe -m pytest -q
```

On 4 November 2026, `check_data.py` prints **60 opportunities**, **60 synthetic SMEs**, **24 cases with no current blockers**, and **7 SME_UNAVAILABLE**. The counts can change if evidence becomes stale. `seed_db.py` prints `"imported": 60` and `"sme_directory_source": "Kyndryl_Synthetic_SME_Directory_60.csv"`. The cleaned test suite prints `37 passed`.

Start the API in terminal 1. Use the reviewer ID printed by `check_data.py` for the case you intend to approve; the current suggested case uses `SME-010`:

```powershell
$env:FORGE_SME_TOKEN = "choose-a-long-local-test-secret"
$env:FORGE_SME_REVIEWER_ID = "SME-010"
.\.venv\Scripts\python.exe -m uvicorn app.api:app --host 127.0.0.1 --port 8000
```

Keep that terminal open. Open `http://127.0.0.1:8000/health` and `http://127.0.0.1:8000/docs`. Health should say `status: ok`, `source_workbook_present: true`, and `sme_directory_present: true`. Qdrant may be unavailable; the core checks still run.

Open a **second** PowerShell terminal in `FORGE-` and start the dashboard:

```powershell
.\.venv\Scripts\python.exe -m streamlit run dashboard\streamlit_app.py --server.address 127.0.0.1 --server.port 8501
```

Open `http://127.0.0.1:8501`. The client page should show **60 total opportunities**, source-stage bars (18 Identified, 22 Noticed, 14 Qualified, 6 Validated), review/risk/priority counts, and a chatbot. Right after seeding, all 60 are `not_evaluated`, so assessed and risk counts start at zero. The page has no opportunity list or SME names.

For an **internal** review demo, use `/docs`: call `POST /api/opportunities/FORGE-POC-ADAI-001/evaluate`, copy its `case_version`, then call `POST /api/reviews/FORGE-POC-ADAI-001/decision` with `X-Reviewer-Token` set to the token above and this JSON (paste the actual version in place of the text):

```json
{
  "decision": "approve",
  "reviewer_id": "SME-010",
  "reviewer_role": "sme",
  "case_version": "PASTE_CASE_VERSION_HERE",
  "comments": "Synthetic POC review complete"
}
```

The internal result endpoint then returns an approved summary. To save its Excel file:

```powershell
.\.venv\Scripts\python.exe scripts\export_approved.py FORGE-POC-ADAI-001
```

The file appears under `dashboard/exports/`. `export_approved.py` refuses a case without a current human approval or with policy blockers. New evaluations change dashboard aggregate counts. Stop the servers with `Ctrl+C` in each terminal.

## What the project produces

- A local SQLite catalog of **60 fictional opportunities**, with specialist matches drawn from the **60-person fictional SME CSV**.
- For each evaluated case: savings calculations, risk score/band, priority, assigned SME or blocker, and an audit trail.
- A local dashboard with aggregate metrics and a simple chatbot, without client-visible opportunity details.
- After human approval of a clear case: an internal JSON summary and an Excel assessment.
- No GTM, CRM, email, or external data transfer.
