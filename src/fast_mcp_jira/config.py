"""Configuration settings for the Fast MCP JIRA server.

This module provides configuration management using pydantic-settings.
Settings are loaded from environment variables and .env files.

Environment Variables:
    JIRA_URL: JIRA instance URL (required)
    JIRA_EMAIL: User email for authentication (required)
    JIRA_API_TOKEN: API token for authentication (required)
    JIRA_SSL_VERIFY: Enable SSL verification (default: true)
    MCP_HOST: Server bind address (default: 127.0.0.1)
    MCP_PORT: Server port (default: 5472)
    LOG_LEVEL: Logging level (default: INFO)
    LOG_FORMAT: Log format - "console" or "json" (default: console)
    REQUEST_TIMEOUT: HTTP request timeout in seconds (default: 30.0)
    UPLOAD_TIMEOUT: File upload timeout in seconds (default: 60.0)
    RATE_LIMIT_PER_SECOND: API rate limit (default: 10.0)
    RATE_LIMIT_BURST: Rate limit burst size (default: 20)
    MCP_API_KEY: API key for MCP endpoint authentication (optional)

Cache Settings:
    CACHE_ENABLED: Enable SQLite caching (default: true)
    CACHE_DB_PATH: Path to cache database (default: ~/.fast-mcp-jira/cache.db)
    CACHE_TTL_METADATA: TTL for metadata in seconds (default: 2592000 = 30 days)
    CACHE_TTL_PROJECTS: TTL for projects in seconds (default: 2592000 = 30 days)
    CACHE_TTL_AGILE: TTL for agile data in seconds (default: 2592000 = 30 days)
    CACHE_TTL_USERS: TTL for user data in seconds (default: 2592000 = 30 days)
    CACHE_CLEANUP_INTERVAL: Cleanup interval in seconds (default: 86400 = daily)
    CACHE_MAX_ENTRIES: Maximum cache entries (default: 10000)

Cache Encryption Settings:
    CACHE_ENCRYPTION_ENABLED: Enable SQLite encryption (default: false)
    CACHE_ENCRYPTION_KEY: Encryption key (min 32 chars, use openssl rand -hex 32)
    CACHE_ENCRYPTION_KEY_FILE: Path to file containing encryption key

Bulk Operation Settings:
    BULK_MAX_BATCH_SIZE: Maximum issues per bulk operation (default: 100)
    BULK_CONCURRENT_REQUESTS: Concurrent requests for bulk ops (default: 10)
"""

import hashlib
import ipaddress
import os
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse

from pydantic_settings import BaseSettings, SettingsConfigDict


