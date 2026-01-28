"""Entry point for the Fast MCP JIRA server."""

import logging
import sys


def setup_logging() -> None:
    """Configure logging based on settings."""
    from .config import get_settings

    settings = get_settings()
    level = getattr(logging, settings.log_level.upper(), logging.INFO)

    # Configure logging to stderr (stdout is reserved for MCP protocol)
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stderr,
    )


def main() -> None:
    """Run the Fast MCP JIRA server."""
    setup_logging()
    logger = logging.getLogger(__name__)

    from .config import get_settings
    from .server import mcp

    settings = get_settings()

    logger.info("Starting Fast MCP JIRA server")
    logger.info("JIRA URL: %s", settings.base_url)
    logger.info("SSL verification: %s", settings.jira_ssl_verify)
    logger.info("Server: %s:%d", settings.host, settings.port)

    # Run with Streamable HTTP transport
    mcp.run(transport="http", host=settings.host, port=settings.port)


if __name__ == "__main__":
    main()
