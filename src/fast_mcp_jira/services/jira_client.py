"""HTTP client for JIRA API requests.

This module provides an async HTTP client for communicating with JIRA Cloud API.
It handles authentication, rate limiting, and error handling.

Security Features:
- Rate limiting to prevent API abuse (token bucket algorithm)
- Error message sanitization to avoid leaking sensitive info
- Configurable SSL verification
- Configurable timeouts

Classes:
    RateLimiter: Token bucket rate limiter for API requests
    JiraError: Exception for JIRA API errors
    JiraClient: Main async HTTP client
"""

import asyncio
import base64
import logging
from time import monotonic
from typing import Any

import httpx

from ..config import Settings

logger = logging.getLogger(__name__)

# Maximum error message length to prevent info leakage
MAX_ERROR_MESSAGE_LENGTH = 500


class RateLimiter:
    """Token bucket rate limiter for API requests.

    Prevents overwhelming the JIRA API with too many requests.
    Uses a token bucket algorithm that allows bursting while
    maintaining an average rate limit.

    Args:
        requests_per_second: Average rate limit (default: 10.0)
        burst: Maximum burst size (default: 20)

    Example:
        >>> limiter = RateLimiter(requests_per_second=10.0, burst=20)
        >>> await limiter.acquire()  # Blocks if rate limit exceeded
    """

    def __init__(self, requests_per_second: float = 10.0, burst: int = 20):
        """Initialize the rate limiter.

        Args:
            requests_per_second: Maximum average requests per second.
            burst: Maximum tokens available for burst traffic.
        """
        self.rate = requests_per_second
        self.burst = burst
        self._tokens = float(burst)
        self._last_update = monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Acquire a rate limit token, waiting if necessary.

        This method blocks until a token is available. Tokens are
        replenished at the configured rate.
        """
        async with self._lock:
            now = monotonic()
            elapsed = now - self._last_update
            # Replenish tokens based on elapsed time
            self._tokens = min(self.burst, self._tokens + elapsed * self.rate)
            self._last_update = now

            if self._tokens < 1:
                # Calculate wait time needed for one token
                wait_time = (1 - self._tokens) / self.rate
                logger.debug("Rate limit: waiting %.2fs", wait_time)
                await asyncio.sleep(wait_time)
                self._tokens = 0
            else:
                self._tokens -= 1


class JiraError(Exception):
    """Exception raised for JIRA API errors.

    Contains the HTTP status code and sanitized error details
    from the JIRA API response.

    Attributes:
        status_code: HTTP status code from JIRA
        details: Additional error details (sanitized)
    """

    def __init__(self, message: str, status_code: int | None = None, details: Any = None):
        """Initialize JIRA error.

        Args:
            message: Human-readable error message (sanitized).
            status_code: HTTP status code if available.
            details: Additional error context (sanitized).
        """
        super().__init__(message)
        self.status_code = status_code
        self.details = details


class JiraClient:
    """Async HTTP client for JIRA Cloud API.

    Handles authentication, rate limiting, and error handling for
    all JIRA API requests. Uses httpx for async HTTP operations.

    Security features:
    - Basic Auth with API token (credentials never logged)
    - Rate limiting to prevent API abuse
    - Error message sanitization
    - Configurable SSL verification and timeouts

    Args:
        settings: Application settings containing JIRA credentials.

    Example:
        >>> client = JiraClient(settings)
        >>> result = await client.get("/rest/api/3/myself")
        >>> await client.close()
    """

    def __init__(self, settings: Settings):
        """Initialize JIRA client.

        Args:
            settings: Settings object with JIRA URL, credentials,
                and configuration options.
        """
        self.settings = settings
        self._client: httpx.AsyncClient | None = None
        self._rate_limiter = RateLimiter(
            requests_per_second=settings.rate_limit_per_second,
            burst=settings.rate_limit_burst,
        )

    def _get_auth_header(self) -> str:
        """Generate Basic auth header value.

        Returns:
            Base64-encoded Authorization header value.
        """
        credentials = f"{self.settings.jira_email}:{self.settings.jira_api_token}"
        encoded = base64.b64encode(credentials.encode()).decode()
        return f"Basic {encoded}"

    @property
    def client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client.

        Creates a new client on first access. The client is configured
        with authentication headers, SSL settings, and timeouts.

        Returns:
            Configured httpx.AsyncClient instance.
        """
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.settings.base_url,
                headers={
                    "Authorization": self._get_auth_header(),
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                verify=self.settings.jira_ssl_verify,
                timeout=self.settings.request_timeout,
            )
            logger.info(
                "JIRA client initialized for %s (SSL verify: %s)",
                self.settings.base_url,
                self.settings.jira_ssl_verify,
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client and release resources."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None
            logger.debug("JIRA client closed")

    def _sanitize_error_message(self, message: str) -> str:
        """Sanitize error message to prevent information leakage.

        Args:
            message: Raw error message from JIRA.

        Returns:
            Truncated and sanitized error message.
        """
        if len(message) > MAX_ERROR_MESSAGE_LENGTH:
            message = message[: MAX_ERROR_MESSAGE_LENGTH - 3] + "..."
        return message

    def _handle_error(self, response: httpx.Response) -> None:
        """Handle error responses from JIRA.

        Extracts error information from JIRA's response format and
        raises a JiraError with sanitized details.

        Args:
            response: HTTP response object with error status.

        Raises:
            JiraError: Always raised with error details.
        """
        try:
            error_data = response.json()
        except Exception:
            error_data = {}

        # Extract primary error message
        message = self._extract_primary_message(error_data)

        # Add field-level errors if present
        field_errors = self._extract_field_errors(error_data)
        if field_errors:
            message = f"{message} - {field_errors}" if message else field_errors

        # Sanitize and raise
        message = self._sanitize_error_message(message)
        raise JiraError(
            message=f"JIRA API error ({response.status_code}): {message}",
            status_code=response.status_code,
            details=None,
        )

    def _extract_primary_message(self, error_data: dict) -> str:
        """Extract primary error message from JIRA error response."""
        if not isinstance(error_data, dict):
            return "Request failed"

        message = error_data.get("message")
        if message:
            return str(message)

        error_messages = error_data.get("errorMessages", [])
        if isinstance(error_messages, list) and error_messages:
            return "; ".join(error_messages)

        return "Unknown error"

    def _extract_field_errors(self, error_data: dict) -> str:
        """Extract field-level errors from JIRA error response."""
        if not isinstance(error_data, dict):
            return ""

        errors = error_data.get("errors", {})
        if not errors:
            return ""

        # Filter out internal fields (starting with _)
        field_errors = [f"{k}: {v}" for k, v in errors.items() if not k.startswith("_")]
        return "; ".join(field_errors)

    async def get(
        self, path: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any] | list[Any]:
        """Make a GET request to JIRA API.

        Args:
            path: API endpoint path (e.g., /rest/api/3/issue/PROJ-123).
            params: Optional query parameters.

        Returns:
            Parsed JSON response as dict or list.

        Raises:
            JiraError: If the request fails.
        """
        await self._rate_limiter.acquire()
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
        """Make a POST request to JIRA API.

        Args:
            path: API endpoint path.
            body: JSON request body.
            params: Optional query parameters.

        Returns:
            Parsed JSON response.

        Raises:
            JiraError: If the request fails.
        """
        await self._rate_limiter.acquire()
        logger.debug("POST %s", path)
        response = await self.client.post(path, json=body, params=params)
        if not response.is_success:
            self._handle_error(response)
        return response.json() if response.content else {}

    async def put(self, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        """Make a PUT request to JIRA API.

        Args:
            path: API endpoint path.
            body: JSON request body.

        Returns:
            Parsed JSON response.

        Raises:
            JiraError: If the request fails.
        """
        await self._rate_limiter.acquire()
        logger.debug("PUT %s", path)
        response = await self.client.put(path, json=body)
        if not response.is_success:
            self._handle_error(response)
        return response.json() if response.content else {}

    async def patch(self, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        """Make a PATCH request to JIRA API.

        Args:
            path: API endpoint path.
            body: JSON request body.

        Returns:
            Parsed JSON response.

        Raises:
            JiraError: If the request fails.
        """
        await self._rate_limiter.acquire()
        logger.debug("PATCH %s", path)
        response = await self.client.patch(path, json=body)
        if not response.is_success:
            self._handle_error(response)
        return response.json() if response.content else {}

    async def delete(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Make a DELETE request to JIRA API.

        Args:
            path: API endpoint path.
            params: Optional query parameters.

        Returns:
            Parsed JSON response (often empty).

        Raises:
            JiraError: If the request fails.
        """
        await self._rate_limiter.acquire()
        logger.debug("DELETE %s", path)
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
        """Make a multipart POST request for file uploads.

        Creates a separate client for multipart uploads to handle
        the different content-type requirements.

        Args:
            path: API endpoint path for attachment upload.
            filename: Name of the file being uploaded.
            content: Raw file content bytes.
            content_type: MIME type of the file.

        Returns:
            Parsed JSON response with attachment details.

        Raises:
            JiraError: If the upload fails.
        """
        await self._rate_limiter.acquire()
        logger.debug("POST multipart %s filename=%s size=%d", path, filename, len(content))

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
            timeout=self.settings.upload_timeout,
        ) as client:
            response = await client.post(path, files=files, headers=headers)

        if not response.is_success:
            self._handle_error(response)
        return response.json() if response.content else {}
