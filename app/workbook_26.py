"""Validate and load the private, fictional 26-column FORGE workbook."""
from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

from openpyxl import load_workbook

from .config import settings
from .schemas import Contract, Evidence, Opportunity, PipelineMatch, PRACTICES
from .sme_directory import load_directory, matching_smes

INPUT_HEADERS = (
    "Opp No", "Opp Name", "Customer", "Customer Number", "Practices", "Service Type",
    "Level 30 Desc", "Line Item Name", "S/S Name", "Opp Create Date", "Industry",
    "Opp Owner User Name", "Contract ID", "Customer Request", "Optimization Type",
    "Environment", "Asset Group ID", "Business Service", "Criticality", "RTO Minutes",
    "RPO Minutes", "Baseline Monthly Cost (USD)", "Proposed Monthly Cost (USD)",
    "One-time Implementation Cost (USD)", "Evidence ID", "Technical Constraints",
)
HEADERS = {
    "Opportunity_Input": INPUT_HEADERS,
    "Contracts": ("Contract ID", "Customer Number", "Effective Start", "Effective End",
                  "Allowed Optimization Types", "Excluded Optimization Types", "Scope Notes"),
    "FinOps_Evidence": ("Evidence ID", "Opp No", "Customer Number", "Asset Group ID",
                        "Period Start", "Period End", "Observed Monthly Cost USD",
                        "Telemetry Summary", "Evidence Notes"),
    "Existing_Opportunities": ("Existing Opp ID", "Customer Number", "Asset Group ID",
                               "Optimization Type", "S/S Name", "Status"),
    "SME_Directory": ("SME ID", "Practice", "Skills", "Available Hours (7d)", "Active"),
}
FINAL_HEADERS = {
    "Contracts": ("Contract ID", "Customer", "Contract Name", "Start Date", "End Date",
                  "Scope Description", "Active Scope Status", "Governing Terms"),
    "FinOps_Evidence": ("Evidence ID", "Opp No", "Source", "Evidence Type",
                        "Collection Date", "Validated Monthly Savings (USD)",
                        "Confidence Score", "Verification Status"),
    "Existing_Opportunities": ("Existing Opp ID", "Customer", "Opportunity Name",
                               "Practice", "Status", "Submitted Date",
                               "Estimated Monthly Savings (USD)"),
}
LEGACY_STAGE_COUNTS = Counter({"Identified": 18, "Noticed": 22, "Qualified": 14, "Validated": 6})
STAGE_COUNTS = Counter({"Stretch": 1, "Won": 19, "Validated": 20,
                        "Qualified": 10, "Noticed": 5, "Identified": 5})
IMPACT = {"LOW": 1, "MEDIUM": 2, "HIGH": 4, "CRITICAL": 5,
          "Standard": 1, "Business Critical": 4, "Mission Critical": 5}
FEASIBILITY = {"non-production": 1, "business-hours": 2, "production": 3,
               "Non-Production": 1, "Staging": 2, "Production": 3, "Disaster Recovery": 4}


def _text(value) -> str:
    return "" if value is None else str(value).strip()


def _date(value, field: str) -> datetime:
    if isinstance(value, datetime):
        result = value
    elif isinstance(value, date):
        result = datetime.combine(value, datetime.min.time())
    else:
        try:
            result = datetime.fromisoformat(_text(value))
        except ValueError as exc:
            raise ValueError(f"Invalid {field} date") from exc
    return result.replace(tzinfo=timezone.utc) if result.tzinfo is None else result.astimezone(timezone.utc)


def _money(value, field: str, *, allow_negative: bool = False) -> Decimal:
    try:
        result = Decimal(_text(value).replace(",", ""))
    except Exception as exc:
        raise ValueError(f"Invalid {field} amount") from exc
    if not result.is_finite() or (result < 0 and not allow_negative):
        raise ValueError(f"Invalid {field} amount")
    return result


def _items(value) -> set[str]:
    return {part.strip() for part in _text(value).split(";") if part.strip()}


