"""Small environment-backed settings object for local runs."""

from dataclasses import dataclass
import os
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")


def _project_path(value: str | None, default: str) -> Path:
    path = Path(value or default).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


@dataclass(frozen=True)
class Settings:
    crm_base_url: str
    crm_port: int
    financial_data_path: Path
    crm_data_path: Path
    memory_dir: Path
    log_file: Path

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            crm_base_url=os.getenv("CRM_BASE_URL", "http://127.0.0.1:8000").rstrip("/"),
            crm_port=int(os.getenv("CRM_PORT", "8000")),
            financial_data_path=_project_path(
                os.getenv("FINANCIAL_DATA_PATH"), "data/client_financials.json"
            ),
            crm_data_path=_project_path(
                os.getenv("CRM_DATA_PATH"), "data/mock_crm_clients.json"
            ),
            memory_dir=_project_path(os.getenv("MEMORY_DIR"), "data/history"),
            log_file=_project_path(os.getenv("LOG_FILE"), "logs/wealth-advisor.log"),
        )
