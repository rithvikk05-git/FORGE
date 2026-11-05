"""Isolate each integration test from the user's local SQLite files."""
from dataclasses import replace
from datetime import datetime, timezone

import pytest

import app.api as api_module
import app.db as db_module
import app.graph as graph_module
import app.services as services_module


@pytest.fixture
def isolated_store(tmp_path, monkeypatch):
    configured = replace(db_module.settings, sqlite_path=tmp_path / "forge.sqlite",
                         checkpoint_path=tmp_path / "langgraph.sqlite",
                         source_xlsx_path=tmp_path / "source.xlsx",
                         sme_token="test-sme-token", sme_reviewer_id="demo-sme",
                         governance_token="test-governance-token", governance_reviewer_id="demo-governance")
    for module in (api_module, db_module, graph_module, services_module):
        monkeypatch.setattr(module, "settings", configured)
    return configured


@pytest.fixture
def valid_case():
    return {
        "opportunity_id": "TEST-001", "practice": "Cloud", "opportunity_name": "Synthetic test case",
        "source_sales_stage": "Identified", "source_system": "test_fixture", "synthetic": True,
        "account_id": "TEST-A", "asset_group_id": "TEST-ASSET", "optimization_type": "rightsizing",
        "required_skill": "rightsizing", "service_impact": 1, "technical_feasibility": 1,
        "capability_fit": 1, "commercial_opportunity_value": "8000", "commercial_currency": "USD",
        "evidence": {"evidence_id": "TEST-E", "observed_at": datetime.now(timezone.utc).isoformat(),
                     "monthly_baseline": "30000", "projected_monthly_cost": "18000", "currency": "USD",
                     "source": "synthetic pytest evidence", "verified": True, "synthetic": True,
                     "implementation_cost": "5000", "ongoing_incremental_monthly_cost": "1000"},
        "contract": {"contract_id": "TEST-C", "scope": "in_scope", "verified": True, "synthetic": True},
        "smes": [{"sme_id": "demo-sme", "practice": "Cloud", "skills": ["rightsizing"],
                  "available": True, "synthetic": True}],
    }
