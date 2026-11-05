# FORGE policy rules for the synthetic POC

These are demonstration rules implemented in `app/policy_engine.py`. They are not approved corporate policy. The final workbook's current evidence limits are summarized in [Final source and flow](FINAL_SOURCE_AND_FLOW.md).

## Evidence and savings

An opportunity needs a linked, internally consistent FinOps evidence record. Evidence older than `EVIDENCE_MAX_AGE_DAYS` (default 180), dated in the future, or marked unverified blocks approval. The workbook's `verified` flag means synthetic source fields agree; it is not a real customer verification.

- Monthly customer savings = observed monthly baseline − proposed monthly cost.
- Annual savings = monthly savings × 12 when the reduction recurs.
- First-year net benefit = (monthly savings − ongoing monthly cost) × 12 − one-time implementation cost.
- Payback months = implementation cost ÷ positive net monthly benefit.

A proposal costing more than the baseline receives `FINANCIAL_ARITHMETIC_ANOMALY`. Claimed savings and commercial opportunity value are separate from validated customer savings.

The final workbook has one negative one-time source amount representing a credit. It is preserved as `source_implementation_cost` and shown as `unvalidated_implementation_credit`; it is not included in validated first-year benefit.

## Scope, duplicates, service, and SMEs

- Missing or unknown contract scope blocks approval; an excluded optimization receives `CONTRACT_OUT_OF_SCOPE`.
- An active pipeline match must have the same customer number, asset group, and optimization type to count as an exact duplicate. Similarity alone cannot decide this.
- Final-workbook historical rows lack asset and optimization keys. A same-customer-and-practice row is marked as a **possible** prior opportunity and triggers `POSSIBLE_PIPELINE_DUPLICATE_REVIEW_REQUIRED`; it is never called an exact duplicate.
- Critical service impact or missing technical/capability factors blocks approval.
- `app/sme_directory.py` and `app/final_sme_rules.py` map workbook optimization labels to CSV specializations. A candidate needs a matching practice and service type. `Available` and `Partially Available` may be assigned; `Limited` may not. No eligible candidate causes `SME_UNAVAILABLE`.
- A historical `Won` source record cannot become a new approved lead. The final workbook has 19 `Won` rows.

## Risk and priority

Each factor scores 0 to 5. A missing factor scores 5.

| Factor | Weight |
| --- | ---: |
| Service impact | 30% |
| Financial uncertainty | 25% |
| Technical feasibility | 20% |
| Capability fit | 15% |
| Resource availability | 10% |

Risk score = 20 × the weighted sum, on a 0–100 scale. Bands are LOW below 25, MEDIUM below 50, HIGH below 75, and CRITICAL otherwise. Any blocker sets priority to `HOLD`. A clear low-risk case with at least USD 10,000 validated monthly savings is `P1`; other clear low/medium cases are `P2`; other clear cases are `P3`.

## Human decision

LangGraph pauses after assessment. The internal API records reviewer identity, role, decision, comments, case version, and time in SQLite. Approval requires the assigned SME identity and local reviewer token. The graph and approved-summary endpoint recheck the case version and policy before producing an internal result. A revision invalidates earlier evaluations and approvals while preserving audit history. No step automatically approves or sends data outside FORGE.
