"""Configuration settings for the Fast MCP JIRA server.

This module provides configuration management using pydantic-settings.
Settings are loaded from environment variables and .env files.

Environment Variables:
    JIRA_URL: JIRA instance URL (required)
    JIRA_EMAIL: User email for authentication (required)
    JIRA_API_TOKEN: API token for authentication (required)
    JIRA_SSL_VERIFY: Enable SSL verification (default: true)
    HOST: Server bind address (default: 0.0.0.0)
    PORT: Server port (default: 5472)
    LOG_LEVEL: Logging level (default: INFO)
    REQUEST_TIMEOUT: HTTP request timeout in seconds (default: 30.0)
    UPLOAD_TIMEOUT: File upload timeout in seconds (default: 60.0)
    RATE_LIMIT_PER_SECOND: API rate limit (default: 10.0)
    RATE_LIMIT_BURST: Rate limit burst size (default: 20)
"""

from functools import lru_cache

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
        host: Server bind address.
        port: Server port number.
        log_level: Python logging level.
        request_timeout: HTTP request timeout in seconds.
        upload_timeout: File upload timeout in seconds.
        rate_limit_per_second: Maximum requests per second.
        rate_limit_burst: Maximum burst requests.
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
    host: str = "0.0.0.0"
    port: int = 5472  # JIRA on phone keypad: J=5, I=4, R=7, A=2

    # Logging
    log_level: str = "INFO"

    # HTTP client timeouts (in seconds)
    request_timeout: float = 30.0
    upload_timeout: float = 60.0

    # Rate limiting configuration
    rate_limit_per_second: float = 10.0
    rate_limit_burst: int = 20

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
