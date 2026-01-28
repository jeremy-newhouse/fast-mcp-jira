# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Using JIRA Tools

Use `/jira` to access JIRA tool documentation and workflows. The skill provides quick reference for all 47 MCP tools.

See [JIRA_USER_GUIDE.md](JIRA_USER_GUIDE.md) for comprehensive documentation.

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

- **`server.py`**: Creates the `FastMCP` instance (`mcp`) and `JiraClient` instance (`jira`). Imports tool modules for side-effect registration. Configures optional API key authentication. Initializes cache service.
- **`auth.py`**: `ApiKeyVerifier` class for MCP endpoint authentication. Enabled when `MCP_API_KEY` is set.
- **`config.py`**: `Settings` class using pydantic-settings to load from `.env`. Use `get_settings()` for cached access. Includes cache and bulk operation settings.
- **`logging_config.py`**: Structured logging with JSON format option. Use `get_logger(__name__)` for module loggers. Includes `@timed` decorator for performance logging.
- **`errors.py`**: Standardized error types (`JiraToolError`, `ValidationError`, `JiraApiError`, etc.) and `format_error_response()` helper.
- **`services/jira_client.py`**: Async HTTP client wrapping `httpx` with Basic auth and rate limiting. Methods: `get()`, `post()`, `post_raw()`, `put()`, `patch()`, `delete()`. Raises `JiraError` on failures.
- **`services/cache.py`**: SQLite-based async cache with TTL expiration. Use `CacheService.make_key()` and `cache.get()`/`cache.set()` for caching. Supports multi-JIRA-instance setups.
- **`tools/`**: Each module registers tools via `@mcp.tool(description=...)` decorator. Import pattern: `from ..server import jira, mcp`
- **`utils/validation.py`**: Input validation for issue keys, project keys, JQL, filenames, etc. All tools should validate user inputs.

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

### Caching Pattern

Tools that fetch cacheable data (metadata, projects, boards) should use the cache service:
```python
from ..server import cache, jira, mcp

@mcp.tool(description="...")
async def get_something() -> dict[str, Any]:
    cache_key = CacheService.make_key("entity_type", "identifier")

    # Check cache first
    if cache:
        cached = await cache.get(cache_key, "entity_type")
        if cached is not None:
            return {"success": True, "data": cached, "_cached": True}

    # Fetch from API
    result = await jira.get("/rest/api/3/...")

    # Store in cache
    if cache:
        await cache.set(cache_key, "entity_type", result)

    return {"success": True, "data": result, "_cached": False}
```

### JIRA API Notes

- Issue descriptions use Atlassian Document Format (ADF). Use `_build_adf_text()` helper from `tools/issues.py` to convert plain text.
- All JIRA REST API v3 endpoints start with `/rest/api/3/`
- Agile endpoints use `/rest/agile/1.0/`
