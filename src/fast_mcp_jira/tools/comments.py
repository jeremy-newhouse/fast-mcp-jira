"""Comment tools for JIRA issues.

This module provides tools for managing comments on JIRA issues:
- add_comment: Add a new comment with markdown support
- get_comments: List all comments on an issue
- delete_comment: Remove a comment

Security Features:
- Issue keys are validated against JIRA format
- Comment IDs are validated as numeric
- Comment body length is limited (max 32,767 chars)
"""

from typing import Annotated, Any

from pydantic import Field
from pydantic import ValidationError as PydanticValidationError

from ..server import jira, mcp
from ..services.jira_client import JiraError
from ..utils.adf import extract_text_from_adf, markdown_to_adf
from ..utils.validation import (
    NumericIdInput,
    ValidationError,
    validate_comment_body,
    validate_issue_key,
)


@mcp.tool(description="Add a comment to a JIRA issue.")
async def add_comment(
    issue_key: Annotated[str, Field(description="Issue key (e.g., PROJ-123)")],
    body: Annotated[
        str,
        Field(
            description="Comment text. Supports markdown: **bold**, *italic*, "
            "- bullet lists, 1. numbered lists, [] checklists, ```code blocks```"
        ),
    ],
) -> dict[str, Any]:
    """Add a comment to an issue."""
    try:
        issue_key = validate_issue_key(issue_key)
        body = validate_comment_body(body)

        result = await jira.post(
            f"/rest/api/3/issue/{issue_key}/comment",
            body={"body": markdown_to_adf(body)},
        )
        return {
            "success": True,
            "comment_id": result.get("id"),
            "issue_key": issue_key,
            "created": result.get("created"),
            "author": result.get("author", {}).get("displayName"),
        }
    except ValidationError as e:
        return {"success": False, "error": str(e), "field": e.field}
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
    start_at: Annotated[int, Field(description="Index of the first comment to return", ge=0)] = 0,
    order_by: Annotated[
        str, Field(description="Order by field (created or -created for descending)")
    ] = "-created",
) -> dict[str, Any]:
    """Get comments for an issue."""
    try:
        issue_key = validate_issue_key(issue_key)

        params = {
            "maxResults": max_results,
            "startAt": start_at,
            "orderBy": order_by,
        }
        result = await jira.get(
            f"/rest/api/3/issue/{issue_key}/comment",
            params=params,
        )
        comments = [
            {
                "id": c.get("id"),
                "body": extract_text_from_adf(c.get("body", {})),
                "author": c.get("author", {}).get("displayName"),
                "created": c.get("created"),
                "updated": c.get("updated"),
            }
            for c in result.get("comments", [])
        ]

        return {
            "success": True,
            "issue_key": issue_key,
            "total": result.get("total"),
            "comments": comments,
        }
    except ValidationError as e:
        return {"success": False, "error": str(e), "field": e.field}
    except JiraError as e:
        return {"success": False, "error": str(e), "status_code": e.status_code}
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool(description="Delete a comment from a JIRA issue.")
async def delete_comment(
    issue_key: Annotated[str, Field(description="Issue key (e.g., PROJ-123)")],
    comment_id: Annotated[str, Field(description="Comment ID to delete")],
) -> dict[str, Any]:
    """Delete a comment from a JIRA issue.

    Permanently removes a comment. This action cannot be undone.
    Requires appropriate permissions on the issue.

    Args:
        issue_key: The JIRA issue key (e.g., "PROJ-123").
        comment_id: Numeric ID of the comment to delete.

    Returns:
        dict containing:
            - success (bool): Whether deletion succeeded
            - deleted_comment_id (str): ID of deleted comment
            - issue_key (str): The issue key

    Example:
        >>> await delete_comment(issue_key="PROJ-123", comment_id="10001")
        {"success": True, "deleted_comment_id": "10001", "issue_key": "PROJ-123"}
    """
    try:
        issue_key = validate_issue_key(issue_key)
        validated_id = NumericIdInput(id=comment_id)

        await jira.delete(f"/rest/api/3/issue/{issue_key}/comment/{validated_id.id}")
        return {
            "success": True,
            "deleted_comment_id": validated_id.id,
            "issue_key": issue_key,
        }
    except ValidationError as e:
        return {"success": False, "error": str(e), "field": e.field}
    except PydanticValidationError as e:
        return {"success": False, "error": str(e.errors()[0]["msg"]), "field": "comment_id"}
    except JiraError as e:
        return {"success": False, "error": str(e), "status_code": e.status_code}
    except Exception as e:
        return {"success": False, "error": str(e)}
