# Test matrix and status

> Historical test snapshot for the previous catalog. See [Final source and flow](FINAL_SOURCE_AND_FLOW.md) for the active `SOC-...` workbook and current checks.

On 4 November 2026, `.\.venv\Scripts\python.exe -m pytest -q --tb=line` completed with **37 passed** on Python 3.12.16. The updated workbook and 60-person SME CSV both passed validation.

| Area | Verified | Remaining |
| --- | --- | --- |
| Updated source | Exact 26-column header; 60 unique IDs; six practices × 10; stages 18/22/14/6; full contract/evidence/pipeline/SME joins; malformed evidence reference rejected. | Recheck if source workbook changes. |
| Data quality | 60 contracts, 54 evidence rows, 11 pipeline rows, and 60 active CSV SMEs; numeric costs and date order valid. Intentional missing evidence, exclusions, duplicates, stale evidence, unfavorable cost, and unavailable skill retained. | Review POC thresholds with project owner before any real-data use. |
| SME matching | 60 IDs, ten people per practice, availability counts, domain aliases, live workbook matches, and duplicate-ID rejection tested. A matched SME completed an internal review and Excel export in an isolated integration test. | Review the explicit specialty map if the source data changes. |
| SME Matching Agent | Deterministic top-three ranking, score breakdown, reasons, missing fields, unavailable candidates, and technical skill evidence tested. | Wire the agent into LangGraph in a later phase. |
| Feasibility Agent | Existing policy weights and factors, score arithmetic, delivery constraints, missing inputs, and no-SME uncertainty tested with synthetic opportunities. | Wire the agent into LangGraph in a later phase. |
| Catalog isolation | New default `_26.sqlite` paths; importer rejects a database containing other opportunity IDs. | Source-control check before commit. |
| Policy and review | Finance, risk, blockers, human decisions, stale case version, audit, and checkpoint reopen covered. | Rehearse selected new IDs through internal API. |
| API | Health, import, evaluation, decisions, metrics, and internal output guards covered by automated tests. Live localhost health and metrics returned 60 cases with the expected stage/practice counts. | Rehearse authorized decisions using the new IDs. |
| Client dashboard | Automated rendering and privacy tests verify aggregate view and local chat, without case list or selectors. AppTest against the live API showed the 60 total, one chat input, and no tables or dataframes. | Manual browser visual check. |
| Excel | Automated export/read-back checks template mapping and output. | Open a generated workbook in Excel and inspect formulas/layout. |
| Optional Qdrant | Core API works without it. | Local vector demonstration only if needed. |

Run `.\.venv\Scripts\python.exe -m pytest -q` after later changes. Keep the private workbook, SME CSV, SQLite, and credentials out of Git.
