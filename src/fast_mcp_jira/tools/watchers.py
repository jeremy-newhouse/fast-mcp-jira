"""Watcher tools for JIRA issues.

This module provides tools for managing issue watchers:
- get_watchers: List all users watching an issue
- add_watcher: Add a user as a watcher
- remove_watcher: Remove a user from watching

Security Features:
- Issue keys are validated against JIRA format
- Account IDs are validated for proper format
- Response sanitization prevents XSS
"""

import json
from typing import Annotated, Any

from pydantic import Field

from ..logging_config import get_logger
from ..server import jira, mcp
from ..services.jira_client import JiraError
from ..utils.validation import (
    ValidationError,
    build_response,
    validate_account_id,
    validate_issue_key,
)

logger = get_logger(__name__)


@mcp.tool(description="Get all watchers of a JIRA issue.")
async def get_watchers(
    issue_key: Annotated[str, Field(description="Issue key (e.g., PROJ-123)")],
) -> dict[str, Any]:
    """Get list of users watching an issue."""
    try:
        issue_key = validate_issue_key(issue_key)

        result = await jira.get(f"/rest/api/3/issue/{issue_key}/watchers")
        watchers = []
        for w in result.get("watchers", []):
            watchers.append(
                {
                    "account_id": w.get("accountId"),
                    "display_name": w.get("displayName"),
                    "email": w.get("emailAddress"),
                    "active": w.get("active"),
                }
            )

        return build_response(
            True,
            issue_key=issue_key,
            watch_count=result.get("watchCount", len(watchers)),
            is_watching=result.get("isWatching", False),
            watchers=watchers,
        )
    except ValidationError as e:
        return build_response(False, error=str(e), field=e.field)
    except JiraError as e:
        return build_response(False, error=str(e), status_code=e.status_code)
    except Exception:
        logger.exception("Unexpected error getting watchers for %s", issue_key)
        return build_response(False, error="Internal error occurred")


@mcp.tool(description="Add a user as a watcher to a JIRA issue.")
async def add_watcher(
    issue_key: Annotated[str, Field(description="Issue key (e.g., PROJ-123)")],
    account_id: Annotated[str, Field(description="Account ID of the user to add as watcher")],
) -> dict[str, Any]:
    """Add a user as a watcher to an issue."""
    try:
        issue_key = validate_issue_key(issue_key)
        account_id = validate_account_id(account_id, "account_id")

        # The API expects the account ID as a quoted JSON string in the body
        # Use json.dumps for proper encoding instead of f-string (security)
        await jira.post_raw(
            f"/rest/api/3/issue/{issue_key}/watchers",
            content=json.dumps(account_id),
        )
        return build_response(
            True,
            issue_key=issue_key,
            added_watcher=account_id,
        )
    except ValidationError as e:
        return build_response(False, error=str(e), field=e.field)
    except JiraError as e:
        return build_response(False, error=str(e), status_code=e.status_code)
    except Exception:
        logger.exception("Unexpected error adding watcher to %s", issue_key)
        return build_response(False, error="Internal error occurred")


@mcp.tool(description="Remove a user from watching a JIRA issue.")
async def remove_watcher(
    issue_key: Annotated[str, Field(description="Issue key (e.g., PROJ-123)")],
    account_id: Annotated[str, Field(description="Account ID of the user to remove as watcher")],
) -> dict[str, Any]:
    """Remove a user from watching an issue."""
    try:
        issue_key = validate_issue_key(issue_key)
        account_id = validate_account_id(account_id, "account_id")

        await jira.delete(
            f"/rest/api/3/issue/{issue_key}/watchers",
            params={"accountId": account_id},
        )
        return build_response(
            True,
            issue_key=issue_key,
            removed_watcher=account_id,
        )
    except ValidationError as e:
        return build_response(False, error=str(e), field=e.field)
    except JiraError as e:
        return build_response(False, error=str(e), status_code=e.status_code)
    except Exception:
        logger.exception("Unexpected error removing watcher from %s", issue_key)
        return build_response(False, error="Internal error occurred")
