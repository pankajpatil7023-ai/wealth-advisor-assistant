"""Deterministic, explainable rules for cash flow and unusual activity."""

import logging
from collections import defaultdict
from statistics import median

from wealth_advisor.models import (
    AnalysisResult,
    CategoryTotal,
    ClientFinancials,
    FlaggedInsight,
    MonthlyTotals,
    Transaction,
)

logger = logging.getLogger(__name__)


def _money(value: float) -> float:
    return round(value, 2)


class AnalyzerAgent:
    """Analyze a ledger without an LLM or paid API."""

    LARGE_EXPENSE_FLOOR = 2_500.0
    LARGE_EXPENSE_MEDIAN_MULTIPLIER = 4.0
    CATEGORY_SPIKE_MULTIPLIER = 2.0
    CATEGORY_SPIKE_MIN_INCREASE = 500.0

    def analyze(self, financials: ClientFinancials) -> AnalysisResult:
        logger.info(
            "Analyzer started for client %s with %d transactions",
            financials.client_id,
            len(financials.transactions),
        )
        transactions = sorted(financials.transactions, key=lambda item: (item.posted_at, item.transaction_id))
        income = [item for item in transactions if item.transaction_type == "income"]
        expenses = [item for item in transactions if item.transaction_type == "expense"]
        total_income = _money(sum(item.amount for item in income))
        total_expenses = _money(sum(item.amount for item in expenses))

        monthly = self._monthly_totals(transactions)
        category_totals = self._category_totals(expenses)
        insights = self._large_expense_insights(expenses)
        insights.extend(self._duplicate_insights(transactions))
        insights.extend(self._category_spike_insights(transactions))
        if total_expenses > total_income:
            insights.append(
                FlaggedInsight(
                    rule_id="cashflow_deficit",
                    title="Expenses exceeded recorded income",
                    explanation=(
                        f"Recorded expenses were {financials.currency} {total_expenses:,.2f}, "
                        f"which is greater than recorded income of "
                        f"{financials.currency} {total_income:,.2f} for this data set."
                    ),
                    severity="high",
                )
            )

        methodology = [
            "Income and expenses are summed from transaction_type; amounts are treated as positive values.",
            (
                "Large expense rule: flag an expense at or above the greater of "
                f"{financials.currency} {self.LARGE_EXPENSE_FLOOR:,.0f} or "
                f"{self.LARGE_EXPENSE_MEDIAN_MULTIPLIER:g} times the median expense."
            ),
            (
                "Duplicate rule: flag repeated transactions with the same date, "
                "amount, transaction type, and merchant or description."
            ),
            (
                "Category spike rule: flag a category whose monthly total is more "
                f"than {self.CATEGORY_SPIKE_MULTIPLIER:g} times its prior observed "
                f"month and at least {financials.currency} "
                f"{self.CATEGORY_SPIKE_MIN_INCREASE:,.0f} higher."
            ),
            "Rules identify items for review; they do not determine whether a transaction is fraudulent.",
        ]
        if not transactions:
            methodology.append(
                "No transactions were available; zero totals are reported and no anomaly rules were applied."
            )

        result = AnalysisResult(
            client_id=financials.client_id,
            currency=financials.currency,
            total_income=total_income,
            total_expenses=total_expenses,
            net_cash_flow=_money(total_income - total_expenses),
            transaction_count=len(transactions),
            monthly_totals=monthly,
            category_totals=category_totals,
            flagged_insights=insights,
            methodology=methodology,
        )
        logger.info(
            "Analyzer finished for %s: income=%.2f expenses=%.2f flags=%d",
            financials.client_id,
            result.total_income,
            result.total_expenses,
            len(result.flagged_insights),
        )
        return result

    @staticmethod
    def _monthly_totals(transactions: list[Transaction]) -> list[MonthlyTotals]:
        totals: dict[str, dict[str, float]] = defaultdict(
            lambda: {"income": 0.0, "expenses": 0.0}
        )
        for item in transactions:
            month = item.posted_at.strftime("%Y-%m")
            key = "income" if item.transaction_type == "income" else "expenses"
            totals[month][key] += item.amount
        return [
            MonthlyTotals(
                month=month,
                income=_money(values["income"]),
                expenses=_money(values["expenses"]),
                net_cash_flow=_money(values["income"] - values["expenses"]),
            )
            for month, values in sorted(totals.items())
        ]

    @staticmethod
    def _category_totals(expenses: list[Transaction]) -> list[CategoryTotal]:
        totals: dict[str, float] = defaultdict(float)
        for item in expenses:
            totals[item.category] += item.amount
        return [
            CategoryTotal(category=category, amount=_money(amount))
            for category, amount in sorted(totals.items(), key=lambda pair: (-pair[1], pair[0]))
        ]

    def _large_expense_insights(
        self, expenses: list[Transaction]
    ) -> list[FlaggedInsight]:
        if not expenses:
            return []
        median_expense = median(item.amount for item in expenses)
        threshold = max(
            self.LARGE_EXPENSE_FLOOR,
            median_expense * self.LARGE_EXPENSE_MEDIAN_MULTIPLIER,
        )
        return [
            FlaggedInsight(
                rule_id="large_expense",
                title=f"Large {item.category.lower()} expense",
                explanation=(
                    f"This expense was {item.amount:,.2f}, at or above the "
                    f"explainable review threshold of {threshold:,.2f} "
                    f"(max of {self.LARGE_EXPENSE_FLOOR:,.2f} and "
                    f"{self.LARGE_EXPENSE_MEDIAN_MULTIPLIER:g} × median expense "
                    f"{median_expense:,.2f})."
                ),
                severity="high" if item.amount >= threshold * 2 else "medium",
                transaction_ids=[item.transaction_id],
            )
            for item in expenses
            if item.amount >= threshold
        ]

    @staticmethod
    def _duplicate_insights(
        transactions: list[Transaction],
    ) -> list[FlaggedInsight]:
        seen: dict[tuple[str, float, str, str], Transaction] = {}
        insights: list[FlaggedInsight] = []
        for item in transactions:
            identity_text = (item.merchant or item.description).strip().casefold()
            identity = (
                item.posted_at.isoformat(),
                item.amount,
                item.transaction_type,
                identity_text,
            )
            first = seen.get(identity)
            if first is None:
                seen[identity] = item
                continue
            insights.append(
                FlaggedInsight(
                    rule_id="possible_duplicate",
                    title="Possible duplicate transaction",
                    explanation=(
                        f"'{item.description}' matches a transaction on "
                        f"{item.posted_at.isoformat()} for {item.amount:,.2f}; "
                        "the date, amount, type, and merchant/description match."
                    ),
                    severity="medium",
                    transaction_ids=[first.transaction_id, item.transaction_id],
                )
            )
        return insights

    def _category_spike_insights(
        self, transactions: list[Transaction]
    ) -> list[FlaggedInsight]:
        by_category_month: dict[str, dict[str, float]] = defaultdict(
            lambda: defaultdict(float)
        )
        for item in transactions:
            if item.transaction_type == "expense":
                by_category_month[item.category][item.posted_at.strftime("%Y-%m")] += item.amount

        insights: list[FlaggedInsight] = []
        for category, month_totals in by_category_month.items():
            months = sorted(month_totals)
            for previous_month, month in zip(months, months[1:]):
                previous = month_totals[previous_month]
                current = month_totals[month]
                threshold = max(
                    previous * self.CATEGORY_SPIKE_MULTIPLIER,
                    previous + self.CATEGORY_SPIKE_MIN_INCREASE,
                )
                if current <= threshold:
                    continue
                insights.append(
                    FlaggedInsight(
                        rule_id="category_monthly_spike",
                        title=f"{category.title()} spending increased",
                        explanation=(
                            f"{category.title()} spending was {current:,.2f} in {month}, "
                            f"up from {previous:,.2f} in the prior observed month "
                            f"({previous_month}); the increase exceeded the rule threshold "
                            f"of {threshold:,.2f}."
                        ),
                        severity="high" if current - previous >= 1_000 else "medium",
                    )
                )
        return insights
