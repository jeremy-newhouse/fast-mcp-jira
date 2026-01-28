"""FastMCP server instance and tool registration."""

from fastmcp import FastMCP

from .config import get_settings
from .services.jira_client import JiraClient

# Initialize settings and JIRA client
settings = get_settings()
jira = JiraClient(settings)

# Create FastMCP server
mcp = FastMCP(
    name="JIRA MCP Server",
    instructions="""
    This MCP server provides tools for interacting with Atlassian JIRA Cloud.

    Use the specific tools for common operations like creating issues, searching, etc.
    All issue keys should be in the format PROJECT-123 (e.g., PROJ-456).
    JQL queries are supported for searching issues.
    """,
)

# Import and register all tools
# These imports have side effects (tool registration via decorators)
from .tools import (  # noqa: E402, F401
    agile,
    attachments,
    comments,
    issues,
    links,
    metadata,
    projects,
    watchers,
    worklogs,
)
