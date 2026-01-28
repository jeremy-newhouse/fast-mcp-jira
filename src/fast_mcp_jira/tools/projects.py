"""Project tools for JIRA.

This module provides tools for managing JIRA projects:
- get_projects: List all projects
- get_project: Get project details
- get_components: Get project components
- get_versions: Get project versions/releases

Security Features:
- Project keys are validated against JIRA format
- Expand parameters are validated

Caching:
- Projects, components, and versions are cached for 6 hours
"""

from typing import Annotated, Any

from pydantic import Field

from ..logging_config import get_logger
from ..server import cache, jira, mcp
from ..services.cache import CacheService
from ..services.jira_client import JiraError
from ..utils.validation import (
    ValidationError,
    build_response,
    validate_expand,
    validate_order_by,
    validate_project_key,
)

logger = get_logger(__name__)


@mcp.tool(description="List all JIRA projects.")
async def get_projects(
    max_results: Annotated[
        int, Field(description="Maximum number of projects to return", ge=1, le=100)
    ] = 50,
    start_at: Annotated[int, Field(description="Index of the first project to return", ge=0)] = 0,
    expand: Annotated[
        str | None,
        Field(description="Comma-separated list of expansions (e.g., description,lead,issueTypes)"),
    ] = None,
) -> dict[str, Any]:
    """Get list of all projects.

    Results are cached for 6 hours. Use invalidate_cache to force refresh.
    """
    # Create cache key from params
    params_hash = CacheService.hash_params(
        {"max_results": max_results, "start_at": start_at, "expand": expand}
    )
    cache_key = CacheService.make_key("projects", params_hash)

    # Try cache first
    if cache:
        cached = await cache.get(cache_key, "projects")
        if cached:
            cached["_cached"] = True
            return cached

    try:
        params: dict[str, Any] = {
            "maxResults": max_results,
            "startAt": start_at,
        }
        if expand:
            expand = validate_expand(expand)
            params["expand"] = expand

        result = await jira.get("/rest/api/3/project/search", params=params)
        projects = []
        for p in result.get("values", []):
            projects.append(
                {
                    "id": p.get("id"),
                    "key": p.get("key"),
                    "name": p.get("name"),
                    "project_type": p.get("projectTypeKey"),
                    "style": p.get("style"),
                    "is_private": p.get("isPrivate"),
                }
            )

        response = build_response(
            True,
            total=result.get("total"),
            start_at=result.get("startAt"),
            max_results=result.get("maxResults"),
            is_last=result.get("isLast", True),
            projects=projects,
        )

        # Cache the response
        if cache:
            await cache.set(cache_key, "projects", response)

        return response
    except ValidationError as e:
        return build_response(False, error=str(e), field=e.field)
    except JiraError as e:
        return build_response(False, error=str(e), status_code=e.status_code)
    except Exception:
        logger.exception("Unexpected error getting projects")
        return build_response(False, error="Internal error occurred")


@mcp.tool(description="Get details of a specific JIRA project.")
async def get_project(
    project_key: Annotated[str, Field(description="Project key (e.g., PROJ)")],
    expand: Annotated[
        str | None,
        Field(description="Comma-separated list of expansions (e.g., description,lead,issueTypes)"),
    ] = None,
) -> dict[str, Any]:
    """Get project details by key.

    Results are cached for 6 hours. Use invalidate_cache to force refresh.
    """
    try:
        project_key = validate_project_key(project_key)

        # Create cache key
        params_hash = CacheService.hash_params({"expand": expand}) if expand else "default"
        cache_key = CacheService.make_key("project", project_key, params_hash)

        # Try cache first
        if cache:
            cached = await cache.get(cache_key, "project")
            if cached:
                cached["_cached"] = True
                return cached

        params = None
        if expand:
            expand = validate_expand(expand)
            params = {"expand": expand}
        result = await jira.get(f"/rest/api/3/project/{project_key}", params=params)
        response = build_response(
            True,
            project={
                "id": result.get("id"),
                "key": result.get("key"),
                "name": result.get("name"),
                "description": result.get("description"),
                "lead": result.get("lead", {}).get("displayName"),
                "project_type": result.get("projectTypeKey"),
                "url": result.get("url"),
                "issue_types": [
                    {"id": it.get("id"), "name": it.get("name")}
                    for it in result.get("issueTypes", [])
                ],
            },
        )

        # Cache the response
        if cache:
            await cache.set(cache_key, "project", response)

        return response
    except ValidationError as e:
        return build_response(False, error=str(e), field=e.field)
    except JiraError as e:
        return build_response(False, error=str(e), status_code=e.status_code)
    except Exception:
        logger.exception("Unexpected error getting project %s", project_key)
        return build_response(False, error="Internal error occurred")


