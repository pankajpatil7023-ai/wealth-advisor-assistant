import json
from pathlib import Path

from wealth_advisor.agents.data_fetcher import DataFetcherAgent
from wealth_advisor.models import ClientProfile
from wealth_advisor.tools.client_data import JsonFinancialDataTool


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class SuccessfulCrm:
    def get_client_profile(self, client_id: str) -> ClientProfile:
        return ClientProfile(
            client_id=client_id,
            name="Test Client",
            age=35,
            risk_tolerance="moderate",
        )


class FailingCrm:
    def get_client_profile(self, client_id: str) -> ClientProfile:
        raise ValueError("CRM is unavailable: ConnectError.")


def test_fetcher_loads_financial_data_and_crm_profile() -> None:
    fetcher = DataFetcherAgent(JsonFinancialDataTool(), SuccessfulCrm())

    financials, profile, warnings, errors = fetcher.run(
        "client-001", PROJECT_ROOT / "data/client_financials.json"
    )

    assert financials is not None
    assert financials.client_id == "client-001"
    assert profile is not None and profile.name == "Test Client"
    assert warnings == []
    assert errors == []


def test_fetcher_handles_crm_failure_without_losing_local_data() -> None:
    fetcher = DataFetcherAgent(JsonFinancialDataTool(), FailingCrm())

    financials, profile, warnings, errors = fetcher.run(
        "client-001", PROJECT_ROOT / "data/client_financials.json"
    )

    assert financials is not None
    assert profile is None
    assert "CRM context could not be loaded" in warnings[0]
    assert errors == []


def test_fetcher_rejects_mismatched_client_id(tmp_path: Path) -> None:
    data_path = tmp_path / "ledger.json"
    data_path.write_text(
        json.dumps({"client_id": "someone-else", "transactions": []}),
        encoding="utf-8",
    )
    fetcher = DataFetcherAgent(JsonFinancialDataTool(), SuccessfulCrm())

    financials, _, _, errors = fetcher.run("client-001", data_path)

    assert financials is None
    assert "not requested client" in errors[0]
