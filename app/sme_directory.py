"""Read the 60-person synthetic SME CSV and explain each match.

The workbook names optimization labels, while the CSV names human specialties.
The mappings below and in final_sme_rules.py translate those vocabularies.
It is deliberately explicit so a teammate can inspect or change a match.
"""
from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path

from .final_sme_rules import FINAL_MATCHING_RULES
from .schemas import PRACTICES, SME

HEADERS = (
    "SME_ID", "SME_Name", "SME_Domain", "Primary_Specialization",
    "Level20_Expertise", "Service_Type_Expertise", "Skillset", "Industry_Expertise",
    "Experience_Years", "Domain_Experience_Years", "Band_Level", "SME_Level",
    "Certifications", "Current_POD", "Current_Account", "Location",
    "Utilization_Percent", "Availability_Status", "Active_Assignments", "Rating_Points",
)

# The CSV uses two older names for practices in the new opportunity workbook.
PRACTICE_NAMES = {
    "Core Enterprise & zCloud": "Core Enterprise and z/OS",
    "Digital Workplace": "Digital Workspace Services",
}

# Each value is a primary specialization as written in the CSV. The first
# specialization is preferred when availability and service type are equal.
MATCHING_RULES = {
    "Applications, Data & AI": {
        "ai_inference_optimization": ("MLOps & AI Platforms", "Generative AI & Agentic AI"),
        "compute_rightsizing": ("Application Managed Services", "MLOps & AI Platforms"),
        "database_decommission": ("Oracle Modernization", "Data Governance"),
        "database_optimization": ("Oracle Modernization", "Data Engineering & Analytics"),
        "environment_consolidation": ("Application Modernization", "Application Managed Services"),
        "gpu_scheduling": ("MLOps & AI Platforms",),
        "index_rightsizing": ("Data Engineering & Analytics", "Oracle Modernization"),
        "storage_tiering": ("Data Engineering & Analytics", "Application Managed Services"),
        "stream_retention": ("Data Engineering & Analytics", "Data Governance"),
    },
    "Cloud": {
        "cluster_autoscaling": ("Cloud Platform Engineering", "Cloud Operations"),
        "compute_purchasing": ("Cloud Optimization", "Cloud Operations"),
        "data_egress_optimization": ("Cloud Optimization", "Cloud Operations"),
        "database_rightsizing": ("Cloud Optimization", "Cloud Operations"),
        "environment_consolidation": ("Hybrid Cloud", "Cloud Migration"),
        "log_retention": ("Cloud Operations",),
        "resource_cleanup": ("Cloud Operations",),
        "snapshot_lifecycle": ("Cloud Operations",),
        "storage_tiering": ("Cloud Optimization", "Cloud Operations"),
        "vm_rightsizing": ("Cloud Optimization", "Cloud Operations"),
    },
    "Core Enterprise and z/OS": {
        "batch_optimization": ("z/OS Systems Programming", "Mainframe Operations"),
        "capacity_optimization": ("z/OS Systems Programming", "Mainframe Operations"),
        "db2_tuning": ("Db2 for z/OS",),
        "environment_consolidation": ("zCloud", "Mainframe Modernization"),
        "license_optimization": ("Mainframe Modernization", "Mainframe Operations"),
        "lpar_rightsizing": ("z/OS Systems Programming",),
        "scheduler_rationalization": ("z/OS Systems Programming",),
        "spool_optimization": ("z/OS Systems Programming",),
        "storage_tiering": ("z/OS Systems Programming", "Mainframe Operations"),
        "tool_rationalization": ("Mainframe Modernization",),
    },
    "Digital Workspace Services": {
        "device_rationalization": ("Device Lifecycle Management", "Endpoint Management"),
        "license_optimization": ("Microsoft 365",),
        "license_reclamation": ("Microsoft 365",),
        "storage_cleanup": ("Endpoint Management",),
        "subscription_cleanup": ("Microsoft 365",),
        "vdi_pool_rightsizing": ("Virtual Desktop",),
    },
    "Network & Edge": {
        "cache_optimization": ("Edge Infrastructure", "Network Operations"),
        "circuit_consolidation": ("WAN & SD-WAN", "Enterprise Routing & Switching"),
        "edge_rightsizing": ("Edge Infrastructure", "Network Operations"),
        "license_optimization": ("Network Operations", "Network Automation"),
        "port_rightsizing": ("Enterprise Routing & Switching",),
        "routing_optimization": ("Enterprise Routing & Switching",),
        "subscription_cleanup": ("Network Operations", "Network Automation"),
        "tool_rationalization": ("Network Automation",),
    },
    "Security & Resiliency": {
        "agent_consolidation": ("SOC & MXDR",),
        "backup_tiering": ("Cyber Recovery", "Resilience & Disaster Recovery"),
        "connector_cleanup": ("Zero Trust", "Identity & PAM"),
        "dr_capacity_scheduling": ("Resilience & Disaster Recovery",),
        "license_reclamation": ("Zero Trust", "Security Assurance & GRC"),
        "log_retention": ("SOC & MXDR",),
        "scanner_consolidation": ("Vulnerability Management",),
        "storage_rightsizing": ("Cyber Recovery", "Resilience & Disaster Recovery"),
        "tool_rationalization": ("Zero Trust", "Security Assurance & GRC"),
    },
}

