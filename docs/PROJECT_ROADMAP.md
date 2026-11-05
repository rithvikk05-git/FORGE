# FORGE project roadmap

> Historical planning snapshot for the earlier `FORGE-POC-...` catalog. For the active final `SOC-...` workbook, current counts, and verification steps, see [Final source and flow](FINAL_SOURCE_AND_FLOW.md).

**Status:** 4 November 2026. **Goal:** a local, demo-ready FinOps assessment POC using the user's updated 60-opportunity fictional workbook and 60-person synthetic SME CSV. The client page shows aggregate metrics and a simple chatbot. Internal case evaluation, human decisions, and exports stay outside that page. FORGE sends no data to GTM, CRM, email, or customer systems.

## Source and boundaries

`data/private/FORGE_60_Opportunities_26_Column_Agent_Input.xlsx` is the active 26-column source. Its contract, evidence, and existing-opportunity tabs are joined by validated keys. The active specialist source is `data/private/Kyndryl_Synthetic_SME_Directory_60.csv`. The workbook and SQLite databases stay local and ignored by Git. `data/opportunity_summary.csv` contains six aggregate practice rows. The earlier catalogs and their files were removed. Source sales stage and FORGE human-review status are separate fields. All financial, contract, and SME records are fictional POC data.

## Phase position

| Phase | Deliverable | Status |
| --- | --- | --- |
| 1. Environment | Python, VS Code, local configuration | `.venv` Python 3.12.16 working; Git executable still unavailable in this shell. |
| 2. Source data | 60 fictional opportunities and references | Updated workbook copied privately; all 60 IDs unique and six practices have ten cases each. |
| 3. Ingestion | Validated Pydantic input and joins | 26-column importer checks headers, required values, contracts, evidence, pipeline, SME, money, and dates. |
| 4. FinOps | Evidence and savings calculations | Implemented for the synthetic data; missing, stale, or unfavorable evidence remains visible. |
| 5. Contract and duplicates | Scope and exact pipeline checks | Implemented; seven exclusions and six active exact matches present. |
| 6. Policy | Risk, feasibility, priority, hard gates | Implemented as explicit POC rules; 24 cases currently have no hard blocker. |
| 7. SME routing | Explainable practice, specialty, service, and availability match | Implemented with the 60-person CSV; seven cases currently have no assignable SME. |
| 8. LangGraph | Intake, policy assessment, review pause, final recheck, internal result | Simplified to real workflow steps with SQLite checkpoints. |
| 9. Human review | Authenticated decision and audit | Implemented and tested, including stale-version safeguards. |
| 10. Local app | FastAPI, aggregate Streamlit, internal Excel | Implemented; final manual visual check remains. |
| 11. Storage and vectors | SQLite, optional Qdrant | New `_26.sqlite` business/checkpoint paths active; Qdrant optional and not yet demonstrated. |
| 12. Containers | Reproducible optional infrastructure | Local compose file exists for Qdrant; Podman run remains optional. |
| 13. Final validation | Regression, user journey, Azure preparation | 37 active-catalog tests passed after legacy cleanup; the local API previously returned 60 cases with an explained SME match. Browser and Excel visual checks, source-control review, and demo rehearsal remain. Azure is documentation only. |

## Path to the endpoint

1. Run `scripts/build_summary.py`, `scripts/seed_db.py --source workbook`, and `pytest -q` with `.venv`. The seed must report 60 cases and the test suite must pass.
2. Start FastAPI and Streamlit as shown in [the implementation plan](IMPLEMENTATION_PLAN.md). Check aggregate totals and chatbot without exposing row-level data on the client page.
3. Through the internal API, evaluate a clear case, record an authorized human decision, and verify audit and internal Excel/JSON outputs. Repeat with blocked and request-changes cases. Restart the API once to confirm persistence.
4. Open an internal Excel output in Excel and inspect its visible labels, mapped cells, and formulas. Inspect VS Code Source Control so no private source, database, or secret is staged.
5. Rehearse the fixed demo. Optional Qdrant similarity search is a later enhancement; it must never override exact policy checks or human approval.

**Endpoint:** another person can follow the local commands, see only aggregate client metrics, use the chatbot, reproduce normal and blocked internal cases, and obtain correctly labeled internal outputs without transferring data outside FORGE.

See [validation findings](UPDATED_WORKBOOK_VALIDATION.md), [data dictionary](DATA_DICTIONARY.md), [policy](POLICY_SPEC.md), and [test matrix](TEST_MATRIX.md).
