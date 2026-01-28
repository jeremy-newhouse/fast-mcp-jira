"""Agile tools for JIRA boards and sprints."""

from typing import Annotated, Any

from pydantic import Field

from ..server import jira, mcp
from ..services.jira_client import JiraError

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
    """List all boards."""
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

        return {
            "success": True,
            "total": result.get("total"),
            "is_last": result.get("isLast"),
            "boards": boards,
        }
    except JiraError as e:
        return {"success": False, "error": str(e), "status_code": e.status_code}
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool(description="Get details of a specific JIRA board.")
async def get_board(
    board_id: Annotated[int, Field(description="Board ID")],
) -> dict[str, Any]:
    """Get board details by ID."""
    try:
        result = await jira.get(f"{AGILE_BASE}/board/{board_id}")
        return {
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
    """Get sprints for a board."""
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

        return {
            "success": True,
            "board_id": board_id,
            "total": result.get("total"),
            "is_last": result.get("isLast"),
            "sprints": sprints,
        }
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
    """Get issues in a sprint."""
    try:
        params: dict[str, Any] = {
            "maxResults": max_results,
            "startAt": start_at,
        }
        if fields:
            params["fields"] = fields
        if jql:
            params["jql"] = jql

        result = await jira.get(f"{AGILE_BASE}/sprint/{sprint_id}/issue", params=params)
        return {
            "success": True,
            "sprint_id": sprint_id,
            "total": result.get("total"),
            "issues": result.get("issues", []),
        }
    except JiraError as e:
        return {"success": False, "error": str(e), "status_code": e.status_code}
    except Exception as e:
        return {"success": False, "error": str(e)}
