"""Entry point for the Fast MCP JIRA server."""

from .config import get_settings
from .logging_config import get_logger, setup_logging


def main() -> None:
    """Run the Fast MCP JIRA server."""
    settings = get_settings()

    # Setup logging with configured format
    setup_logging(
        level=settings.log_level,
        json_format=settings.log_format.lower() == "json",
    )

    logger = get_logger(__name__)

    from .server import mcp

    logger.info("Starting Fast MCP JIRA server")
    logger.info(
        "Server configuration",
        extra={
            "jira_url": settings.base_url,
            "ssl_verify": settings.jira_ssl_verify,
            "host": settings.mcp_host,
            "port": settings.mcp_port,
            "cache_enabled": settings.cache_enabled,
            "auth_enabled": settings.mcp_api_key is not None,
        },
    )

    # Run with Streamable HTTP transport
    mcp.run(transport="http", host=settings.mcp_host, port=settings.mcp_port)


if __name__ == "__main__":
    main()
