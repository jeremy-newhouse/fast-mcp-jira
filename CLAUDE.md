# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies
uv sync

# Run the server
uv run python -m fast_mcp_jira

# Lint
uv run ruff check src/
uv run ruff format --check src/

# Format code
uv run ruff format src/

# Run tests (requires tests directory)
uv run pytest
uv run pytest tests/test_file.py::test_name -v  # single test
```

## Architecture

This is a FastMCP server that exposes JIRA Cloud operations as MCP tools over Streamable HTTP transport.

### Key Components

- **`server.py`**: Creates the `FastMCP` instance (`mcp`) and `JiraClient` instance (`jira`). Imports tool modules for side-effect registration.
- **`config.py`**: `Settings` class using pydantic-settings to load from `.env`. Use `get_settings()` for cached access.
- **`services/jira_client.py`**: Async HTTP client wrapping `httpx` with Basic auth. Methods: `get()`, `post()`, `put()`, `patch()`, `delete()`. Raises `JiraError` on failures.
- **`tools/`**: Each module registers tools via `@mcp.tool(description=...)` decorator. Import pattern: `from ..server import jira, mcp`

### Tool Module Pattern

Tools follow this structure:
```python
from ..server import jira, mcp
from ..services.jira_client import JiraError

@mcp.tool(description="...")
async def tool_name(param: Annotated[str, Field(description="...")]) -> dict[str, Any]:
    try:
        result = await jira.get("/rest/api/3/...")
        return {"success": True, "data": result}
    except JiraError as e:
        return {"success": False, "error": str(e), "status_code": e.status_code}
```

### JIRA API Notes

- Issue descriptions use Atlassian Document Format (ADF). Use `_build_adf_text()` helper from `tools/issues.py` to convert plain text.
- All JIRA REST API v3 endpoints start with `/rest/api/3/`
- Agile endpoints use `/rest/agile/1.0/`
