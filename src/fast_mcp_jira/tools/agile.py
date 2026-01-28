"""Agile tools for JIRA boards and sprints.

This module provides tools for managing JIRA Agile boards and sprints:
- get_boards: List all boards (Scrum/Kanban)
- get_board: Get board details
- get_sprints: List sprints for a board
- get_sprint_issues: Get issues in a sprint
- create_sprint: Create a new sprint
- update_sprint: Update sprint details
- start_sprint: Start a future sprint
- complete_sprint: Complete an active sprint
- move_issues_to_sprint: Move issues to a sprint or backlog
- delete_sprint: Delete a sprint

Security Features:
- JQL queries are validated to prevent injection attacks

Caching:
- Boards and sprints are cached for 30 minutes
"""

from typing import Annotated, Any

from pydantic import Field
from pydantic import ValidationError as PydanticValidationError

from ..server import cache, jira, mcp
from ..services.cache import CacheService
from ..services.jira_client import JiraError
from ..utils.validation import JqlInput, validate_issue_key

# Agile REST API base path
AGILE_BASE = "/rest/agile/1.0"


@mcp.tool(description="List all JIRA boards (Scrum/Kanban) with optional filtering.")
async def get_boards(
    project_key: Annotated[str | None, Field(description="Filter boards by project key")] = None,
    board_type: Annotated[
        str | None,
        Field(description="Filter by board type: 'scrum', 'kanban', or 'simple'"),
    ] = None,
    name: Annotated[str | None, Field(description="Filter boards by name (partial match)")] = None,
    max_results: Annotated[
        int, Field(description="Maximum number of boards to return", ge=1, le=100)
    ] = 50,
    start_at: Annotated[int, Field(description="Index of the first board to return", ge=0)] = 0,
) -> dict[str, Any]:
    """List all boards.

    Results are cached for 30 minutes. Use invalidate_cache to force refresh.
    """
    # Create cache key from params
    params_hash = CacheService.hash_params(
        {
            "project_key": project_key,
            "board_type": board_type,
            "name": name,
            "max_results": max_results,
            "start_at": start_at,
        }
    )
    cache_key = CacheService.make_key("boards", params_hash)

    # Try cache first
    if cache:
        cached = await cache.get(cache_key, "boards")
        if cached:
            cached["_cached"] = True
            return cached

    try:
        params: dict[str, Any] = {
            "maxResults": max_results,
            "startAt": start_at,
        }
        if project_key:
            params["projectKeyOrId"] = project_key
        if board_type:
            params["type"] = board_type
        if name:
            params["name"] = name

        result = await jira.get(f"{AGILE_BASE}/board", params=params)
        boards = []
        for b in result.get("values", []):
            boards.append(
                {
                    "id": b.get("id"),
                    "name": b.get("name"),
                    "type": b.get("type"),
                    "location": {
                        "project_key": b.get("location", {}).get("projectKey"),
                        "project_name": b.get("location", {}).get("projectName"),
                    },
                }
            )

        response = {
            "success": True,
            "total": result.get("total"),
            "is_last": result.get("isLast"),
            "boards": boards,
        }

        # Cache the response
        if cache:
            await cache.set(cache_key, "boards", response)

        return response
    except JiraError as e:
        return {"success": False, "error": str(e), "status_code": e.status_code}
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool(description="Get details of a specific JIRA board.")
async def get_board(
    board_id: Annotated[int, Field(description="Board ID")],
) -> dict[str, Any]:
    """Get board details by ID.

    Results are cached for 30 minutes. Use invalidate_cache to force refresh.
    """
    cache_key = CacheService.make_key("board", str(board_id))

    # Try cache first
    if cache:
        cached = await cache.get(cache_key, "board")
        if cached:
            cached["_cached"] = True
            return cached

    try:
        result = await jira.get(f"{AGILE_BASE}/board/{board_id}")
        response = {
            "success": True,
            "board": {
                "id": result.get("id"),
                "name": result.get("name"),
                "type": result.get("type"),
                "self": result.get("self"),
                "location": {
                    "project_id": result.get("location", {}).get("projectId"),
                    "project_key": result.get("location", {}).get("projectKey"),
                    "project_name": result.get("location", {}).get("projectName"),
                },
            },
        }

        # Cache the response
        if cache:
            await cache.set(cache_key, "board", response)

        return response
    except JiraError as e:
        return {"success": False, "error": str(e), "status_code": e.status_code}
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool(description="Get sprints for a JIRA board.")
async def get_sprints(
    board_id: Annotated[int, Field(description="Board ID")],
    state: Annotated[
        str | None,
        Field(description="Filter by sprint state: 'active', 'future', 'closed'"),
    ] = None,
    max_results: Annotated[
        int, Field(description="Maximum number of sprints to return", ge=1, le=100)
    ] = 50,
    start_at: Annotated[int, Field(description="Index of the first sprint to return", ge=0)] = 0,
) -> dict[str, Any]:
    """Get sprints for a board.

    Results are cached for 30 minutes. Use invalidate_cache to force refresh.
    """
    # Create cache key from params
    params_hash = CacheService.hash_params(
        {"state": state, "max_results": max_results, "start_at": start_at}
    )
    cache_key = CacheService.make_key("sprints", str(board_id), params_hash)

    # Try cache first
    if cache:
        cached = await cache.get(cache_key, "sprints")
        if cached:
            cached["_cached"] = True
            return cached

    try:
        params: dict[str, Any] = {
            "maxResults": max_results,
            "startAt": start_at,
        }
        if state:
            params["state"] = state

        result = await jira.get(f"{AGILE_BASE}/board/{board_id}/sprint", params=params)
        sprints = []
        for s in result.get("values", []):
            sprints.append(
                {
                    "id": s.get("id"),
                    "name": s.get("name"),
                    "state": s.get("state"),
                    "start_date": s.get("startDate"),
                    "end_date": s.get("endDate"),
                    "complete_date": s.get("completeDate"),
                    "goal": s.get("goal"),
                }
            )

        response = {
            "success": True,
            "board_id": board_id,
            "total": result.get("total"),
            "is_last": result.get("isLast"),
            "sprints": sprints,
        }

        # Cache the response
        if cache:
            await cache.set(cache_key, "sprints", response)

        return response
    except JiraError as e:
        return {"success": False, "error": str(e), "status_code": e.status_code}
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool(description="Get all issues in a sprint.")
async def get_sprint_issues(
    sprint_id: Annotated[int, Field(description="Sprint ID")],
    fields: Annotated[
        str | None,
        Field(description="Comma-separated fields to return (e.g., summary,status,assignee)"),
    ] = "summary,status,assignee,priority",
    jql: Annotated[
        str | None,
        Field(description="Additional JQL filter to apply"),
    ] = None,
    max_results: Annotated[
        int, Field(description="Maximum number of issues to return", ge=1, le=100)
    ] = 50,
    start_at: Annotated[int, Field(description="Index of the first issue to return", ge=0)] = 0,
) -> dict[str, Any]:
    """Get issues in a sprint.

    Note: Sprint issues are NOT cached as they change frequently.
    """
    try:
        params: dict[str, Any] = {
            "maxResults": max_results,
            "startAt": start_at,
        }
        if fields:
            params["fields"] = fields
        if jql:
            # Validate JQL to prevent injection attacks
            validated_jql = JqlInput(jql=jql)
            params["jql"] = validated_jql.jql

        result = await jira.get(f"{AGILE_BASE}/sprint/{sprint_id}/issue", params=params)
        return {
            "success": True,
            "sprint_id": sprint_id,
            "total": result.get("total"),
            "issues": result.get("issues", []),
        }
    except PydanticValidationError as e:
        return {"success": False, "error": str(e.errors()[0]["msg"]), "field": "jql"}
    except JiraError as e:
        return {"success": False, "error": str(e), "status_code": e.status_code}
    except Exception as e:
        return {"success": False, "error": str(e)}


