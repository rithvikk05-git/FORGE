# Synthetic SME directory: validation and matching

> The 60-person CSV remains active. Opportunity-specific examples and match counts below use the previous workbook; see [Final source and flow](FINAL_SOURCE_AND_FLOW.md) for current `SOC-...` matching results.

**Checked:** 4 November 2026. The user's `Kyndryl_Synthetic_SME_Directory_60.csv` was copied from Downloads to `data/private/Kyndryl_Synthetic_SME_Directory_60.csv` without changing any cell. Both files have SHA-256 `D4E909ADF4A9273899816632473CF0D42CE14234204BBE2B2D22ABED54E30323`. The private folder is ignored by Git. The CSV includes fictional names and account labels, so the client dashboard never reads it.

| Check | Result |
| --- | --- |
| Shape | 60 rows, 20 expected columns, 60 unique SME IDs. |
| Practices | Ten people in each of six domains. `Core Enterprise & zCloud` maps to `Core Enterprise and z/OS`; `Digital Workplace` maps to `Digital Workspace Services`. The source file stays unchanged. |
| Availability | 14 Available, 22 Partially Available, 24 Limited. Status agrees with utilization ranges in this CSV. |
| Numeric fields | Utilization 41–95%; experience, assignments, and ratings parse within valid ranges. |
| Active matching | The updated workbook uses codes such as `vm_rightsizing`; the CSV uses specializations such as `Cloud Optimization`. `app/sme_directory.py` holds an explicit translation for every optimization and practice pair in the current 60 cases. |
| Service fit | A candidate must have the same practice and a compatible `Manage`, `Consult`, or `Both` service type. Industry, utilization, and rating rank valid candidates. |
| Availability rule | Available and Partially Available specialists can be assigned. Limited specialists are visible as candidates but cannot be assigned. |
| Current assessment | 56 cases have at least one specialist candidate; 53 have an assignable specialist; seven receive `SME_UNAVAILABLE`. With all other policy gates, 24 cases currently have no blocker. These counts may change when evidence ages. |

The workbook's own 12-person `SME_Directory` tab is retained for provenance and shape validation, but it does not supply active recommendations. The 60-person CSV is now the active SME source. The match is a **synthetic POC routing rule**. It does not establish a real person's assignment, commitment, or current capacity.

Run `.\.venv\Scripts\python.exe scripts\check_data.py` from `FORGE-` to see current totals and a suggested internal demo case. The script prints the assigned SME ID needed for the review demo. Reimporting the catalog after this update changes case versions and clears earlier evaluations or approvals for cases whose SME profile changed; historical audit events remain.