def _is_private_or_internal_ip(hostname: str) -> bool:
    """Check if hostname is a private, loopback, or link-local IP.

    This prevents SSRF attacks by blocking requests to internal networks.

    Args:
        hostname: The hostname or IP address to check.

    Returns:
        True if the hostname is a private/internal IP, False otherwise.
    """
    if not hostname:
        return False
    try:
        ip = ipaddress.ip_address(hostname)
        return ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved
    except ValueError:
        # Not a valid IP address - likely a hostname, which is OK
        return False


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    All settings can be configured via environment variables or a .env file.
    Required settings will raise an error if not provided.

    Attributes:
        jira_url: JIRA Cloud instance URL.
        jira_email: Email address for JIRA authentication.
        jira_api_token: API token for JIRA authentication.
        jira_ssl_verify: Whether to verify SSL certificates.
        mcp_host: Server bind address.
        mcp_port: Server port number.
        log_level: Python logging level.
        log_format: Log format - "console" or "json".
        request_timeout: HTTP request timeout in seconds.
        upload_timeout: File upload timeout in seconds.
        rate_limit_per_second: Maximum requests per second.
        rate_limit_burst: Maximum burst requests.
        mcp_api_key: API key for MCP endpoint authentication.
        cache_enabled: Whether SQLite caching is enabled.
        cache_db_path: Path to cache database file.
        cache_ttl_metadata: TTL for metadata (issue types, priorities).
        cache_ttl_projects: TTL for project data.
        cache_ttl_agile: TTL for agile data (boards, sprints).
        cache_ttl_users: TTL for user search results.
        cache_cleanup_interval: Background cleanup interval.
        cache_max_entries: Maximum cache entries before cleanup.
        bulk_max_batch_size: Maximum issues per bulk operation.
        bulk_concurrent_requests: Concurrent requests for bulk ops.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Required JIRA configuration
    jira_url: str
    jira_email: str
    jira_api_token: str

    # Optional SSL configuration
    jira_ssl_verify: bool = True

    # Server configuration
    mcp_host: str = "127.0.0.1"
    mcp_port: int = 5472  # JIRA on phone keypad: J=5, I=4, R=7, A=2

    # Logging
    log_level: str = "INFO"
    log_format: str = "console"  # "console" or "json"

    # HTTP client timeouts (in seconds)
    request_timeout: float = 30.0
    upload_timeout: float = 60.0

    # Rate limiting configuration
    rate_limit_per_second: float = 10.0
    rate_limit_burst: int = 20

    # MCP endpoint authentication (optional)
    # If set, clients must provide this key in the Authorization header
    mcp_api_key: str | None = None

    # Cache configuration
    cache_enabled: bool = True
    cache_db_path: str = "~/.fast-mcp-jira/cache.db"
    cache_ttl_metadata: int = 2592000  # 30 days - issue types, priorities, statuses
    cache_ttl_projects: int = 2592000  # 30 days - projects, components, versions
    cache_ttl_agile: int = 2592000  # 30 days - boards, sprints
    cache_ttl_users: int = 2592000  # 30 days - user search results
    cache_cleanup_interval: int = 86400  # Run cleanup daily
    cache_max_entries: int = 10000  # Maximum cache entries

    # Cache encryption (optional - requires sqlcipher3-binary)
    cache_encryption_enabled: bool = False
    cache_encryption_key: str | None = None
    cache_encryption_key_file: str | None = None

    # Bulk operation configuration
    bulk_max_batch_size: int = 100  # Maximum issues per bulk operation
    bulk_concurrent_requests: int = 10  # Concurrent requests for bulk ops

    @property
    def cache_db_full_path(self) -> Path:
        """Get expanded cache database path."""
        path = Path(os.path.expanduser(self.cache_db_path))
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def base_url(self) -> str:
        """Get the full JIRA base URL.

        Security: Validates that the URL does not point to private/internal
        IP addresses to prevent SSRF attacks.

        Raises:
            ValueError: If the URL points to a private/internal IP.
        """
        url = self.jira_url.strip()

        # Add https:// if no protocol specified
        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"

        # Add .atlassian.net if it looks like just a site name (no dots in domain)
        if "." not in url.split("://", 1)[1]:
            url = f"{url}.atlassian.net"

        # SSRF Prevention: Block private/internal IP addresses
        parsed = urlparse(url)
        hostname = parsed.hostname or ""
        if _is_private_or_internal_ip(hostname):
            raise ValueError(
                f"JIRA URL points to private/internal IP address: {hostname}. "
                "This is blocked for security reasons (SSRF prevention)."
            )

        return url.rstrip("/")

    @property
    def cache_partition_key(self) -> str:
        """Get cache partition key for isolating cache per user.

        Combines JIRA URL with MCP API Key (if set) to ensure:
        - Different JIRA instances have separate caches
        - Different users (API keys) have separate caches
        - Same user's cache persists across sessions

        Returns:
            A stable hash string identifying this user's cache partition.
        """
        # Include JIRA URL for instance isolation
        key_parts = [self.base_url]

        # Include MCP API Key for user isolation (if configured)
        if self.mcp_api_key:
            key_parts.append(self.mcp_api_key)
        else:
            # Fall back to JIRA credentials for user isolation
            key_parts.append(self.jira_email)

        combined = ":".join(key_parts)
        return hashlib.sha256(combined.encode()).hexdigest()[:16]

    @property
    def cache_encryption_key_resolved(self) -> str | None:
        """Resolve cache encryption key from env var or file.

        Priority:
        1. CACHE_ENCRYPTION_KEY environment variable (direct key)
        2. CACHE_ENCRYPTION_KEY_FILE (path to file containing key)

        Returns:
            The encryption key if encryption is enabled, None otherwise.

        Raises:
            ValueError: If encryption is enabled but no valid key is provided,
                or if the key is too short (< 32 characters).
            FileNotFoundError: If the key file doesn't exist.
            PermissionError: If the key file has insecure permissions.
        """
        if not self.cache_encryption_enabled:
            return None

        # Priority 1: Direct environment variable
        if self.cache_encryption_key:
            if len(self.cache_encryption_key) < 32:
                raise ValueError(
                    "Cache encryption key must be at least 32 characters. "
                    "Generate with: openssl rand -hex 32"
                )
            return self.cache_encryption_key

        # Priority 2: Key file
        if self.cache_encryption_key_file:
            key_path = Path(os.path.expanduser(self.cache_encryption_key_file))
            if not key_path.exists():
                raise FileNotFoundError(f"Cache encryption key file not found: {key_path}")

            # Security: Verify restrictive permissions (owner read/write only)
            stat = key_path.stat()
            if stat.st_mode & 0o077:  # Check if group/other have any permissions
                raise PermissionError(
                    f"Encryption key file has insecure permissions: {oct(stat.st_mode)}. "
                    "Must be 0o600 (owner read/write only). Fix with: chmod 600 <file>"
                )

            key = key_path.read_text().strip()
            if len(key) < 32:
                raise ValueError("Cache encryption key from file must be at least 32 characters")
            return key

        raise ValueError(
            "Cache encryption enabled but no key provided. "
            "Set CACHE_ENCRYPTION_KEY or CACHE_ENCRYPTION_KEY_FILE"
        )


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
