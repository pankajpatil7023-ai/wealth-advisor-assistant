"""Fetch and validate local financial data and CRM context."""

import logging
from pathlib import Path

from wealth_advisor.models import ClientFinancials, ClientProfile
from wealth_advisor.tools.client_data import FinancialDataTool
from wealth_advisor.tools.crm_client import CrmTool

logger = logging.getLogger(__name__)


class DataFetcherAgent:
    def __init__(self, financial_tool: FinancialDataTool, crm_tool: CrmTool) -> None:
        self.financial_tool = financial_tool
        self.crm_tool = crm_tool

    def run(
        self, client_id: str, data_path: Path
    ) -> tuple[ClientFinancials | None, ClientProfile | None, list[str], list[str]]:
        logger.info("Data fetcher started for client %s", client_id)
        financial_data: ClientFinancials | None = None
        crm_profile: ClientProfile | None = None
        warnings: list[str] = []
        errors: list[str] = []

        try:
            candidate = self.financial_tool.load(data_path)
            if candidate.client_id != client_id:
                errors.append(
                    f"Financial file is for client '{candidate.client_id}', "
                    f"not requested client '{client_id}'."
                )
                logger.error(errors[-1])
            else:
                financial_data = candidate
                if not candidate.transactions:
                    warnings.append("No transactions were found in the financial data.")
                    logger.warning(warnings[-1])
        except (ValueError, OSError) as exc:
            errors.append(str(exc))
            logger.error("Financial data fetch failed: %s", exc)

        try:
            crm_profile = self.crm_tool.get_client_profile(client_id)
            logger.info("Loaded CRM profile for client %s", client_id)
        except (ValueError, OSError) as exc:
            warnings.append(f"CRM context could not be loaded: {exc}")
            logger.warning(warnings[-1])

        logger.info(
            "Data fetcher finished for %s (financial_data=%s, crm_profile=%s)",
            client_id,
            financial_data is not None,
            crm_profile is not None,
        )
        return financial_data, crm_profile, warnings, errors
