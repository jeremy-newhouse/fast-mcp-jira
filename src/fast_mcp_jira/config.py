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
    CACHE_TTL_METADATA: TTL for metadata in seconds (default: 86400 = 24h)
    CACHE_TTL_PROJECTS: TTL for projects in seconds (default: 21600 = 6h)
    CACHE_TTL_AGILE: TTL for agile data in seconds (default: 1800 = 30m)
    CACHE_TTL_USERS: TTL for user data in seconds (default: 3600 = 1h)
    CACHE_CLEANUP_INTERVAL: Cleanup interval in seconds (default: 3600)
    CACHE_MAX_ENTRIES: Maximum cache entries (default: 10000)

Bulk Operation Settings:
    BULK_MAX_BATCH_SIZE: Maximum issues per bulk operation (default: 100)
    BULK_CONCURRENT_REQUESTS: Concurrent requests for bulk ops (default: 10)
"""

import os
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


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
    cache_ttl_metadata: int = 86400  # 24 hours - issue types, priorities, statuses
    cache_ttl_projects: int = 21600  # 6 hours - projects, components, versions
    cache_ttl_agile: int = 1800  # 30 minutes - boards, sprints
    cache_ttl_users: int = 3600  # 1 hour - user search results
    cache_cleanup_interval: int = 3600  # Run cleanup every hour
    cache_max_entries: int = 10000  # Maximum cache entries

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
        """Get the full JIRA base URL."""
        url = self.jira_url.strip()

        # Add https:// if no protocol specified
        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"

        # Add .atlassian.net if it looks like just a site name (no dots in domain)
        if "." not in url.split("://", 1)[1]:
            url = f"{url}.atlassian.net"

        return url.rstrip("/")


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
