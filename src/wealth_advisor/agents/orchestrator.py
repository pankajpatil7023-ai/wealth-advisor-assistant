"""LangGraph workflow coordinating the fetch, analyze, review, and report steps."""

import logging
from pathlib import Path
from typing import Callable, TypedDict
from uuid import uuid4

from langgraph.graph import END, START, StateGraph

from wealth_advisor.agents.analyzer import AnalyzerAgent
from wealth_advisor.agents.data_fetcher import DataFetcherAgent
from wealth_advisor.models import (
    AnalysisResult,
    ClientFinancials,
    ClientProfile,
    FinalReport,
    FlaggedInsight,
    HistoricalSummary,
    ReviewDecision,
)
from wealth_advisor.tools.memory import MemoryStore

logger = logging.getLogger(__name__)
ReviewHandler = Callable[[list[FlaggedInsight]], list[ReviewDecision]]


class WorkflowState(TypedDict, total=False):
    client_id: str
    session_id: str
    data_path: str
    financial_data: ClientFinancials | None
    client_profile: ClientProfile | None
    analysis: AnalysisResult | None
    review_decisions: list[ReviewDecision]
    previous_summaries: list[HistoricalSummary]
    warnings: list[str]
    errors: list[str]
    final_report: FinalReport


class OrchestratorAgent:
    def __init__(
        self,
        data_fetcher: DataFetcherAgent,
        analyzer: AnalyzerAgent,
        memory: MemoryStore,
        review_handler: ReviewHandler | None = None,
    ) -> None:
        self.data_fetcher = data_fetcher
        self.analyzer = analyzer
        self.memory = memory
        self.review_handler = review_handler
        self.graph = self._build_graph()

    def _build_graph(self):
        workflow = StateGraph(WorkflowState)
        workflow.add_node("fetch_data", self._fetch_data)
        workflow.add_node("analyze", self._analyze)
        workflow.add_node("human_review", self._human_review)
        workflow.add_node("finalize", self._finalize)
        workflow.add_edge(START, "fetch_data")
        workflow.add_conditional_edges(
            "fetch_data",
            self._route_after_fetch,
            {"analyze": "analyze", "finalize": "finalize"},
        )
        workflow.add_edge("analyze", "human_review")
        workflow.add_edge("human_review", "finalize")
        workflow.add_edge("finalize", END)
        return workflow.compile()

    def run(
        self,
        client_id: str,
        data_path: str,
        session_id: str | None = None,
    ) -> FinalReport:
        run_id = session_id or str(uuid4())
        logger.info("Orchestrator started for client %s (session %s)", client_id, run_id)
        state = self.graph.invoke(
            {
                "client_id": client_id,
                "session_id": run_id,
                "data_path": data_path,
                "financial_data": None,
                "client_profile": None,
                "analysis": None,
                "review_decisions": [],
                "previous_summaries": self.memory.get_recent_summaries(client_id),
                "warnings": [],
                "errors": [],
            }
        )
        report = state["final_report"]
        logger.info(
            "Orchestrator finished for client %s (session %s, approved=%d, rejected=%d)",
            client_id,
            run_id,
            len(report.approved_insights),
            report.rejected_insight_count,
        )
        return report

    def _fetch_data(self, state: WorkflowState) -> WorkflowState:
        financial_data, client_profile, warnings, errors = self.data_fetcher.run(
            state["client_id"],
            data_path=Path(state["data_path"]),
        )
        return {
            "financial_data": financial_data,
            "client_profile": client_profile,
            "warnings": [*state.get("warnings", []), *warnings],
            "errors": [*state.get("errors", []), *errors],
        }

    def _route_after_fetch(self, state: WorkflowState) -> str:
        if state.get("financial_data") is None:
            logger.warning("Skipping analysis because validated financial data is unavailable.")
            return "finalize"
        return "analyze"

    def _analyze(self, state: WorkflowState) -> WorkflowState:
        financial_data = state.get("financial_data")
        if financial_data is None:
            return {"analysis": None}
        try:
            return {"analysis": self.analyzer.analyze(financial_data)}
        except Exception as exc:
            message = f"Analysis could not be completed: {exc}"
            logger.exception(message)
            return {
                "analysis": None,
                "errors": [*state.get("errors", []), message],
            }

    def _human_review(self, state: WorkflowState) -> WorkflowState:
        analysis = state.get("analysis")
        if analysis is None or not analysis.flagged_insights:
            logger.info("Human review skipped; there are no flagged insights.")
            return {"review_decisions": []}

        insights = analysis.flagged_insights
        if self.review_handler is None:
            logger.warning(
                "No human reviewer was provided; all %d flagged insight(s) were rejected.",
                len(insights),
            )
            return {
                "review_decisions": [
                    ReviewDecision(insight_id=item.insight_id, decision="rejected")
                    for item in insights
                ],
                "warnings": [
                    *state.get("warnings", []),
                    "No human reviewer was available; flagged insights were excluded from the final report.",
                ],
            }

        try:
            requested = self.review_handler(insights)
        except Exception as exc:
            logger.exception("Human review callback failed; rejecting all flagged insights.")
            return {
                "review_decisions": [
                    ReviewDecision(insight_id=item.insight_id, decision="rejected")
                    for item in insights
                ],
                "warnings": [
                    *state.get("warnings", []),
                    f"Human review failed; flagged insights were excluded: {exc}",
                ],
            }

        valid_ids = {item.insight_id for item in insights}
        decisions_by_id: dict[str, ReviewDecision] = {}
        for decision in requested:
            if decision.insight_id in valid_ids:
                decisions_by_id[decision.insight_id] = decision
            else:
                logger.warning("Ignoring review decision for unknown insight %s", decision.insight_id)
        decisions = [
            decisions_by_id.get(
                item.insight_id,
                ReviewDecision(insight_id=item.insight_id, decision="rejected"),
            )
            for item in insights
        ]
        logger.info(
            "Human review completed: %d approved, %d rejected",
            sum(item.decision == "approved" for item in decisions),
            sum(item.decision == "rejected" for item in decisions),
        )
        return {"review_decisions": decisions}

    def _finalize(self, state: WorkflowState) -> WorkflowState:
        analysis = state.get("analysis")
        decisions = state.get("review_decisions", [])
        approved_ids = {
            decision.insight_id
            for decision in decisions
            if decision.decision == "approved"
        }
        approved_insights = (
            [
                item
                for item in analysis.flagged_insights
                if item.insight_id in approved_ids
            ]
            if analysis
            else []
        )
        rejected_count = (
            len(analysis.flagged_insights) - len(approved_insights)
            if analysis
            else 0
        )
        report = FinalReport(
            client_id=state["client_id"],
            session_id=state["session_id"],
            client_profile=state.get("client_profile"),
            analysis=analysis,
            approved_insights=approved_insights,
            rejected_insight_count=rejected_count,
            review_decisions=decisions,
            previous_summaries=state.get("previous_summaries", []),
            warnings=state.get("warnings", []),
            errors=state.get("errors", []),
        )

        if analysis is not None:
            summary = HistoricalSummary(
                client_id=state["client_id"],
                session_id=state["session_id"],
                total_income=analysis.total_income,
                total_expenses=analysis.total_expenses,
                net_cash_flow=analysis.net_cash_flow,
                approved_insight_count=len(approved_insights),
            )
            try:
                self.memory.save_summary(summary)
                self.memory.add_session_note(
                    state["session_id"],
                    f"Completed analysis for {state['client_id']}: "
                    f"{len(approved_insights)} insight(s) approved.",
                )
            except (OSError, ValueError) as exc:
                message = f"Report completed, but memory could not be saved: {exc}"
                logger.exception(message)
                report.warnings.append(message)
        else:
            logger.warning(
                "Finalizing a partial report for %s because analysis did not run.",
                state["client_id"],
            )

        logger.info(
            "Final report prepared for %s: %d approved insight(s)",
            state["client_id"],
            len(report.approved_insights),
        )
        return {"final_report": report}
