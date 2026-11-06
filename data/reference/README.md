# FORGE reference data

These four local JSON files are ready for approved data:

- `successful_opportunities.json` — completed, won projects only. A `Won` sales stage in the intake workbook does **not** enter this repository automatically.
- `cost_impact.json` — cost evidence.
- `technical_impact.json` — technical evidence.
- `compliance.json` — compliance evidence.

Each file has this shape:

```json
{"schema_version": 1, "records": []}
```

The `.example.json` files are tracked by Git so teammates receive empty templates. Copy each example to the matching `.json` filename before adding local records. The active `.json` files are ignored by Git.

Add objects to `records` with a unique `reference_id`. To link a record to an opportunity, set its `opportunity_id` to the source ID. Alternatively, provide both `practice` and `optimization_type` for a broad match. Other source fields can be retained in each object. Missing files are treated as empty; malformed files fail validation at intake.

The agents surface matching records as `reference_evidence` and their IDs as `reference_ids`. They do not change approved policy or agent scores from these future sheets until scoring rules and source definitions are supplied. The prompt template is `null` in the graph and API result until designed.

Form submissions use `POST /api/opportunities/form` and live in the normal opportunity list. Previous form submissions appear as separate `form_opportunities` references. They never become successful projects automatically.
