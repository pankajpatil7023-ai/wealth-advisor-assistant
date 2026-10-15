from pathlib import Path

from fastapi.testclient import TestClient
from pydantic import ValidationError

from wealth_advisor.agents.analyzer import AnalyzerAgent
from wealth_advisor.agents.data_fetcher import DataFetcherAgent
from wealth_advisor.agents.orchestrator import OrchestratorAgent
from wealth_advisor.models import ClientFinancials, ClientProfile
from wealth_advisor.mock_crm_api import app
from wealth_advisor.tools.client_data import JsonFinancialDataTool
from wealth_advisor.tools.memory import MemoryStore


PROJECT_ROOT = Path(__file__).resolve().parents[1]
client = TestClient(app)


class MissingCrm:
    def get_client_profile(self, client_id: str) -> ClientProfile:
        raise ValueError(f"CRM has no profile for client '{client_id}'.")


def test_invalid_json_returns_a_clear_partial_report(tmp_path: Path) -> None:
    data_path = tmp_path / "broken.json"
    data_path.write_text('{"client_id": ', encoding="utf-8")
    orchestrator = OrchestratorAgent(
        data_fetcher=DataFetcherAgent(JsonFinancialDataTool(), MissingCrm()),
        analyzer=AnalyzerAgent(),
        memory=MemoryStore(tmp_path / "memory"),
    )

    report = orchestrator.run("client-001", str(data_path), session_id="bad-json")

    assert report.analysis is None
    assert report.errors
    assert "invalid JSON" in report.errors[0]
    assert any("CRM context" in warning for warning in report.warnings)


def test_missing_file_is_reported_instead_of_crashing(tmp_path: Path) -> None:
    orchestrator = OrchestratorAgent(
        data_fetcher=DataFetcherAgent(JsonFinancialDataTool(), MissingCrm()),
        analyzer=AnalyzerAgent(),
        memory=MemoryStore(tmp_path / "memory"),
    )

    report = orchestrator.run(
        "client-001",
        str(tmp_path / "does-not-exist.json"),
        session_id="missing-file",
    )

    assert report.analysis is None
    assert "was not found" in report.errors[0]


def test_missing_required_fields_fail_pydantic_validation() -> None:
    try:
        ClientFinancials.model_validate({"transactions": []})
    except ValidationError as exc:
        assert any(item["loc"] == ("client_id",) for item in exc.errors())
    else:
        raise AssertionError("A ledger without client_id must fail validation.")


def test_mock_crm_serves_sample_and_returns_404_for_unknown_client() -> None:
    response = client.get("/clients/client-001")
    missing = client.get("/clients/unknown-client")

    assert response.status_code == 200
    assert response.json()["name"] == "Jordan Lee"
    assert missing.status_code == 404
