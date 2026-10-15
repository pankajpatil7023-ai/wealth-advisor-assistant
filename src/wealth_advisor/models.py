"""Validated inputs and outputs shared by the agents and tools."""

from datetime import date, datetime, timezone
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Transaction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    transaction_id: str = Field(default_factory=lambda: str(uuid4()))
    posted_at: date
    description: str = Field(min_length=1)
    category: str = Field(min_length=1)
    transaction_type: Literal["income", "expense"]
    amount: float = Field(gt=0)
    merchant: str | None = None

    @field_validator("category", "description")
    @classmethod
    def strip_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("must not be blank")
        return cleaned


class ClientFinancials(BaseModel):
    model_config = ConfigDict(extra="forbid")

    client_id: str = Field(min_length=1)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    current_balance: float = 0
    transactions: list[Transaction] = Field(default_factory=list)

    @field_validator("client_id")
    @classmethod
    def strip_client_id(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("client_id must not be blank")
        return cleaned


class ClientProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    client_id: str
    name: str
    age: int = Field(ge=18)
    financial_goals: list[str] = Field(default_factory=list)
    risk_tolerance: Literal["conservative", "moderate", "aggressive"]
    advisor_notes: str = ""


class MonthlyTotals(BaseModel):
    month: str
    income: float = 0
    expenses: float = 0
    net_cash_flow: float = 0


class CategoryTotal(BaseModel):
    category: str
    amount: float


class FlaggedInsight(BaseModel):
    insight_id: str = Field(default_factory=lambda: str(uuid4()))
    rule_id: str
    title: str
    explanation: str
    severity: Literal["low", "medium", "high"]
    transaction_ids: list[str] = Field(default_factory=list)


class AnalysisResult(BaseModel):
    client_id: str
    currency: str
    total_income: float
    total_expenses: float
    net_cash_flow: float
    transaction_count: int
    monthly_totals: list[MonthlyTotals]
    category_totals: list[CategoryTotal]
    flagged_insights: list[FlaggedInsight]
    methodology: list[str]


class ReviewDecision(BaseModel):
    insight_id: str
    decision: Literal["approved", "rejected"]
    reviewer: str = "local user"
    reviewed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class HistoricalSummary(BaseModel):
    client_id: str
    session_id: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    total_income: float
    total_expenses: float
    net_cash_flow: float
    approved_insight_count: int


class FinalReport(BaseModel):
    client_id: str
    session_id: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    client_profile: ClientProfile | None = None
    analysis: AnalysisResult | None = None
    approved_insights: list[FlaggedInsight] = Field(default_factory=list)
    rejected_insight_count: int = 0
    review_decisions: list[ReviewDecision] = Field(default_factory=list)
    previous_summaries: list[HistoricalSummary] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    disclaimer: str = (
        "Demonstration only. This report is not financial, tax, or investment advice."
    )
