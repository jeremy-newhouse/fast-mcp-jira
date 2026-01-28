"""Worklog tools for JIRA time tracking.

This module provides tools for managing time tracking on JIRA issues:
- add_worklog: Log time spent on an issue
- get_worklogs: Get all worklogs for an issue
- delete_worklog: Delete a worklog entry

Security Features:
- Issue keys are validated against JIRA format
- Worklog IDs are validated as numeric
"""

from typing import Annotated, Any

from pydantic import Field
from pydantic import ValidationError as PydanticValidationError

from ..server import jira, mcp
from ..services.jira_client import JiraError
from ..utils.adf import extract_text_from_adf, markdown_to_adf
from ..utils.validation import NumericIdInput, ValidationError, validate_issue_key


@mcp.tool(description="Log time spent on a JIRA issue.")
async def add_worklog(
    issue_key: Annotated[str, Field(description="Issue key (e.g., PROJ-123)")],
    time_spent: Annotated[
        str,
        Field(description="Time spent in JIRA format (e.g., '2h 30m', '1d', '3h')"),
    ],
    comment: Annotated[
        str | None,
        Field(description="Optional comment describing the work. Supports markdown."),
    ] = None,
    started: Annotated[
        str | None,
        Field(description="When work started (ISO 8601, e.g., 2024-01-15T09:00:00.000+0000)"),
    ] = None,
) -> dict[str, Any]:
    """Add a worklog entry to an issue."""
    try:
        issue_key = validate_issue_key(issue_key)

        body: dict[str, Any] = {"timeSpent": time_spent}

        if comment:
            body["comment"] = markdown_to_adf(comment)

        if started:
            body["started"] = started

        result = await jira.post(
            f"/rest/api/3/issue/{issue_key}/worklog",
            body=body,
        )
        return {
            "success": True,
            "worklog_id": result.get("id"),
            "issue_key": issue_key,
            "time_spent": result.get("timeSpent"),
            "time_spent_seconds": result.get("timeSpentSeconds"),
            "author": result.get("author", {}).get("displayName"),
            "started": result.get("started"),
        }
    except ValidationError as e:
        return {"success": False, "error": str(e), "field": e.field}
    except JiraError as e:
        return {"success": False, "error": str(e), "status_code": e.status_code}
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool(description="Get all worklogs for a JIRA issue.")
async def get_worklogs(
    issue_key: Annotated[str, Field(description="Issue key (e.g., PROJ-123)")],
    max_results: Annotated[
        int, Field(description="Maximum number of worklogs to return", ge=1, le=100)
    ] = 50,
    start_at: Annotated[int, Field(description="Index of the first worklog to return", ge=0)] = 0,
) -> dict[str, Any]:
    """Get worklogs for an issue."""
    try:
        issue_key = validate_issue_key(issue_key)

        params = {
            "maxResults": max_results,
            "startAt": start_at,
        }
        result = await jira.get(
            f"/rest/api/3/issue/{issue_key}/worklog",
            params=params,
        )
        worklogs = []
        for w in result.get("worklogs", []):
            # Extract plain text from ADF comment
            comment = w.get("comment", {})
            comment_text = extract_text_from_adf(comment) if isinstance(comment, dict) else None

            worklogs.append(
                {
                    "id": w.get("id"),
                    "time_spent": w.get("timeSpent"),
                    "time_spent_seconds": w.get("timeSpentSeconds"),
                    "comment": comment_text or None,
                    "author": w.get("author", {}).get("displayName"),
                    "started": w.get("started"),
                    "created": w.get("created"),
                    "updated": w.get("updated"),
                }
            )

        return {
            "success": True,
            "issue_key": issue_key,
            "total": result.get("total"),
            "worklogs": worklogs,
        }
    except ValidationError as e:
        return {"success": False, "error": str(e), "field": e.field}
    except JiraError as e:
        return {"success": False, "error": str(e), "status_code": e.status_code}
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool(description="Delete a worklog entry from a JIRA issue.")
async def delete_worklog(
    issue_key: Annotated[str, Field(description="Issue key (e.g., PROJ-123)")],
    worklog_id: Annotated[str, Field(description="Worklog ID to delete")],
) -> dict[str, Any]:
    """Delete a worklog entry from an issue."""
    try:
        issue_key = validate_issue_key(issue_key)
        validated_id = NumericIdInput(id=worklog_id)

        await jira.delete(f"/rest/api/3/issue/{issue_key}/worklog/{validated_id.id}")
        return {
            "success": True,
            "deleted_worklog_id": validated_id.id,
            "issue_key": issue_key,
        }
    except ValidationError as e:
        return {"success": False, "error": str(e), "field": e.field}
    except PydanticValidationError as e:
        return {"success": False, "error": str(e.errors()[0]["msg"]), "field": "worklog_id"}
    except JiraError as e:
        return {"success": False, "error": str(e), "status_code": e.status_code}
    except Exception as e:
        return {"success": False, "error": str(e)}