def _rows(book, sheet_name: str) -> list[dict]:
    if sheet_name not in book.sheetnames:
        raise ValueError(f"Missing worksheet {sheet_name}")
    iterator = book[sheet_name].values
    header = tuple(next(iterator, ()))
    accepted = (HEADERS[sheet_name], FINAL_HEADERS.get(sheet_name))
    if header not in accepted:
        raise ValueError(f"Incorrect columns in {sheet_name}")
    result = []
    for row_number, values in enumerate(iterator, 2):
        if not any(value is not None for value in values):
            continue
        if len(values) != len(header):
            raise ValueError(f"Incorrect column count in {sheet_name} row {row_number}")
        result.append({**dict(zip(header, values)), "_row": row_number})
    return result


def _keyed(rows: list[dict], key: str, sheet: str,
           allow_identical: bool = False) -> dict[str, dict]:
    result = {}
    for row in rows:
        value = _text(row[key])
        if not value:
            raise ValueError(f"Missing {key} in {sheet}")
        if value in result:
            old = {name: content for name, content in result[value].items() if name != "_row"}
            new = {name: content for name, content in row.items() if name != "_row"}
            if not allow_identical or old != new:
                raise ValueError(f"Conflicting duplicate {key} in {sheet}")
            continue
        result[value] = row
    return result


def _check_master(book, input_rows: list[dict]) -> None:
    """The final workbook repeats all input fields in its master tab."""
    if "Master_Consolidated" not in book.sheetnames:
        return
    iterator = book["Master_Consolidated"].values
    headers = tuple(next(iterator, ()))
    if not set(INPUT_HEADERS).issubset(headers):
        raise ValueError("Master_Consolidated is missing opportunity input columns")
    master = _keyed([dict(zip(headers, row)) for row in iterator if any(value is not None for value in row)],
                    "Opp No", "Master_Consolidated")
    if len(master) != len(input_rows):
        raise ValueError("Master_Consolidated row count does not match Opportunity_Input")
    for row in input_rows:
        source = master.get(_text(row["Opp No"]))
        if source is None or any(source[name] != row[name] for name in INPUT_HEADERS):
            raise ValueError(f"Master_Consolidated differs from Opportunity_Input row {row['_row']}")


