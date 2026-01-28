"""Metadata tools for JIRA (issue types, priorities, statuses, users, fields).

These tools retrieve JIRA system metadata. Results are cached for performance
since metadata rarely changes.

Cached entities and TTLs:
- issue_types: 24 hours
- priorities: 24 hours
- statuses: 24 hours
- fields: 24 hours
- users: 1 hour (search results)
"""

from typing import Annotated, Any

from pydantic import Field

from ..logging_config import get_logger
from ..server import cache, jira, mcp
from ..services.cache import CacheService
from ..services.jira_client import JiraError

logger = get_logger(__name__)


@mcp.tool(description="Get all issue types available in JIRA.")
async def get_issue_types() -> dict[str, Any]:
    """Get list of all issue types.

    Results are cached for 24 hours. Use invalidate_cache to force refresh.
    """
    cache_key = CacheService.make_key("issue_types")

    # Try cache first
    if cache:
        cached = await cache.get(cache_key, "issue_types")
        if cached:
            cached["_cached"] = True
            return cached

    try:
        result = await jira.get("/rest/api/3/issuetype")
        issue_types = []
        for it in result if isinstance(result, list) else []:
            issue_types.append(
                {
                    "id": it.get("id"),
                    "name": it.get("name"),
                    "description": it.get("description"),
                    "subtask": it.get("subtask"),
                    "hierarchy_level": it.get("hierarchyLevel"),
                }
            )

        response = {
            "success": True,
            "total": len(issue_types),
            "issue_types": issue_types,
        }

        # Cache the response
        if cache:
            await cache.set(cache_key, "issue_types", response)

        return response
    except JiraError as e:
        return {"success": False, "error": str(e), "status_code": e.status_code}
    except Exception:
        logger.exception("Unexpected error getting issue types")
        return {"success": False, "error": "Internal error occurred"}


@mcp.tool(description="Get all priority levels available in JIRA.")
async def get_priorities() -> dict[str, Any]:
    """Get list of all priority levels.

    Results are cached for 24 hours. Use invalidate_cache to force refresh.
    """
    cache_key = CacheService.make_key("priorities")

    # Try cache first
    if cache:
        cached = await cache.get(cache_key, "priorities")
        if cached:
            cached["_cached"] = True
            return cached

    try:
        result = await jira.get("/rest/api/3/priority")
        priorities = []
        for p in result if isinstance(result, list) else []:
            priorities.append(
                {
                    "id": p.get("id"),
                    "name": p.get("name"),
                    "description": p.get("description"),
                    "icon_url": p.get("iconUrl"),
                }
            )

        response = {
            "success": True,
            "total": len(priorities),
            "priorities": priorities,
        }

        # Cache the response
        if cache:
            await cache.set(cache_key, "priorities", response)

        return response
    except JiraError as e:
        return {"success": False, "error": str(e), "status_code": e.status_code}
    except Exception:
        logger.exception("Unexpected error getting priorities")
        return {"success": False, "error": "Internal error occurred"}


@mcp.tool(description="Get all workflow statuses available in JIRA.")
async def get_statuses() -> dict[str, Any]:
    """Get list of all workflow statuses.

    Results are cached for 24 hours. Use invalidate_cache to force refresh.
    """
    cache_key = CacheService.make_key("statuses")

    # Try cache first
    if cache:
        cached = await cache.get(cache_key, "statuses")
        if cached:
            cached["_cached"] = True
            return cached

    try:
        result = await jira.get("/rest/api/3/status")
        statuses = []
        for s in result if isinstance(result, list) else []:
            statuses.append(
                {
                    "id": s.get("id"),
                    "name": s.get("name"),
                    "description": s.get("description"),
                    "category": s.get("statusCategory", {}).get("name"),
                    "category_key": s.get("statusCategory", {}).get("key"),
                }
            )

        response = {
            "success": True,
            "total": len(statuses),
            "statuses": statuses,
        }

        # Cache the response
        if cache:
            await cache.set(cache_key, "statuses", response)

        return response
    except JiraError as e:
        return {"success": False, "error": str(e), "status_code": e.status_code}
    except Exception:
        logger.exception("Unexpected error getting statuses")
        return {"success": False, "error": "Internal error occurred"}


@mcp.tool(description="Search for JIRA users by query string.")
async def search_users(
    query: Annotated[str, Field(description="Search query (name, email, or username)")],
    max_results: Annotated[
        int, Field(description="Maximum number of users to return", ge=1, le=100)
    ] = 50,
    start_at: Annotated[int, Field(description="Index of the first user to return", ge=0)] = 0,
) -> dict[str, Any]:
    """Search for users by name, email, or username.

    Results are cached for 1 hour per unique query. Use invalidate_cache to force refresh.
    """
    # Create cache key from query params
    params_hash = CacheService.hash_params(
        {"query": query, "max_results": max_results, "start_at": start_at}
    )
    cache_key = CacheService.make_key("users", params_hash)

    # Try cache first
    if cache:
        cached = await cache.get(cache_key, "users")
        if cached:
            cached["_cached"] = True
            return cached

    try:
        params = {
            "query": query,
            "maxResults": max_results,
            "startAt": start_at,
        }
        result = await jira.get("/rest/api/3/user/search", params=params)
        users = []
        for u in result if isinstance(result, list) else []:
            users.append(
                {
                    "account_id": u.get("accountId"),
                    "display_name": u.get("displayName"),
                    "email": u.get("emailAddress"),
                    "active": u.get("active"),
                    "account_type": u.get("accountType"),
                }
            )

        response = {
            "success": True,
            "total": len(users),
            "users": users,
        }

        # Cache the response
        if cache:
            await cache.set(cache_key, "users", response)

        return response
    except JiraError as e:
        return {"success": False, "error": str(e), "status_code": e.status_code}
    except Exception:
        logger.exception("Unexpected error searching users")
        return {"success": False, "error": "Internal error occurred"}


@mcp.tool(description="Get all available fields in JIRA.")
async def get_fields() -> dict[str, Any]:
    """Get list of all fields (system and custom).

    Results are cached for 24 hours. Use invalidate_cache to force refresh.
    """
    cache_key = CacheService.make_key("fields")

    # Try cache first
    if cache:
        cached = await cache.get(cache_key, "fields")
        if cached:
            cached["_cached"] = True
            return cached

    try:
        result = await jira.get("/rest/api/3/field")
        fields = []
        for f in result if isinstance(result, list) else []:
            fields.append(
                {
                    "id": f.get("id"),
                    "name": f.get("name"),
                    "custom": f.get("custom"),
                    "orderable": f.get("orderable"),
                    "navigable": f.get("navigable"),
                    "searchable": f.get("searchable"),
                    "schema_type": f.get("schema", {}).get("type") if f.get("schema") else None,
                }
            )

        response = {
            "success": True,
            "total": len(fields),
            "fields": fields,
        }

        # Cache the response
        if cache:
            await cache.set(cache_key, "fields", response)

        return response
    except JiraError as e:
        return {"success": False, "error": str(e), "status_code": e.status_code}
    except Exception:
        logger.exception("Unexpected error getting fields")
        return {"success": False, "error": "Internal error occurred"}
