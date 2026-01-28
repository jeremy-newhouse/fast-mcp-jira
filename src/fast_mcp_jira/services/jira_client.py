"""HTTP client for JIRA API requests."""

import base64
import logging
from typing import Any

import httpx

from ..config import Settings

logger = logging.getLogger(__name__)


class JiraError(Exception):
    """Exception raised for JIRA API errors."""

    def __init__(self, message: str, status_code: int | None = None, details: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.details = details


class JiraClient:
    """Async HTTP client for JIRA Cloud API."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self._client: httpx.AsyncClient | None = None

    def _get_auth_header(self) -> str:
        """Generate Basic auth header value."""
        credentials = f"{self.settings.jira_email}:{self.settings.jira_api_token}"
        encoded = base64.b64encode(credentials.encode()).decode()
        return f"Basic {encoded}"

    @property
    def client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.settings.base_url,
                headers={
                    "Authorization": self._get_auth_header(),
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                verify=self.settings.jira_ssl_verify,
                timeout=30.0,
            )
            logger.info(
                "JIRA client initialized for %s (SSL verify: %s)",
                self.settings.base_url,
                self.settings.jira_ssl_verify,
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    def _handle_error(self, response: httpx.Response) -> None:
        """Handle error responses from JIRA."""
        try:
            error_data = response.json()
        except Exception:
            error_data = {"message": response.text}

        # Extract error message from JIRA's error format
        if isinstance(error_data, dict):
            message = error_data.get("message") or error_data.get("errorMessages", [])
            if isinstance(message, list):
                message = "; ".join(message) if message else "Unknown error"
            errors = error_data.get("errors", {})
            if errors:
                field_errors = [f"{k}: {v}" for k, v in errors.items()]
                if message:
                    message = f"{message} - {'; '.join(field_errors)}"
                else:
                    message = "; ".join(field_errors)
        else:
            message = str(error_data)

        raise JiraError(
            message=f"JIRA API error ({response.status_code}): {message}",
            status_code=response.status_code,
            details=error_data,
        )

    async def get(
        self, path: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any] | list[Any]:
        """Make a GET request to JIRA API."""
        logger.debug("GET %s params=%s", path, params)
        response = await self.client.get(path, params=params)
        if not response.is_success:
            self._handle_error(response)
        return response.json() if response.content else {}

    async def post(
        self,
        path: str,
        body: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Make a POST request to JIRA API."""
        logger.debug("POST %s body=%s params=%s", path, body, params)
        response = await self.client.post(path, json=body, params=params)
        if not response.is_success:
            self._handle_error(response)
        return response.json() if response.content else {}

    async def put(self, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        """Make a PUT request to JIRA API."""
        logger.debug("PUT %s body=%s", path, body)
        response = await self.client.put(path, json=body)
        if not response.is_success:
            self._handle_error(response)
        return response.json() if response.content else {}

    async def patch(self, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        """Make a PATCH request to JIRA API."""
        logger.debug("PATCH %s body=%s", path, body)
        response = await self.client.patch(path, json=body)
        if not response.is_success:
            self._handle_error(response)
        return response.json() if response.content else {}

    async def delete(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Make a DELETE request to JIRA API."""
        logger.debug("DELETE %s params=%s", path, params)
        response = await self.client.delete(path, params=params)
        if not response.is_success:
            self._handle_error(response)
        return response.json() if response.content else {}

    async def post_multipart(
        self,
        path: str,
        filename: str,
        content: bytes,
        content_type: str = "application/octet-stream",
    ) -> dict[str, Any]:
        """Make a multipart POST request for file uploads."""
        logger.debug("POST multipart %s filename=%s", path, filename)
        files = {"file": (filename, content, content_type)}
        # Need to override content-type header for multipart
        headers = {
            "Authorization": self._get_auth_header(),
            "Accept": "application/json",
            "X-Atlassian-Token": "no-check",  # Required for attachment uploads
        }
        async with httpx.AsyncClient(
            base_url=self.settings.base_url,
            verify=self.settings.jira_ssl_verify,
            timeout=60.0,
        ) as client:
            response = await client.post(path, files=files, headers=headers)
        if not response.is_success:
            self._handle_error(response)
        return response.json() if response.content else {}