def load_cases(path: Path, sme_csv_path: Path | None = None) -> tuple[list[Opportunity], Counter, Counter]:
    """Join the opportunity workbook with the separate 60-person SME CSV."""
    directory = load_directory(sme_csv_path or settings.sme_csv_path)
    book = load_workbook(path, read_only=True, data_only=True)
    try:
        input_rows = _rows(book, "Opportunity_Input")
        _check_master(book, input_rows)
        contract_rows = _rows(book, "Contracts")
        contracts = _keyed(contract_rows, "Contract ID", "Contracts",
                           allow_identical="Customer" in contract_rows[0])
        evidence = _keyed(_rows(book, "FinOps_Evidence"), "Evidence ID", "FinOps_Evidence")
        pipeline = _rows(book, "Existing_Opportunities")
        # This 12-person tab is retained and validated as workbook provenance.
        # The separate 60-person CSV supplies active SME recommendations.
        workbook_smes = _rows(book, "SME_Directory")
    finally:
        book.close()
    if len(input_rows) != 60:
        raise ValueError("Expected exactly 60 opportunities")
    _keyed(input_rows, "Opp No", "Opportunity_Input")
    practices = Counter(_text(row["Practices"]) for row in input_rows)
    stages = Counter(_text(row["S/S Name"]) for row in input_rows)
    if practices != Counter({practice: 10 for practice in PRACTICES}):
        raise ValueError("Expected ten opportunities in each of the six current practices")
    if stages not in (STAGE_COUNTS, LEGACY_STAGE_COUNTS):
        raise ValueError("Source stage counts do not match this 60-row workbook")
    if len(contract_rows) != 60 or len(evidence) != 54 or len(pipeline) != 11 or len(workbook_smes) != 12:
        raise ValueError("Reference worksheet row counts do not match the verified workbook")
    final_layout = "Customer" in next(iter(contracts.values()))

    cases = []
    for row in input_rows:
        opportunity_id = _text(row["Opp No"])
        customer_number = _text(row["Customer Number"])
        asset_group = _text(row["Asset Group ID"])
        optimization = _text(row["Optimization Type"])
        required = [name for name in INPUT_HEADERS if name not in ("Evidence ID", "RTO Minutes", "RPO Minutes")]
        if any(not _text(row[name]) for name in required):
            raise ValueError(f"Incomplete required source fields in row {row['_row']}")
        baseline = _money(row["Baseline Monthly Cost (USD)"], "baseline")
        proposed = _money(row["Proposed Monthly Cost (USD)"], "proposed cost")
        implementation = _money(row["One-time Implementation Cost (USD)"],
                                "implementation cost", allow_negative=final_layout)
        if baseline <= 0:
            raise ValueError(f"Nonpositive baseline in row {row['_row']}")

        contract_id = _text(row["Contract ID"])
        contract_row = contracts.get(contract_id)
        contract_customer = "Customer" if final_layout else "Customer Number"
        expected_customer = _text(row["Customer"]) if final_layout else customer_number
        if not contract_row or _text(contract_row[contract_customer]) != expected_customer:
            raise ValueError(f"Invalid contract reference in row {row['_row']}")
        contract_start = _date(contract_row["Start Date" if final_layout else "Effective Start"], "contract start")
        contract_end = _date(contract_row["End Date" if final_layout else "Effective End"], "contract end")
        if contract_end < contract_start:
            raise ValueError(f"Reversed contract dates in row {row['_row']}")
        if final_layout:
            # "Active" confirms a contract exists; it does not approve this
            # optimization's scope. Keep the policy blocker until SME review.
            status = _text(contract_row["Active Scope Status"])
            if status != "Active":
                raise ValueError(f"Unsupported contract status in row {row['_row']}")
            contract = Contract(contract_id=contract_id, scope="unknown",
                                verified=False, synthetic=True)
        else:
            allowed = _items(contract_row["Allowed Optimization Types"])
            excluded = _items(contract_row["Excluded Optimization Types"])
            scope = ("out_of_scope" if optimization in excluded else
                     "in_scope" if optimization in allowed else "unknown")
            contract = Contract(contract_id=contract_id, scope=scope, verified=True, synthetic=True)

        evidence_id = _text(row["Evidence ID"])
        measured = None
        if evidence_id:
            evidence_row = evidence.get(evidence_id)
            joins = (("Opp No", opportunity_id),) if final_layout else (
                ("Opp No", opportunity_id), ("Customer Number", customer_number),
                ("Asset Group ID", asset_group))
            if not evidence_row or any(_text(evidence_row[key]) != expected for key, expected in joins):
                raise ValueError(f"Invalid evidence reference in row {row['_row']}")
            if final_layout:
                observed_at = _date(evidence_row["Collection Date"], "evidence collection")
                savings = _money(evidence_row["Validated Monthly Savings (USD)"], "validated savings")
                if savings != baseline - proposed:
                    raise ValueError(f"Validated savings differs from cost projection in row {row['_row']}")
                confidence = float(evidence_row["Confidence Score"])
                if not 0 <= confidence <= 1:
                    raise ValueError(f"Invalid evidence confidence in row {row['_row']}")
                verified = _text(evidence_row["Verification Status"]) == "Verified"
                source = _text(evidence_row["Source"])
                evidence_type = _text(evidence_row["Evidence Type"])
                if not source or not evidence_type:
                    raise ValueError(f"Missing evidence provenance in row {row['_row']}")
            else:
                period_start = _date(evidence_row["Period Start"], "evidence start")
                observed_at = _date(evidence_row["Period End"], "evidence end")
                if observed_at < period_start:
                    raise ValueError(f"Invalid evidence period in row {row['_row']}")
                observed = _money(evidence_row["Observed Monthly Cost USD"], "observed cost")
                if observed != baseline:
                    raise ValueError(f"Baseline differs from linked evidence in row {row['_row']}")
                confidence, verified = None, True
                source = "Synthetic workbook FinOps_Evidence and POC cost projection"
                evidence_type = None
            if observed_at > datetime.now(timezone.utc):
                raise ValueError(f"Future evidence date in row {row['_row']}")
            measured = Evidence(evidence_id=evidence_id, observed_at=observed_at,
                                monthly_baseline=baseline, projected_monthly_cost=proposed,
                                implementation_cost=max(implementation, Decimal("0")), currency="USD",
                                source=source, verified=verified, synthetic=True, recurring=True,
                                evidence_type=evidence_type, confidence_score=confidence)

        matches = [] if final_layout else [PipelineMatch(pipeline_id=_text(item["Existing Opp ID"]),
                                 account_id=customer_number, asset_group_id=asset_group,
                                 optimization_type=optimization, synthetic=True)
                   for item in pipeline if _text(item["Status"]) == "ACTIVE" and
                   _text(item["Customer Number"]) == customer_number and
                   _text(item["Asset Group ID"]) == asset_group and
                   _text(item["Optimization Type"]) == optimization]
        possible = [_text(item["Existing Opp ID"]) for item in pipeline
                    if final_layout and _text(item["Customer"]) == _text(row["Customer"])
                    and _text(item["Practice"]) == _text(row["Practices"])]
        practice = _text(row["Practices"])
        candidates = matching_smes(
            directory, practice, optimization,
            _text(row["Service Type"]), _text(row["Industry"]),
        )
        matching_sme = any(sme.available and sme.matched_optimization == optimization
                           for sme in candidates)
        criticality = _text(row["Criticality"])
        environment = _text(row["Environment"])
        if criticality not in IMPACT or environment not in FEASIBILITY:
            raise ValueError(f"Unsupported impact or environment in row {row['_row']}")
        cases.append(Opportunity(
            opportunity_id=opportunity_id, opportunity_name=_text(row["Opp Name"]),
            practice=practice, source_sales_stage=_text(row["S/S Name"]),
            source_system="FORGE_26_workbook", source_file=path.name,
            source_record_id=opportunity_id, source_sheet="Opportunity_Input",
            source_row=row["_row"], synthetic=True,
            customer_name=_text(row["Customer"]), customer_number=customer_number,
            account_id=customer_number, service_type=_text(row["Service Type"]),
            level30_description=_text(row["Level 30 Desc"]),
            line_item_name=_text(row["Line Item Name"]),
            source_created_at=_date(row["Opp Create Date"], "opportunity creation"),
            industry=_text(row["Industry"]), source_owner_user_name=_text(row["Opp Owner User Name"]),
            customer_request=_text(row["Customer Request"]), optimization_type=optimization,
            required_skill=optimization, environment=environment, asset_group_id=asset_group,
            business_service=_text(row["Business Service"]), criticality=criticality,
            rto_minutes=int(row["RTO Minutes"]) if row["RTO Minutes"] is not None else None,
            rpo_minutes=int(row["RPO Minutes"]) if row["RPO Minutes"] is not None else None,
            technical_constraints=_text(row["Technical Constraints"]),
            source_baseline_monthly_cost=baseline, source_proposed_monthly_cost=proposed,
            source_implementation_cost=implementation,
            claimed_monthly_customer_savings=baseline - proposed if baseline >= proposed else None,
            evidence=measured, contract=contract, pipeline_matches=matches,
            possible_existing_opportunity_ids=possible, smes=candidates,
            service_impact=IMPACT[criticality], technical_feasibility=FEASIBILITY[environment],
            capability_fit=1 if matching_sme else 4,
        ))
    return cases, practices, stages
