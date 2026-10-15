"""JSON-backed financial data tool with explicit validation failures."""

import json
import logging
from pathlib import Path
from typing import Protocol

from pydantic import ValidationError

from wealth_advisor.models import ClientFinancials

logger = logging.getLogger(__name__)


class FinancialDataTool(Protocol):
    def load(self, path: Path) -> ClientFinancials: ...


class JsonFinancialDataTool:
    def load(self, path: Path) -> ClientFinancials:
        logger.info("Loading client financial data from %s", path)
        try:
            with path.open("r", encoding="utf-8") as source:
                payload = json.load(source)
        except FileNotFoundError as exc:
            raise ValueError(f"Financial data file was not found: {path}") from exc
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Financial data file contains invalid JSON at line {exc.lineno}, "
                f"column {exc.colno}."
            ) from exc
        except OSError as exc:
            raise ValueError(f"Could not read financial data file: {exc}") from exc

        try:
            return ClientFinancials.model_validate(payload)
        except ValidationError as exc:
            details = "; ".join(
                f"{'.'.join(str(part) for part in issue['loc'])}: {issue['msg']}"
                for issue in exc.errors()
            )
            raise ValueError(f"Financial data is missing or has invalid fields: {details}") from exc