@mcp.tool(description="Get components for a JIRA project.")
async def get_components(
    project_key: Annotated[str, Field(description="Project key (e.g., PROJ)")],
) -> dict[str, Any]:
    """Get list of components for a project.

    Results are cached for 6 hours. Use invalidate_cache to force refresh.
    """
    try:
        project_key = validate_project_key(project_key)

        # Create cache key
        cache_key = CacheService.make_key("components", project_key)

        # Try cache first
        if cache:
            cached = await cache.get(cache_key, "components")
            if cached:
                cached["_cached"] = True
                return cached

        result = await jira.get(f"/rest/api/3/project/{project_key}/components")
        components = []
        for c in result if isinstance(result, list) else []:
            components.append(
                {
                    "id": c.get("id"),
                    "name": c.get("name"),
                    "description": c.get("description"),
                    "lead": c.get("lead", {}).get("displayName") if c.get("lead") else None,
                    "assignee_type": c.get("assigneeType"),
                }
            )

        response = build_response(
            True,
            project_key=project_key,
            total=len(components),
            components=components,
        )

        # Cache the response
        if cache:
            await cache.set(cache_key, "components", response)

        return response
    except ValidationError as e:
        return build_response(False, error=str(e), field=e.field)
    except JiraError as e:
        return build_response(False, error=str(e), status_code=e.status_code)
    except Exception:
        logger.exception("Unexpected error getting components for %s", project_key)
        return build_response(False, error="Internal error occurred")


@mcp.tool(description="Get versions/releases for a JIRA project.")
async def get_versions(
    project_key: Annotated[str, Field(description="Project key (e.g., PROJ)")],
    max_results: Annotated[
        int, Field(description="Maximum number of versions to return", ge=1, le=100)
    ] = 50,
    start_at: Annotated[int, Field(description="Index of the first version to return", ge=0)] = 0,
    order_by: Annotated[
        str | None,
        Field(description="Order by field (e.g., 'name', '-releaseDate' for descending)"),
    ] = None,
) -> dict[str, Any]:
    """Get list of versions/releases for a project.

    Results are cached for 6 hours. Use invalidate_cache to force refresh.
    """
    try:
        project_key = validate_project_key(project_key)

        # Validate order_by if provided
        if order_by:
            order_by = validate_order_by(order_by)

        # Create cache key
        params_hash = CacheService.hash_params(
            {"max_results": max_results, "start_at": start_at, "order_by": order_by}
        )
        cache_key = CacheService.make_key("versions", project_key, params_hash)

        # Try cache first
        if cache:
            cached = await cache.get(cache_key, "versions")
            if cached:
                cached["_cached"] = True
                return cached

        params: dict[str, Any] = {
            "maxResults": max_results,
            "startAt": start_at,
        }
        if order_by:
            params["orderBy"] = order_by

        result = await jira.get(f"/rest/api/3/project/{project_key}/version", params=params)
        versions = []
        for v in result.get("values", []):
            versions.append(
                {
                    "id": v.get("id"),
                    "name": v.get("name"),
                    "description": v.get("description"),
                    "archived": v.get("archived"),
                    "released": v.get("released"),
                    "release_date": v.get("releaseDate"),
                    "start_date": v.get("startDate"),
                }
            )

        response = build_response(
            True,
            project_key=project_key,
            total=result.get("total"),
            start_at=result.get("startAt"),
            max_results=result.get("maxResults"),
            is_last=result.get("isLast", True),
            versions=versions,
        )

        # Cache the response
        if cache:
            await cache.set(cache_key, "versions", response)

        return response
    except ValidationError as e:
        return build_response(False, error=str(e), field=e.field)
    except JiraError as e:
        return build_response(False, error=str(e), status_code=e.status_code)
    except Exception:
        logger.exception("Unexpected error getting versions for %s", project_key)
        return build_response(False, error="Internal error occurred")
