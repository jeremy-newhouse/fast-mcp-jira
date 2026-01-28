"""Configuration settings for the Fast MCP JIRA server."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

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

    @property
    def base_url(self) -> str:
        """Get the full JIRA base URL."""
        url = self.jira_url.strip()

        # Add https:// if no protocol specified
        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"

        # Add .atlassian.net if it looks like just a site name
        if not any(domain in url for domain in [".atlassian.net", ".jira.com", "."]):
            url = f"{url}.atlassian.net"

        # Remove trailing slash
        return url.rstrip("/")


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
