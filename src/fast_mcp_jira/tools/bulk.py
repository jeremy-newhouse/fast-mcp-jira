"""Bulk operation tools for JIRA.

This module provides tools for performing bulk operations on multiple issues:
- bulk_update_issues: Update multiple issues at once
- bulk_transition_issues: Transition multiple issues to a new status
- bulk_add_comments: Add comments to multiple issues

Security Features:
- Issue keys are validated against JIRA format
- Batch size limits prevent abuse

Performance:
- Uses asyncio.gather for parallel execution
- Respects rate limiter
"""

import asyncio
from typing import Annotated, Any

from pydantic import Field

from ..config import get_settings
from ..logging_config import get_logger
from ..server import jira, mcp
from ..services.jira_client import JiraError
from ..utils.validation import ValidationError, validate_issue_key

logger = get_logger(__name__)


async def _update_single_issue(issue_key: str, updates: dict[str, Any]) -> dict[str, Any]:
    """Update a single issue and return result."""
    try:
        await jira.put(f"/rest/api/3/issue/{issue_key}", body={"fields": updates})
        return {"issue_key": issue_key, "success": True}
    except JiraError as e:
        return {"issue_key": issue_key, "success": False, "error": str(e)}
    except Exception as e:
        return {"issue_key": issue_key, "success": False, "error": str(e)}


async def _transition_single_issue(issue_key: str, transition_id: str) -> dict[str, Any]:
    """Transition a single issue and return result."""
    try:
        await jira.post(
            f"/rest/api/3/issue/{issue_key}/transitions",
            body={"transition": {"id": transition_id}},
        )
        return {"issue_key": issue_key, "success": True}
    except JiraError as e:
        return {"issue_key": issue_key, "success": False, "error": str(e)}
    except Exception as e:
        return {"issue_key": issue_key, "success": False, "error": str(e)}


async def _add_single_comment(issue_key: str, body: str) -> dict[str, Any]:
    """Add comment to a single issue and return result."""
    try:
        from ..utils.adf import markdown_to_adf

        await jira.post(
            f"/rest/api/3/issue/{issue_key}/comment",
            body={"body": markdown_to_adf(body)},
        )
        return {"issue_key": issue_key, "success": True}
    except JiraError as e:
        return {"issue_key": issue_key, "success": False, "error": str(e)}
    except Exception as e:
        return {"issue_key": issue_key, "success": False, "error": str(e)}


async def _get_transition_id(issue_key: str, transition_name: str) -> str | None:
    """Get transition ID by name for an issue."""
    try:
        result = await jira.get(f"/rest/api/3/issue/{issue_key}/transitions")
        for t in result.get("transitions", []):
            if t.get("name", "").lower() == transition_name.lower():
                return t.get("id")
        return None
    except Exception:
        return None


@mcp.tool(description="Update multiple issues at once with the same field values.")
async def bulk_update_issues(
    issue_keys: Annotated[
        list[str],
        Field(description="List of issue keys to update (e.g., ['PROJ-1', 'PROJ-2', 'PROJ-3'])"),
    ],
    updates: Annotated[
        dict[str, Any],
        Field(
            description=(
                "Fields to update on all issues. Example: "
                '{"priority": {"name": "High"}, "labels": ["urgent", "review"]}'
            )
        ),
    ],
) -> dict[str, Any]:
    """Update multiple issues with the same field values.

    Performs updates in parallel while respecting rate limits.
    Returns detailed results for each issue.

    Args:
        issue_keys: List of issue keys to update.
        updates: Field values to set on all issues. Use JIRA field names.

    Returns:
        Summary with success/failure counts and per-issue results.

    Example updates:
        - Set priority: {"priority": {"name": "High"}}
        - Add labels: {"labels": ["label1", "label2"]}
        - Set assignee: {"assignee": {"accountId": "..."}}
        - Set custom field: {"customfield_10001": "value"}
    """
    settings = get_settings()

    # Validate batch size
    if len(issue_keys) > settings.bulk_max_batch_size:
        return {
            "success": False,
            "error": f"Batch size {len(issue_keys)} exceeds maximum {settings.bulk_max_batch_size}",
            "code": "BATCH_SIZE_ERROR",
        }

    # Validate issue keys
    try:
        validated_keys = [validate_issue_key(key) for key in issue_keys]
    except ValidationError as e:
        return {"success": False, "error": str(e), "field": "issue_keys"}

    if not updates:
        return {"success": False, "error": "No updates provided", "code": "VALIDATION_ERROR"}

    logger.info(
        "Starting bulk update",
        extra={"issue_count": len(validated_keys), "fields": list(updates.keys())},
    )

    # Execute updates in parallel
    tasks = [_update_single_issue(key, updates) for key in validated_keys]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Process results
    processed_results = []
    success_count = 0
    failure_count = 0

    for result in results:
        if isinstance(result, Exception):
            processed_results.append({"success": False, "error": str(result)})
            failure_count += 1
        elif isinstance(result, dict):
            processed_results.append(result)
            if result.get("success"):
                success_count += 1
            else:
                failure_count += 1
        else:
            processed_results.append({"success": False, "error": "Unknown result"})
            failure_count += 1

    logger.info(
        "Bulk update completed",
        extra={"success_count": success_count, "failure_count": failure_count},
    )

    return {
        "success": failure_count == 0,
        "total": len(validated_keys),
        "updated": success_count,
        "failed": failure_count,
        "results": processed_results,
    }


