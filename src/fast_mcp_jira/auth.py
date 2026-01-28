"""API key authentication for the MCP endpoint.

This module provides a simple API key authentication mechanism for the
FastMCP server. When MCP_API_KEY is configured, clients must provide
the key in the Authorization header as a Bearer token.

Security Features:
- Timing-safe comparison to prevent timing attacks
- Optional: disabled when MCP_API_KEY is not set

Usage:
    Set MCP_API_KEY environment variable to enable authentication.
    Clients must include: Authorization: Bearer <api-key>
"""

import hmac

from fastmcp.server.auth import AccessToken, TokenVerifier


class ApiKeyVerifier(TokenVerifier):
    """Simple API key verifier for MCP endpoint authentication.

    This verifier validates that the provided Bearer token matches the
    configured API key. Uses timing-safe comparison to prevent timing attacks.

    Args:
        api_key: The API key that clients must provide.

    Example:
        >>> verifier = ApiKeyVerifier(api_key="secret-key-123")
        >>> # Clients must include: Authorization: Bearer secret-key-123
    """

    def __init__(self, api_key: str):
        """Initialize the API key verifier.

        Args:
            api_key: The API key that clients must provide for authentication.
        """
        super().__init__()
        self.api_key = api_key

    async def verify_token(self, token: str) -> AccessToken | None:
        """Verify the provided token against the configured API key.

        Uses constant-time comparison to prevent timing attacks.

        Args:
            token: The bearer token from the Authorization header.

        Returns:
            AccessToken if the key matches, None otherwise.
        """
        # Use constant-time comparison to prevent timing attacks
        if not hmac.compare_digest(token, self.api_key):
            return None

        # Return a simple access token with no scopes
        return AccessToken(
            token=token,
            client_id="api-key-client",
            scopes=[],
            expires_at=None,
            claims={},
        )
