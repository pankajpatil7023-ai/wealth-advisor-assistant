"""Start the local mock CRM API."""

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

import uvicorn  # noqa: E402
from wealth_advisor.config import Settings  # noqa: E402


if __name__ == "__main__":
    settings = Settings.from_env()
    uvicorn.run(
        "wealth_advisor.mock_crm_api:app",
        host="127.0.0.1",
        port=settings.crm_port,
        reload=False,
    )
