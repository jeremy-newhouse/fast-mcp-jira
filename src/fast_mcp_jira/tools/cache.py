"""Cache management tools for JIRA MCP server.

These tools allow inspection and management of the SQLite cache
that stores JIRA API responses for improved performance.

Tools:
    get_cache_stats: View cache statistics including hit rates
    invalidate_cache: Clear cache entries by type or entirely
"""

from typing import Annotated, Any

from pydantic import Field

from ..server import cache, mcp


@mcp.tool(description="Get cache statistics and health information.")
async def get_cache_stats() -> dict[str, Any]:
    """Get cache statistics including hit rates and entry counts.

    Returns cache health metrics including:
    - Total entries and valid/expired counts
    - Overall hit rate percentage
    - Hit/miss statistics per entity type
    - Cache database location

    Returns:
        Cache statistics dictionary with success status.
    """
    if cache is None:
        return {
            "success": False,
            "error": {"message": "Cache is disabled", "code": "CACHE_DISABLED"},
        }

    stats = await cache.get_stats()
    return {"success": True, **stats}


@mcp.tool(description="Invalidate (clear) cache entries.")
async def invalidate_cache(
    entity_type: Annotated[
        str | None,
        Field(
            default=None,
            description=(
                "Entity type to invalidate. Options: issue_types, priorities, "
                "statuses, fields, link_types, projects, project, components, "
                "versions, boards, board, sprints, users. Leave empty with "
                "invalidate_all=true to clear everything."
            ),
        ),
    ] = None,
    cache_key: Annotated[
        str | None,
        Field(
            default=None,
            description="Specific cache key to invalidate (e.g., 'project:MYPROJ')",
        ),
    ] = None,
    invalidate_all: Annotated[
        bool,
        Field(
            default=False,
            description="Set to true to invalidate all cache entries for this JIRA instance",
        ),
    ] = False,
) -> dict[str, Any]:
    """Invalidate (clear) cache entries.

    Use this to force fresh data retrieval from JIRA. Useful when:
    - You know data has changed in JIRA
    - Troubleshooting stale data issues
    - After configuration changes in JIRA

    Args:
        entity_type: Clear all entries of this type (e.g., 'issue_types', 'projects').
        cache_key: Clear a specific cache entry by key.
        invalidate_all: Set true to clear the entire cache.

    Returns:
        Number of entries invalidated.
    """
    if cache is None:
        return {
            "success": False,
            "error": {"message": "Cache is disabled", "code": "CACHE_DISABLED"},
        }

    if not any([entity_type, cache_key, invalidate_all]):
        return {
            "success": False,
            "error": {
                "message": "Must specify entity_type, cache_key, or invalidate_all=true",
                "code": "VALIDATION_ERROR",
            },
        }

    if invalidate_all:
        count = await cache.invalidate()
    elif entity_type:
        count = await cache.invalidate(entity_type=entity_type)
    else:
        count = await cache.invalidate(cache_key=cache_key)

    return {
        "success": True,
        "invalidated_count": count,
        "entity_type": entity_type,
        "cache_key": cache_key,
        "invalidate_all": invalidate_all,
    }
