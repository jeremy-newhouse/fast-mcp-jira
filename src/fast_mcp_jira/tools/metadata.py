"""Metadata tools for JIRA (issue types, priorities, statuses, users, fields)."""

from typing import Annotated, Any

from pydantic import Field

from ..server import jira, mcp
from ..services.jira_client import JiraError


@mcp.tool(description="Get all issue types available in JIRA.")
async def get_issue_types() -> dict[str, Any]:
    """Get list of all issue types."""
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

        return {
            "success": True,
            "total": len(issue_types),
            "issue_types": issue_types,
        }
    except JiraError as e:
        return {"success": False, "error": str(e), "status_code": e.status_code}
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool(description="Get all priority levels available in JIRA.")
async def get_priorities() -> dict[str, Any]:
    """Get list of all priority levels."""
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

        return {
            "success": True,
            "total": len(priorities),
            "priorities": priorities,
        }
    except JiraError as e:
        return {"success": False, "error": str(e), "status_code": e.status_code}
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool(description="Get all workflow statuses available in JIRA.")
async def get_statuses() -> dict[str, Any]:
    """Get list of all workflow statuses."""
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

        return {
            "success": True,
            "total": len(statuses),
            "statuses": statuses,
        }
    except JiraError as e:
        return {"success": False, "error": str(e), "status_code": e.status_code}
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool(description="Search for JIRA users by query string.")
async def search_users(
    query: Annotated[str, Field(description="Search query (name, email, or username)")],
    max_results: Annotated[
        int, Field(description="Maximum number of users to return", ge=1, le=100)
    ] = 50,
    start_at: Annotated[int, Field(description="Index of the first user to return", ge=0)] = 0,
) -> dict[str, Any]:
    """Search for users by name, email, or username."""
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

        return {
            "success": True,
            "total": len(users),
            "users": users,
        }
    except JiraError as e:
        return {"success": False, "error": str(e), "status_code": e.status_code}
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool(description="Get all available fields in JIRA.")
async def get_fields() -> dict[str, Any]:
    """Get list of all fields (system and custom)."""
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

        return {
            "success": True,
            "total": len(fields),
            "fields": fields,
        }
    except JiraError as e:
        return {"success": False, "error": str(e), "status_code": e.status_code}
    except Exception as e:
        return {"success": False, "error": str(e)}
