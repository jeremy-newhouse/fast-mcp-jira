"""Tests for API key authentication.

These tests verify the ApiKeyVerifier class properly validates
API keys with timing-safe comparison.
"""

import pytest

from fast_mcp_jira.auth import ApiKeyVerifier


class TestApiKeyVerifier:
    """Tests for API key authentication."""

    @pytest.fixture
    def verifier(self):
        """Create a verifier with a known API key."""
        return ApiKeyVerifier(api_key="test-secret-key-123")

    @pytest.mark.asyncio
    async def test_valid_api_key(self, verifier):
        """Valid API key should return an AccessToken."""
        result = await verifier.verify_token("test-secret-key-123")
        assert result is not None
        assert result.client_id == "api-key-client"
        assert result.scopes == []
        assert result.expires_at is None

    @pytest.mark.asyncio
    async def test_invalid_api_key(self, verifier):
        """Invalid API key should return None."""
        result = await verifier.verify_token("wrong-key")
        assert result is None

    @pytest.mark.asyncio
    async def test_empty_api_key(self, verifier):
        """Empty API key should return None."""
        result = await verifier.verify_token("")
        assert result is None

    @pytest.mark.asyncio
    async def test_partial_api_key(self, verifier):
        """Partial API key should return None."""
        result = await verifier.verify_token("test-secret")
        assert result is None

    @pytest.mark.asyncio
    async def test_api_key_with_extra_characters(self, verifier):
        """API key with extra characters should return None."""
        result = await verifier.verify_token("test-secret-key-123-extra")
        assert result is None

    @pytest.mark.asyncio
    async def test_case_sensitive(self, verifier):
        """API key comparison should be case-sensitive."""
        result = await verifier.verify_token("TEST-SECRET-KEY-123")
        assert result is None
