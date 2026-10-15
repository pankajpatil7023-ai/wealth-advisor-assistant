import json
from pathlib import Path

from wealth_advisor.agents.analyzer import AnalyzerAgent
from wealth_advisor.agents.data_fetcher import DataFetcherAgent
from wealth_advisor.agents.orchestrator import OrchestratorAgent
from wealth_advisor.models import ClientProfile, ReviewDecision
from wealth_advisor.tools.client_data import JsonFinancialDataTool
from wealth_advisor.tools.memory import MemoryStore


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class SampleCrm:
    def get_client_profile(self, client_id: str) -> ClientProfile:
        return ClientProfile(
            client_id=client_id,
            name="Jordan Test",
            age=38,
            risk_tolerance="moderate",
        )


def test_langgraph_workflow_applies_review_and_stores_memory(tmp_path: Path) -> None:
    reviewed_ids: list[str] = []

    def reviewer(insights):
        reviewed_ids.extend(item.insight_id for item in insights)
        return [
            ReviewDecision(
                insight_id=item.insight_id,
                decision="approved" if index == 0 else "rejected",
                reviewer="test reviewer",
            )
            for index, item in enumerate(insights)
        ]

    memory = MemoryStore(tmp_path / "memory")
    orchestrator = OrchestratorAgent(
        data_fetcher=DataFetcherAgent(JsonFinancialDataTool(), SampleCrm()),
        analyzer=AnalyzerAgent(),
        memory=memory,
        review_handler=reviewer,
    )

    report = orchestrator.run(
        "client-001",
        str(PROJECT_ROOT / "data/client_financials.json"),
        session_id="session-one",
    )

    assert report.analysis is not None
    assert report.client_profile is not None
    assert len(reviewed_ids) == 3
    assert len(report.approved_insights) == 1
    assert report.rejected_insight_count == 2
    assert report.approved_insights[0].insight_id == reviewed_ids[0]
    assert len(memory.get_recent_summaries("client-001")) == 1
    session_file = tmp_path / "memory/sessions/session-one.json"
    assert session_file.exists()
    assert "1 insight(s) approved" in json.loads(session_file.read_text(encoding="utf-8"))[0]["note"]

    second_report = orchestrator.run(
        "client-001",
        str(PROJECT_ROOT / "data/client_financials.json"),
        session_id="session-two",
    )
    assert len(second_report.previous_summaries) == 1


def test_missing_reviewer_fails_closed(tmp_path: Path) -> None:
    orchestrator = OrchestratorAgent(
        data_fetcher=DataFetcherAgent(JsonFinancialDataTool(), SampleCrm()),
        analyzer=AnalyzerAgent(),
        memory=MemoryStore(tmp_path / "memory"),
    )

    report = orchestrator.run(
        "client-001",
        str(PROJECT_ROOT / "data/client_financials.json"),
        session_id="no-reviewer",
    )

    assert report.analysis is not None
    assert report.approved_insights == []
    assert report.rejected_insight_count == 3
    assert any("No human reviewer" in warning for warning in report.warnings)
