"""FastMCP server instance and tool registration.

This module initializes the FastMCP server with all JIRA tools,
authentication, and caching services.

Global instances:
    settings: Application settings
    jira: JIRA HTTP client
    cache: SQLite cache service (may be None if disabled)
    mcp: FastMCP server instance
"""

import time

from fastmcp import FastMCP
from fastmcp.server.lifespan import lifespan

from .auth import ApiKeyVerifier
from .config import get_settings
from .logging_config import get_logger
from .services.cache import CacheService
from .services.jira_client import JiraClient

logger = get_logger(__name__)

# Initialize settings and JIRA client
settings = get_settings()
jira = JiraClient(settings)

# Initialize cache service (if enabled)
cache: CacheService | None = None
if settings.cache_enabled:
    cache = CacheService(settings)

# Configure authentication if API key is set
auth_provider = None
if settings.mcp_api_key:
    auth_provider = ApiKeyVerifier(api_key=settings.mcp_api_key)
else:
    # Security warning: unauthenticated access
    logger.warning(
        "MCP_API_KEY not set - endpoint is UNAUTHENTICATED. "
        "Set MCP_API_KEY environment variable for production deployments."
    )


@lifespan
async def app_lifespan(server: FastMCP) -> dict:
    """Initialize and cleanup server services."""
    logger.info("Starting JIRA MCP server services")

    # Startup: initialize cache
    if cache:
        await cache.initialize()
        logger.info(
            "Cache service initialized",
            extra={"cache_enabled": True, "cache_path": str(settings.cache_db_full_path)},
        )

    try:
        yield {"cache": cache, "jira": jira}
    finally:
        # Shutdown: cleanup services with timing
        logger.info("Shutdown initiated")
        start_time = time.time()

        # Close JIRA client
        try:
            await jira.close()
            logger.info(
                "JIRA client closed",
                extra={"elapsed_ms": round((time.time() - start_time) * 1000, 2)},
            )
        except Exception as e:
            elapsed_ms = round((time.time() - start_time) * 1000, 2)
            logger.error(
                "JIRA client close failed",
                extra={"error": str(e), "elapsed_ms": elapsed_ms},
            )

        # Close cache service
        if cache:
            try:
                await cache.close()
                logger.info(
                    "Cache service closed",
                    extra={"elapsed_ms": round((time.time() - start_time) * 1000, 2)},
                )
            except Exception as e:
                elapsed_ms = round((time.time() - start_time) * 1000, 2)
                logger.error(
                    "Cache service close failed",
                    extra={"error": str(e), "elapsed_ms": elapsed_ms},
                )

        logger.info(
            "Shutdown complete",
            extra={"total_ms": round((time.time() - start_time) * 1000, 2)},
        )


# Create FastMCP server
mcp = FastMCP(
    name="JIRA MCP Server",
    instructions="""
    This MCP server provides tools for interacting with Atlassian JIRA Cloud.

    Use the specific tools for common operations like creating issues, searching, etc.
    All issue keys should be in the format PROJECT-123 (e.g., PROJ-456).
    JQL queries are supported for searching issues.
    """,
    auth=auth_provider,
    lifespan=app_lifespan,
)

# Register custom field tools (if enabled)
if settings.custom_fields_enabled:
    from .tools.custom_fields import register_custom_field_tools

    custom_fields = settings.load_custom_fields()
    if custom_fields:
        register_custom_field_tools(mcp, jira, custom_fields)


# Import and register all tools
# These imports have side effects (tool registration via decorators)
from .tools import (  # noqa: E402, F401
    agile,
    attachments,
    bulk,
    comments,
    issues,
    links,
    metadata,
    projects,
    watchers,
    worklogs,
)
from .tools import cache as cache_tools  # noqa: E402, F401
