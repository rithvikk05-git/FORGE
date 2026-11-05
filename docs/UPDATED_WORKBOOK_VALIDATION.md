# Updated 26-column workbook validation

> Historical validation of the previous `FORGE-POC-...` workbook. The active final `SOC-...` workbook is documented in [Final source and flow](FINAL_SOURCE_AND_FLOW.md).

**Checked:** 4 November 2026. The source is the user's `FORGE_60_Opportunities_26_Column_Agent_Input.xlsx` in Downloads. A byte-identical copy is stored at `data/private/FORGE_60_Opportunities_26_Column_Agent_Input.xlsx`; `data/private/` is ignored by Git. The original Downloads file was not edited.

The updated workbook is the **active local POC source**. It has eight sheets: `Opportunity_Input`, `_Lists`, `Contracts`, `FinOps_Evidence`, `Existing_Opportunities`, `SME_Directory`, `Field_Dictionary`, and `Read_Me`. All source records are explicitly described in the workbook as fictional. The old eight-column workbook and generated reference files have been removed; the default SQLite and graph files end in `_26.sqlite`.

| Check | Result |
| --- | --- |
| Intake shape | 60 rows, 26 exact columns, 60 unique IDs. |
| Practice coverage | Six current practice labels; exactly ten rows each. |
| Source stages | Identified 18, Noticed 22, Qualified 14, Validated 6. No `Won` rows. |
| Required input | No blank required cells. Evidence ID is intentionally blank in six rows. |
| Contracts | 60 unique contract IDs; all 60 customer joins valid; date order valid; none expired at validation. Seven optimizations are excluded by their contracts. |
| Evidence | 54 unique records; all 54 linked IDs, opportunity IDs, customer numbers, asset groups, and observed baselines match. Three evidence periods are stale under the current 180-day POC rule. |
| Existing opportunities | 11 reference rows: six active and five closed. Six intake rows exactly match an active reference. Closed rows do not block as duplicates. |
| Finance | All monthly and one-time cost cells are numeric and nonnegative; baselines are positive. Two proposals cost more than baseline and are flagged as unfavorable arithmetic. |
| Workbook SME tab | 12 entries, 11 active. This original tab is validated as provenance; the separate 60-person CSV now supplies active SME recommendations. |
| CSV comparison | The provided 26-column CSV contains the same 60 IDs and no differing intake-cell values compared with the Excel sheet. The Excel adds reference tabs, so it is the active source. |
| Policy result with new SME CSV | 24 of 60 cases have no current hard blockers under the local synthetic POC assumptions. Others can have more than one blocker. Counts can change as evidence ages. |

**Appropriate corrections made in the project:**

1. Added a strict importer for the 26-column sheet and its reference tabs, including cross-sheet joins, money/date checks, and source provenance. The workbook's data cells were not changed because the audit found no broken links or invalid required values.
2. Updated the active configuration to the private workbook and new `_26.sqlite` paths. This prevents mixing its entirely different `FORGE-...` IDs with the earlier catalog.
3. Replaced the tracked `data/opportunity_summary.csv` containing old 50-case rows with a six-row, aggregate practice/stage summary. Restored the complete 26-column CSV as ignored `data/private/opportunity_details.csv` for internal inspection. Its 60 IDs, headers, and cells match the workbook; it is not exposed in the client dashboard.
4. Preserved intentional negative scenarios: blank evidence, contract exclusions, active duplicates, unfavorable costs, high service criticality, stale evidence, and unavailable skills. They become policy blockers instead of being silently repaired.
5. Mapped `Customer` to the customer field of the **internal** Excel exporter. The aggregate-only client dashboard still reads only `/api/metrics` and displays no opportunity identifiers or names.

**Interpretation:** The workbook's source and reference tabs are fictional POC data, not actual verified customer costs, contract permissions, SME commitments, or revenue. `verified=True` in an imported evidence object means that its synthetic baseline matches its linked synthetic evidence record; it does not establish real-world verification. The importer assigns POC risk inputs from criticality and environment. SME matching uses the explicit specialization map, matching practice and service type, and CSV availability status. No data is sent to GTM, CRM, email, or other external systems.

**Commands:** From the inner `FORGE-` folder, run `.\.venv\Scripts\python.exe scripts\build_summary.py`, `.\.venv\Scripts\python.exe scripts\seed_db.py --source workbook`, and `.\.venv\Scripts\python.exe -m pytest -q`. The source copy must already be present in `data/private/`.

**Verification completed:** The Downloads workbook and private copy have the same SHA-256 hash (`5F331CE995E3601E87FC3A2CA66535F0C7B6D1DDCE9DA591161D2F7B538323DF`). The separate SME CSV was copied byte for byte and validated as described in [SME validation](SME_DIRECTORY_VALIDATION.md). The local database seeded all 60 cases. The cleaned suite passed 37 tests. An earlier live FastAPI smoke returned health `ok` and the expected 60-case practice/stage aggregates; the dashboard rendered the 60 total, one chat input, and no data tables. Manual Excel and browser visual checks remain.