# =============================================================================
# Sprint Management Tools
# =============================================================================


@mcp.tool(description="Create a new sprint on a Scrum board.")
async def create_sprint(
    board_id: Annotated[int, Field(description="Board ID (must be a Scrum board)")],
    name: Annotated[str, Field(description="Sprint name")],
    start_date: Annotated[
        str | None,
        Field(description="Sprint start date in ISO 8601 format (e.g., 2024-01-15T09:00:00.000Z)"),
    ] = None,
    end_date: Annotated[
        str | None,
        Field(description="Sprint end date in ISO 8601 format (e.g., 2024-01-29T17:00:00.000Z)"),
    ] = None,
    goal: Annotated[
        str | None,
        Field(description="Sprint goal description"),
    ] = None,
) -> dict[str, Any]:
    """Create a new sprint on a Scrum board.

    The sprint is created in 'future' state. Use start_sprint to activate it.
    """
    try:
        body: dict[str, Any] = {
            "name": name,
            "originBoardId": board_id,
        }
        if start_date:
            body["startDate"] = start_date
        if end_date:
            body["endDate"] = end_date
        if goal:
            body["goal"] = goal

        result = await jira.post(f"{AGILE_BASE}/sprint", body=body)

        # Invalidate sprints cache for this board
        if cache:
            await cache.invalidate(prefix=f"sprints:{board_id}")

        return {
            "success": True,
            "sprint": {
                "id": result.get("id"),
                "name": result.get("name"),
                "state": result.get("state"),
                "start_date": result.get("startDate"),
                "end_date": result.get("endDate"),
                "goal": result.get("goal"),
            },
        }
    except JiraError as e:
        return {"success": False, "error": str(e), "status_code": e.status_code}
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool(description="Update sprint details (name, dates, goal, or state).")
async def update_sprint(
    sprint_id: Annotated[int, Field(description="Sprint ID to update")],
    name: Annotated[str | None, Field(description="New sprint name")] = None,
    start_date: Annotated[
        str | None,
        Field(description="New start date in ISO 8601 format"),
    ] = None,
    end_date: Annotated[
        str | None,
        Field(description="New end date in ISO 8601 format"),
    ] = None,
    goal: Annotated[str | None, Field(description="New sprint goal")] = None,
    state: Annotated[
        str | None,
        Field(description="New state: 'active' to start, 'closed' to complete"),
    ] = None,
) -> dict[str, Any]:
    """Update sprint details.

    Use state='active' to start a future sprint, state='closed' to complete it.
    """
    try:
        # JIRA API requires state in the request body - fetch current if not provided
        if state is None:
            current_sprint = await jira.get(f"{AGILE_BASE}/sprint/{sprint_id}")
            state = current_sprint.get("state")

        body: dict[str, Any] = {"state": state}
        if name is not None:
            body["name"] = name
        if start_date is not None:
            body["startDate"] = start_date
        if end_date is not None:
            body["endDate"] = end_date
        if goal is not None:
            body["goal"] = goal

        # Check if only state is set (no actual updates requested)
        if len(body) == 1 and "state" in body:
            return {"success": False, "error": "No fields to update", "code": "VALIDATION_ERROR"}

        result = await jira.put(f"{AGILE_BASE}/sprint/{sprint_id}", body=body)

        # Invalidate sprints cache
        if cache:
            await cache.invalidate(entity_type="sprints")

        return {
            "success": True,
            "sprint": {
                "id": result.get("id"),
                "name": result.get("name"),
                "state": result.get("state"),
                "start_date": result.get("startDate"),
                "end_date": result.get("endDate"),
                "goal": result.get("goal"),
            },
        }
    except JiraError as e:
        return {"success": False, "error": str(e), "status_code": e.status_code}
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool(description="Start a future sprint (sets state to active).")
async def start_sprint(
    sprint_id: Annotated[int, Field(description="Sprint ID to start")],
    start_date: Annotated[
        str | None,
        Field(description="Start date in ISO 8601 format (defaults to now)"),
    ] = None,
    end_date: Annotated[
        str | None,
        Field(description="End date in ISO 8601 format (required if not set on sprint)"),
    ] = None,
) -> dict[str, Any]:
    """Start a future sprint.

    The sprint must be in 'future' state. An end date is required either
    on the sprint already or provided here.
    """
    try:
        body: dict[str, Any] = {"state": "active"}
        if start_date:
            body["startDate"] = start_date
        if end_date:
            body["endDate"] = end_date

        result = await jira.put(f"{AGILE_BASE}/sprint/{sprint_id}", body=body)

        # Invalidate sprints cache
        if cache:
            await cache.invalidate(entity_type="sprints")

        return {
            "success": True,
            "message": f"Sprint {sprint_id} started",
            "sprint": {
                "id": result.get("id"),
                "name": result.get("name"),
                "state": result.get("state"),
                "start_date": result.get("startDate"),
                "end_date": result.get("endDate"),
            },
        }
    except JiraError as e:
        return {"success": False, "error": str(e), "status_code": e.status_code}
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool(description="Complete an active sprint.")
async def complete_sprint(
    sprint_id: Annotated[int, Field(description="Sprint ID to complete")],
) -> dict[str, Any]:
    """Complete an active sprint.

    Incomplete issues will remain in the sprint but can be moved to another
    sprint or backlog using move_issues_to_sprint.
    """
    try:
        body: dict[str, Any] = {"state": "closed"}
        result = await jira.put(f"{AGILE_BASE}/sprint/{sprint_id}", body=body)

        # Invalidate sprints cache
        if cache:
            await cache.invalidate(entity_type="sprints")

        return {
            "success": True,
            "message": f"Sprint {sprint_id} completed",
            "sprint": {
                "id": result.get("id"),
                "name": result.get("name"),
                "state": result.get("state"),
                "complete_date": result.get("completeDate"),
            },
        }
    except JiraError as e:
        return {"success": False, "error": str(e), "status_code": e.status_code}
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool(description="Move issues to a sprint or backlog.")
async def move_issues_to_sprint(
    sprint_id: Annotated[
        int,
        Field(description="Target sprint ID (use 0 or omit for backlog)"),
    ],
    issue_keys: Annotated[
        list[str],
        Field(description="List of issue keys to move (e.g., ['PROJ-1', 'PROJ-2'])"),
    ],
) -> dict[str, Any]:
    """Move issues to a sprint or backlog.

    Use sprint_id=0 to move issues to the backlog.
    """
    try:
        # Validate issue keys
        validated_keys = [validate_issue_key(key) for key in issue_keys]

        if sprint_id == 0:
            # Move to backlog
            body = {"issues": validated_keys}
            await jira.post(f"{AGILE_BASE}/backlog/issue", body=body)
            return {
                "success": True,
                "message": f"Moved {len(validated_keys)} issues to backlog",
                "issue_keys": validated_keys,
            }
        else:
            # Move to sprint
            body = {"issues": validated_keys}
            await jira.post(f"{AGILE_BASE}/sprint/{sprint_id}/issue", body=body)
            return {
                "success": True,
                "message": f"Moved {len(validated_keys)} issues to sprint {sprint_id}",
                "sprint_id": sprint_id,
                "issue_keys": validated_keys,
            }
    except JiraError as e:
        return {"success": False, "error": str(e), "status_code": e.status_code}
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool(description="Delete a sprint (issues return to backlog).")
async def delete_sprint(
    sprint_id: Annotated[int, Field(description="Sprint ID to delete")],
) -> dict[str, Any]:
    """Delete a sprint.

    Issues in the deleted sprint will be moved to the backlog.
    """
    try:
        await jira.delete(f"{AGILE_BASE}/sprint/{sprint_id}")

        # Invalidate sprints cache
        if cache:
            await cache.invalidate(entity_type="sprints")

        return {
            "success": True,
            "message": f"Sprint {sprint_id} deleted",
            "deleted_sprint_id": sprint_id,
        }
    except JiraError as e:
        return {"success": False, "error": str(e), "status_code": e.status_code}
    except Exception as e:
        return {"success": False, "error": str(e)}