for practice, labels in FINAL_MATCHING_RULES.items():
    MATCHING_RULES[practice].update(labels)


def load_directory(path: Path) -> list[dict[str, str]]:
    """Validate the CSV once; keep the supplied file unchanged."""
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != HEADERS:
            raise ValueError("SME CSV has unexpected column names")
        rows = list(reader)

    if len(rows) != 60:
        raise ValueError("SME CSV must have exactly 60 people")

    seen_ids = set()
    domains = Counter()
    for line, row in enumerate(rows, 2):
        sme_id = row["SME_ID"].strip()
        if not sme_id or sme_id in seen_ids:
            raise ValueError(f"Missing or duplicate SME ID on CSV line {line}")
        seen_ids.add(sme_id)
        for field in ("SME_Name", "SME_Domain", "Primary_Specialization", "Skillset"):
            if not row[field].strip():
                raise ValueError(f"Missing {field} on CSV line {line}")

        practice = PRACTICE_NAMES.get(row["SME_Domain"], row["SME_Domain"])
        if practice not in PRACTICES:
            raise ValueError(f"Unknown SME domain on CSV line {line}")
        row["practice"] = practice
        domains[practice] += 1

        if row["Service_Type_Expertise"] not in {"Manage", "Consult", "Both"}:
            raise ValueError(f"Unknown SME service type on CSV line {line}")
        if row["Availability_Status"] not in {"Available", "Partially Available", "Limited"}:
            raise ValueError(f"Unknown SME availability on CSV line {line}")
        try:
            utilization = int(row["Utilization_Percent"])
            years = int(row["Experience_Years"])
            domain_years = int(row["Domain_Experience_Years"])
            assignments = int(row["Active_Assignments"])
            rating = float(row["Rating_Points"])
        except ValueError as exc:
            raise ValueError(f"Invalid SME numeric value on CSV line {line}") from exc
        if not (0 <= utilization <= 100 and 0 <= domain_years <= years and assignments >= 0 and 0 <= rating <= 5):
            raise ValueError(f"Out-of-range SME value on CSV line {line}")
        if (row["Availability_Status"] == "Available" and utilization > 60 or
                row["Availability_Status"] == "Partially Available" and not 60 < utilization <= 80 or
                row["Availability_Status"] == "Limited" and utilization <= 80):
            raise ValueError(f"SME availability conflicts with utilization on CSV line {line}")

    if domains != Counter({practice: 10 for practice in PRACTICES}):
        raise ValueError("SME CSV must have ten people in each practice")
    return rows


def matching_smes(directory: list[dict[str, str]], practice: str,
                  optimization: str, service_type: str | None, industry: str | None) -> list[SME]:
    """Return matching specialists in a reproducible order.

    A limited SME remains visible as a candidate but cannot be assigned by policy.
    Industry and utilization only rank otherwise valid candidates; they never
    turn an unrelated specialty into a match.
    """
    specialties = MATCHING_RULES.get(practice, {}).get(optimization)
    if not specialties:
        return []
    candidates = []
    for row in directory:
        if row["practice"] != practice:
            continue
        specialty = row["Primary_Specialization"]
        if specialty not in specialties:
            continue
        if service_type and row["Service_Type_Expertise"] not in {service_type, "Both"}:
            continue
        available = row["Availability_Status"] != "Limited"
        sme = SME(
            sme_id=row["SME_ID"], practice=practice,
            skills=[item.strip() for item in row["Skillset"].split(",") if item.strip()],
            matched_optimization=optimization,
            available=available, synthetic=True, name=row["SME_Name"],
            specialization=specialty, availability_status=row["Availability_Status"],
            utilization_percent=int(row["Utilization_Percent"]),
            rating_points=float(row["Rating_Points"]),
            experience_years=int(row["Experience_Years"]),
            service_type_expertise=row["Service_Type_Expertise"],
            industry_expertise=row["Industry_Expertise"],
            match_reason=f"{specialty} covers {optimization}"
            + (f"; {service_type} service" if service_type else ""),
        )
        industry_match = bool(industry and industry.lower() in row["Industry_Expertise"].lower())
        rank = (
            not available,
            specialties.index(specialty),
            not industry_match,
            int(row["Utilization_Percent"]),
            -float(row["Rating_Points"]),
            row["SME_ID"],
        )
        candidates.append((rank, sme))
    candidates.sort(key=lambda item: item[0])
    return [sme for _, sme in candidates]
