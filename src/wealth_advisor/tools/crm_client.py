"""CRM tool abstraction and its HTTP implementation."""

from typing import Protocol

import httpx

from wealth_advisor.models import ClientProfile


class CrmTool(Protocol):
    def get_client_profile(self, client_id: str) -> ClientProfile: ...


class HttpCrmClient:
    """Small adapter around the mock CRM REST API."""

    def __init__(self, base_url: str, timeout_seconds: float = 3.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def get_client_profile(self, client_id: str) -> ClientProfile:
        try:
            response = httpx.get(
                f"{self.base_url}/clients/{client_id}",
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            return ClientProfile.model_validate(response.json())
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                raise ValueError(f"CRM has no profile for client '{client_id}'.") from exc
            raise ValueError(
                f"CRM returned HTTP {exc.response.status_code} for client '{client_id}'."
            ) from exc
        except httpx.TimeoutException as exc:
            raise ValueError("CRM request timed out.") from exc
        except httpx.RequestError as exc:
            raise ValueError(f"CRM is unavailable: {exc.__class__.__name__}.") from exc
        except ValueError:
            raise
        except Exception as exc:
            raise ValueError(f"CRM response was invalid: {exc}") from exc
