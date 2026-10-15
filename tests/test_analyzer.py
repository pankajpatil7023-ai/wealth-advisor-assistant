import json
from pathlib import Path

from wealth_advisor.agents.analyzer import AnalyzerAgent
from wealth_advisor.models import ClientFinancials


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_sample_ledger_metrics_and_explainable_flags() -> None:
    raw = json.loads((PROJECT_ROOT / "data/client_financials.json").read_text(encoding="utf-8"))
    result = AnalyzerAgent().analyze(ClientFinancials.model_validate(raw))

    assert result.total_income == 14200.0
    assert result.total_expenses == 9424.2
    assert result.net_cash_flow == 4775.8
    assert result.transaction_count == 12
    assert [item.month for item in result.monthly_totals] == ["2026-01", "2026-02"]
    assert {item.rule_id for item in result.flagged_insights} == {
        "large_expense",
        "possible_duplicate",
        "category_monthly_spike",
    }
    assert all(item.explanation for item in result.flagged_insights)
    assert all(item.rule_id for item in result.flagged_insights)


def test_empty_transactions_produce_zero_totals_without_crashing() -> None:
    financials = ClientFinancials.model_validate(
        {"client_id": "client-empty", "transactions": []}
    )

    result = AnalyzerAgent().analyze(financials)

    assert result.transaction_count == 0
    assert result.total_income == 0
    assert result.total_expenses == 0
    assert result.net_cash_flow == 0
    assert result.flagged_insights == []
    assert any("No transactions" in item for item in result.methodology)


def test_negative_cash_flow_is_flagged() -> None:
    financials = ClientFinancials.model_validate(
        {
            "client_id": "client-deficit",
            "transactions": [
                {
                    "transaction_id": "expense-1",
                    "posted_at": "2026-01-01",
                    "description": "Large bill",
                    "category": "bills",
                    "transaction_type": "expense",
                    "amount": 3000,
                },
                {
                    "transaction_id": "income-1",
                    "posted_at": "2026-01-02",
                    "description": "Pay",
                    "category": "salary",
                    "transaction_type": "income",
                    "amount": 1000,
                },
            ],
        }
    )

    result = AnalyzerAgent().analyze(financials)

    assert result.net_cash_flow == -2000
    assert "cashflow_deficit" in {item.rule_id for item in result.flagged_insights}
