"""Simple JSON-backed session notes and per-client historical summaries."""

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

from pydantic import ValidationError

from wealth_advisor.models import HistoricalSummary

logger = logging.getLogger(__name__)
_SAFE_NAME = re.compile(r"[^A-Za-z0-9_.-]+")


class MemoryStore:
    def __init__(self, root: Path) -> None:
        self.root = root

    @staticmethod
    def _safe_name(value: str) -> str:
        name = _SAFE_NAME.sub("_", value.strip())
        if not name or name in {".", ".."}:
            raise ValueError("Memory identifiers must contain safe filename characters.")
        return name

    def get_recent_summaries(
        self, client_id: str, limit: int = 5
    ) -> list[HistoricalSummary]:
        path = self.root / "clients" / f"{self._safe_name(client_id)}.json"
        if not path.exists():
            return []
        try:
            with path.open("r", encoding="utf-8") as source:
                payload = json.load(source)
            summaries = [HistoricalSummary.model_validate(item) for item in payload]
            return summaries[-limit:]
        except (OSError, json.JSONDecodeError, TypeError, ValidationError) as exc:
            logger.warning("Could not read historical memory for %s: %s", client_id, exc)
            return []

    def save_summary(self, summary: HistoricalSummary) -> None:
        path = self.root / "clients" / f"{self._safe_name(summary.client_id)}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        existing = self.get_recent_summaries(summary.client_id, limit=10_000)
        existing.append(summary)
        temporary = path.with_suffix(".tmp")
        with temporary.open("w", encoding="utf-8") as destination:
            json.dump(
                [item.model_dump(mode="json") for item in existing],
                destination,
                indent=2,
            )
            destination.write("\n")
        temporary.replace(path)
        logger.info(
            "Stored historical summary for %s (session %s)",
            summary.client_id,
            summary.session_id,
        )

    def add_session_note(self, session_id: str, note: str) -> None:
        path = self.root / "sessions" / f"{self._safe_name(session_id)}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        notes: list[dict[str, str]] = []
        if path.exists():
            try:
                with path.open("r", encoding="utf-8") as source:
                    notes = json.load(source)
            except (OSError, json.JSONDecodeError, TypeError) as exc:
                logger.warning("Starting fresh session memory for %s: %s", session_id, exc)
        notes.append(
            {
                "created_at": datetime.now(timezone.utc).isoformat(),
                "note": note,
            }
        )
        temporary = path.with_suffix(".tmp")
        with temporary.open("w", encoding="utf-8") as destination:
            json.dump(notes, destination, indent=2)
            destination.write("\n")
        temporary.replace(path)
        logger.info("Stored session note for %s", session_id)
