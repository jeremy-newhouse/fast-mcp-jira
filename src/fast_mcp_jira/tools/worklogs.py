"""Worklog tools for JIRA time tracking."""

from typing import Annotated, Any

from pydantic import Field

from ..server import jira, mcp
from ..services.jira_client import JiraError


def _build_adf_text(text: str) -> dict[str, Any]:
    """Build Atlassian Document Format (ADF) structure for text content."""
    return {
        "type": "doc",
        "version": 1,
        "content": [
            {
                "type": "paragraph",
                "content": [{"type": "text", "text": text}],
            }
        ],
    }


@mcp.tool(description="Log time spent on a JIRA issue.")
async def add_worklog(
    issue_key: Annotated[str, Field(description="Issue key (e.g., PROJ-123)")],
    time_spent: Annotated[
        str,
        Field(description="Time spent in JIRA format (e.g., '2h 30m', '1d', '3h')"),
    ],
    comment: Annotated[
        str | None, Field(description="Optional comment describing the work")
    ] = None,
    started: Annotated[
        str | None,
        Field(description="When work started in ISO 8601 format (e.g., '2024-01-15T09:00:00.000+0000')"),
    ] = None,
) -> dict[str, Any]:
    """Add a worklog entry to an issue."""
    try:
        body: dict[str, Any] = {"timeSpent": time_spent}

        if comment:
            body["comment"] = _build_adf_text(comment)

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
    start_at: Annotated[
        int, Field(description="Index of the first worklog to return", ge=0)
    ] = 0,
) -> dict[str, Any]:
    """Get worklogs for an issue."""
    try:
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
            # Extract plain text from ADF comment if possible
            comment_text = ""
            comment = w.get("comment", {})
            if isinstance(comment, dict):
                for content in comment.get("content", []):
                    for item in content.get("content", []):
                        if item.get("type") == "text":
                            comment_text += item.get("text", "")

            worklogs.append({
                "id": w.get("id"),
                "time_spent": w.get("timeSpent"),
                "time_spent_seconds": w.get("timeSpentSeconds"),
                "comment": comment_text or None,
                "author": w.get("author", {}).get("displayName"),
                "started": w.get("started"),
                "created": w.get("created"),
                "updated": w.get("updated"),
            })

        return {
            "success": True,
            "issue_key": issue_key,
            "total": result.get("total"),
            "worklogs": worklogs,
        }
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
        await jira.delete(f"/rest/api/3/issue/{issue_key}/worklog/{worklog_id}")
        return {
            "success": True,
            "deleted_worklog_id": worklog_id,
            "issue_key": issue_key,
        }
    except JiraError as e:
        return {"success": False, "error": str(e), "status_code": e.status_code}
    except Exception as e:
        return {"success": False, "error": str(e)}
