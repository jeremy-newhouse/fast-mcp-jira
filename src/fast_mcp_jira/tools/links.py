"""Issue link tools for JIRA."""

from typing import Annotated, Any

from pydantic import Field

from ..server import jira, mcp
from ..services.jira_client import JiraError


@mcp.tool(description="Get all issue link types available in JIRA.")
async def get_link_types() -> dict[str, Any]:
    """Get list of all issue link types (e.g., blocks, duplicates, relates to)."""
    try:
        result = await jira.get("/rest/api/3/issueLinkType")
        link_types = []
        for lt in result.get("issueLinkTypes", []):
            link_types.append(
                {
                    "id": lt.get("id"),
                    "name": lt.get("name"),
                    "inward": lt.get("inward"),
                    "outward": lt.get("outward"),
                }
            )

        return {
            "success": True,
            "total": len(link_types),
            "link_types": link_types,
        }
    except JiraError as e:
        return {"success": False, "error": str(e), "status_code": e.status_code}
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool(description="Create a link between two JIRA issues.")
async def create_link(
    inward_issue: Annotated[str, Field(description="Inward issue key (e.g., PROJ-123)")],
    outward_issue: Annotated[str, Field(description="Outward issue key (e.g., PROJ-456)")],
    link_type: Annotated[
        str, Field(description="Link type name (e.g., 'Blocks', 'Duplicate', 'Relates')")
    ],
) -> dict[str, Any]:
    """Create a link between two issues.

    The link direction is: outward_issue [link_type] inward_issue.
    For example: PROJ-456 blocks PROJ-123
    """
    try:
        body = {
            "type": {"name": link_type},
            "inwardIssue": {"key": inward_issue},
            "outwardIssue": {"key": outward_issue},
        }
        await jira.post("/rest/api/3/issueLink", body=body)
        return {
            "success": True,
            "inward_issue": inward_issue,
            "outward_issue": outward_issue,
            "link_type": link_type,
        }
    except JiraError as e:
        return {"success": False, "error": str(e), "status_code": e.status_code}
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool(description="Delete an issue link by its ID.")
async def delete_link(
    link_id: Annotated[str, Field(description="Issue link ID to delete")],
) -> dict[str, Any]:
    """Delete an issue link."""
    try:
        await jira.delete(f"/rest/api/3/issueLink/{link_id}")
        return {
            "success": True,
            "deleted_link_id": link_id,
        }
    except JiraError as e:
        return {"success": False, "error": str(e), "status_code": e.status_code}
    except Exception as e:
        return {"success": False, "error": str(e)}
