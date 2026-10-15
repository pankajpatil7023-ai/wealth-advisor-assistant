"""Interactive command-line runner for the end-to-end workflow."""

import argparse
import json
import logging
import os
from pathlib import Path
from uuid import uuid4

from wealth_advisor.agents.analyzer import AnalyzerAgent
from wealth_advisor.agents.data_fetcher import DataFetcherAgent
from wealth_advisor.agents.orchestrator import OrchestratorAgent
from wealth_advisor.config import Settings
from wealth_advisor.logging_config import configure_logging
from wealth_advisor.models import FlaggedInsight, ReviewDecision
from wealth_advisor.tools.client_data import JsonFinancialDataTool
from wealth_advisor.tools.crm_client import HttpCrmClient
from wealth_advisor.tools.memory import MemoryStore

logger = logging.getLogger(__name__)


def _review_in_terminal(insights: list[FlaggedInsight]) -> list[ReviewDecision]:
    decisions: list[ReviewDecision] = []
    print("\nHuman review required before flagged insights enter the final report.")
    for index, insight in enumerate(insights, start=1):
        print(f"\n[{index}/{len(insights)}] {insight.title} ({insight.severity})")
        print(f"Rule: {insight.rule_id}")
        print(insight.explanation)
        answer = input("Approve this insight? [y/N]: ").strip().casefold()
        decisions.append(
            ReviewDecision(
                insight_id=insight.insight_id,
                decision="approved" if answer in {"y", "yes"} else "rejected",
                reviewer="local CLI reviewer",
            )
        )
    return decisions


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Analyze fictional client finances with a reviewable multi-agent workflow."
    )
    parser.add_argument("--client-id", default="client-001")
    parser.add_argument("--data", type=Path, help="Override the financial JSON file.")
    parser.add_argument("--session-id", default=None)
    parser.add_argument(
        "--no-review",
        action="store_true",
        help="Skip interactive review. Flagged insights are safely excluded.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings = Settings.from_env()
    configure_logging(settings.log_file, os.getenv("LOG_LEVEL", "INFO"))
    data_path = args.data or settings.financial_data_path
    if not data_path.is_absolute():
        data_path = Path.cwd() / data_path

    fetcher = DataFetcherAgent(
        financial_tool=JsonFinancialDataTool(),
        crm_tool=HttpCrmClient(settings.crm_base_url),
    )
    orchestrator = OrchestratorAgent(
        data_fetcher=fetcher,
        analyzer=AnalyzerAgent(),
        memory=MemoryStore(settings.memory_dir),
        review_handler=None if args.no_review else _review_in_terminal,
    )
    report = orchestrator.run(
        client_id=args.client_id,
        data_path=str(data_path),
        session_id=args.session_id or str(uuid4()),
    )

    output_path = Path.cwd() / "outputs" / "generated_report.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as destination:
        json.dump(report.model_dump(mode="json"), destination, indent=2)
        destination.write("\n")

    print("\nFinal report")
    print(json.dumps(report.model_dump(mode="json"), indent=2))
    print(f"\nSaved report to: {output_path}")
    logger.info("CLI run finished; report saved to %s", output_path)
    return 0 if report.analysis is not None else 1
