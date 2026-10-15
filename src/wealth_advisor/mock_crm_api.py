"""Local FastAPI mock CRM backed by the included sample JSON file."""

import json
import logging

from fastapi import FastAPI, HTTPException
from pydantic import ValidationError

from wealth_advisor.config import Settings
from wealth_advisor.models import ClientProfile

logger = logging.getLogger(__name__)
app = FastAPI(
    title="Wealth Advisor Mock CRM",
    description="Local-only REST API serving fictional sample client profiles.",
    version="1.0.0",
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/clients/{client_id}", response_model=ClientProfile)
def get_client(client_id: str) -> ClientProfile:
    data_path = Settings.from_env().crm_data_path
    try:
        with data_path.open("r", encoding="utf-8") as source:
            records = json.load(source)
    except FileNotFoundError as exc:
        logger.exception("Mock CRM data file is missing: %s", data_path)
        raise HTTPException(status_code=500, detail="Mock CRM data file is missing.") from exc
    except json.JSONDecodeError as exc:
        logger.exception("Mock CRM data file contains invalid JSON.")
        raise HTTPException(status_code=500, detail="Mock CRM data file is invalid JSON.") from exc
    except OSError as exc:
        logger.exception("Mock CRM data file could not be read.")
        raise HTTPException(status_code=500, detail="Mock CRM data file could not be read.") from exc

    if not isinstance(records, list):
        raise HTTPException(status_code=500, detail="Mock CRM data must be a JSON list.")
    for record in records:
        if isinstance(record, dict) and record.get("client_id") == client_id:
            try:
                return ClientProfile.model_validate(record)
            except ValidationError as exc:
                logger.exception("Mock CRM profile for %s failed validation.", client_id)
                raise HTTPException(
                    status_code=500,
                    detail="Mock CRM profile failed validation.",
                ) from exc
    raise HTTPException(status_code=404, detail=f"Client '{client_id}' was not found.")
