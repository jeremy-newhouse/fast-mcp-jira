"""Watcher tools for JIRA issues."""

from typing import Annotated, Any

from pydantic import Field

from ..server import jira, mcp
from ..services.jira_client import JiraError


@mcp.tool(description="Get all watchers of a JIRA issue.")
async def get_watchers(
    issue_key: Annotated[str, Field(description="Issue key (e.g., PROJ-123)")],
) -> dict[str, Any]:
    """Get list of users watching an issue."""
    try:
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

        return {
            "success": True,
            "issue_key": issue_key,
            "watch_count": result.get("watchCount", len(watchers)),
            "is_watching": result.get("isWatching", False),
            "watchers": watchers,
        }
    except JiraError as e:
        return {"success": False, "error": str(e), "status_code": e.status_code}
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool(description="Add a user as a watcher to a JIRA issue.")
async def add_watcher(
    issue_key: Annotated[str, Field(description="Issue key (e.g., PROJ-123)")],
    account_id: Annotated[str, Field(description="Account ID of the user to add as watcher")],
) -> dict[str, Any]:
    """Add a user as a watcher to an issue."""
    try:
        # The API expects the account ID as a quoted JSON string in the body
        # We use the raw post with the account_id wrapped in quotes
        import httpx

        headers = {
            "Authorization": jira._get_auth_header(),
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        async with httpx.AsyncClient(
            base_url=jira.settings.base_url,
            verify=jira.settings.jira_ssl_verify,
            timeout=30.0,
        ) as client:
            response = await client.post(
                f"/rest/api/3/issue/{issue_key}/watchers",
                content=f'"{account_id}"',  # Raw JSON string
                headers=headers,
            )
        if not response.is_success:
            raise JiraError(
                message=f"JIRA API error ({response.status_code}): {response.text}",
                status_code=response.status_code,
            )
        return {
            "success": True,
            "issue_key": issue_key,
            "added_watcher": account_id,
        }
    except JiraError as e:
        return {"success": False, "error": str(e), "status_code": e.status_code}
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool(description="Remove a user from watching a JIRA issue.")
async def remove_watcher(
    issue_key: Annotated[str, Field(description="Issue key (e.g., PROJ-123)")],
    account_id: Annotated[str, Field(description="Account ID of the user to remove as watcher")],
) -> dict[str, Any]:
    """Remove a user from watching an issue."""
    try:
        await jira.delete(
            f"/rest/api/3/issue/{issue_key}/watchers",
            params={"accountId": account_id},
        )
        return {
            "success": True,
            "issue_key": issue_key,
            "removed_watcher": account_id,
        }
    except JiraError as e:
        return {"success": False, "error": str(e), "status_code": e.status_code}
    except Exception as e:
        return {"success": False, "error": str(e)}