@mcp.tool(description="Transition multiple issues to a new status.")
async def bulk_transition_issues(
    issue_keys: Annotated[
        list[str],
        Field(description="List of issue keys to transition"),
    ],
    transition_name: Annotated[
        str,
        Field(description="Target transition name (e.g., 'In Progress', 'Done', 'To Do')"),
    ],
) -> dict[str, Any]:
    """Transition multiple issues to a new status.

    Note: Transition names must match exactly (case-insensitive).
    Available transitions depend on the issue's current status and workflow.

    Args:
        issue_keys: List of issue keys to transition.
        transition_name: Name of the transition to apply.

    Returns:
        Summary with success/failure counts and per-issue results.
    """
    settings = get_settings()

    # Validate batch size
    if len(issue_keys) > settings.bulk_max_batch_size:
        return {
            "success": False,
            "error": f"Batch size {len(issue_keys)} exceeds maximum {settings.bulk_max_batch_size}",
            "code": "BATCH_SIZE_ERROR",
        }

    # Validate issue keys
    try:
        validated_keys = [validate_issue_key(key) for key in issue_keys]
    except ValidationError as e:
        return {"success": False, "error": str(e), "field": "issue_keys"}

    logger.info(
        "Starting bulk transition",
        extra={"issue_count": len(validated_keys), "transition": transition_name},
    )

    # First, get transition IDs for each issue (they may differ based on current state)
    transition_tasks = []
    for key in validated_keys:
        transition_tasks.append(_get_transition_id(key, transition_name))

    transition_ids = await asyncio.gather(*transition_tasks)

    # Execute transitions
    results = []
    success_count = 0
    failure_count = 0

    for key, transition_id in zip(validated_keys, transition_ids):
        if transition_id is None:
            results.append(
                {
                    "issue_key": key,
                    "success": False,
                    "error": f"Transition '{transition_name}' not available for this issue",
                }
            )
            failure_count += 1
        else:
            result = await _transition_single_issue(key, transition_id)
            results.append(result)
            if result.get("success"):
                success_count += 1
            else:
                failure_count += 1

    logger.info(
        "Bulk transition completed",
        extra={"success_count": success_count, "failure_count": failure_count},
    )

    return {
        "success": failure_count == 0,
        "total": len(validated_keys),
        "transitioned": success_count,
        "failed": failure_count,
        "transition_name": transition_name,
        "results": results,
    }


@mcp.tool(description="Add the same comment to multiple issues.")
async def bulk_add_comments(
    issue_keys: Annotated[
        list[str],
        Field(description="List of issue keys to add comment to"),
    ],
    body: Annotated[
        str,
        Field(
            description=(
                "Comment text to add. Supports markdown: **bold**, *italic*, "
                "- bullet lists, 1. numbered lists, ```code blocks```"
            )
        ),
    ],
) -> dict[str, Any]:
    """Add the same comment to multiple issues.

    Useful for:
    - Announcing changes affecting multiple issues
    - Adding release notes to related issues
    - Bulk status updates

    Args:
        issue_keys: List of issue keys to comment on.
        body: Comment text (supports markdown).

    Returns:
        Summary with success/failure counts and per-issue results.
    """
    settings = get_settings()

    # Validate batch size
    if len(issue_keys) > settings.bulk_max_batch_size:
        return {
            "success": False,
            "error": f"Batch size {len(issue_keys)} exceeds maximum {settings.bulk_max_batch_size}",
            "code": "BATCH_SIZE_ERROR",
        }

    # Validate issue keys
    try:
        validated_keys = [validate_issue_key(key) for key in issue_keys]
    except ValidationError as e:
        return {"success": False, "error": str(e), "field": "issue_keys"}

    if not body.strip():
        return {
            "success": False,
            "error": "Comment body cannot be empty",
            "code": "VALIDATION_ERROR",
        }

    logger.info(
        "Starting bulk comment",
        extra={"issue_count": len(validated_keys), "comment_length": len(body)},
    )

    # Execute comments in parallel
    tasks = [_add_single_comment(key, body) for key in validated_keys]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Process results
    processed_results = []
    success_count = 0
    failure_count = 0

    for result in results:
        if isinstance(result, Exception):
            processed_results.append({"success": False, "error": str(result)})
            failure_count += 1
        elif isinstance(result, dict):
            processed_results.append(result)
            if result.get("success"):
                success_count += 1
            else:
                failure_count += 1
        else:
            processed_results.append({"success": False, "error": "Unknown result"})
            failure_count += 1

    logger.info(
        "Bulk comment completed",
        extra={"success_count": success_count, "failure_count": failure_count},
    )

    return {
        "success": failure_count == 0,
        "total": len(validated_keys),
        "commented": success_count,
        "failed": failure_count,
        "results": processed_results,
    }
