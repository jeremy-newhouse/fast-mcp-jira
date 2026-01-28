"""Comment tools for JIRA issues."""

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


@mcp.tool(description="Add a comment to a JIRA issue.")
async def add_comment(
    issue_key: Annotated[str, Field(description="Issue key (e.g., PROJ-123)")],
    body: Annotated[str, Field(description="Comment text content")],
) -> dict[str, Any]:
    """Add a comment to an issue."""
    try:
        result = await jira.post(
            f"/rest/api/3/issue/{issue_key}/comment",
            body={"body": _build_adf_text(body)},
        )
        return {
            "success": True,
            "comment_id": result.get("id"),
            "issue_key": issue_key,
            "created": result.get("created"),
            "author": result.get("author", {}).get("displayName"),
        }
    except JiraError as e:
        return {"success": False, "error": str(e), "status_code": e.status_code}
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool(description="Get all comments on a JIRA issue.")
async def get_comments(
    issue_key: Annotated[str, Field(description="Issue key (e.g., PROJ-123)")],
    max_results: Annotated[
        int, Field(description="Maximum number of comments to return", ge=1, le=100)
    ] = 50,
    start_at: Annotated[
        int, Field(description="Index of the first comment to return", ge=0)
    ] = 0,
    order_by: Annotated[
        str, Field(description="Order by field (created or -created for descending)")
    ] = "-created",
) -> dict[str, Any]:
    """Get comments for an issue."""
    try:
        params = {
            "maxResults": max_results,
            "startAt": start_at,
            "orderBy": order_by,
        }
        result = await jira.get(
            f"/rest/api/3/issue/{issue_key}/comment",
            params=params,
        )
        comments = []
        for c in result.get("comments", []):
            # Extract plain text from ADF body if possible
            body_text = ""
            body = c.get("body", {})
            if isinstance(body, dict):
                for content in body.get("content", []):
                    for item in content.get("content", []):
                        if item.get("type") == "text":
                            body_text += item.get("text", "")
            comments.append({
                "id": c.get("id"),
                "body": body_text or str(body),
                "author": c.get("author", {}).get("displayName"),
                "created": c.get("created"),
                "updated": c.get("updated"),
            })

        return {
            "success": True,
            "issue_key": issue_key,
            "total": result.get("total"),
            "comments": comments,
        }
    except JiraError as e:
        return {"success": False, "error": str(e), "status_code": e.status_code}
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool(description="Delete a comment from a JIRA issue.")
async def delete_comment(
    issue_key: Annotated[str, Field(description="Issue key (e.g., PROJ-123)")],
    comment_id: Annotated[str, Field(description="Comment ID to delete")],
) -> dict[str, Any]:
    """Delete a comment from an issue."""
    try:
        await jira.delete(f"/rest/api/3/issue/{issue_key}/comment/{comment_id}")
        return {
            "success": True,
            "deleted_comment_id": comment_id,
            "issue_key": issue_key,
        }
    except JiraError as e:
        return {"success": False, "error": str(e), "status_code": e.status_code}
    except Exception as e:
        return {"success": False, "error": str(e)}
