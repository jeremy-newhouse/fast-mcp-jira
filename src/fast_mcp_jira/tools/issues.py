"""Issue tools for JIRA."""

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


@mcp.tool(description="Create a new JIRA issue.")
async def create_issue(
    project_key: Annotated[str, Field(description="Project key (e.g., PROJ)")],
    summary: Annotated[str, Field(description="Issue summary/title")],
    issue_type: Annotated[
        str, Field(description="Issue type name (e.g., Bug, Task, Story, Epic)")
    ] = "Task",
    description: Annotated[
        str | None, Field(description="Issue description (plain text)")
    ] = None,
    priority: Annotated[
        str | None, Field(description="Priority name (e.g., High, Medium, Low)")
    ] = None,
    labels: Annotated[
        list[str] | None, Field(description="List of labels to apply")
    ] = None,
    assignee: Annotated[
        str | None, Field(description="Assignee account ID")
    ] = None,
) -> dict[str, Any]:
    """Create a new issue in JIRA."""
    try:
        fields: dict[str, Any] = {
            "project": {"key": project_key},
            "summary": summary,
            "issuetype": {"name": issue_type},
        }

        if description:
            fields["description"] = _build_adf_text(description)

        if priority:
            fields["priority"] = {"name": priority}

        if labels:
            fields["labels"] = labels

        if assignee:
            fields["assignee"] = {"accountId": assignee}

        result = await jira.post("/rest/api/3/issue", body={"fields": fields})
        return {
            "success": True,
            "issue_key": result.get("key"),
            "issue_id": result.get("id"),
            "self": result.get("self"),
        }
    except JiraError as e:
        return {"success": False, "error": str(e), "status_code": e.status_code}
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool(description="Get details of a JIRA issue by its key.")
async def get_issue(
    issue_key: Annotated[str, Field(description="Issue key (e.g., PROJ-123)")],
    fields: Annotated[
        str | None,
        Field(description="Comma-separated list of fields to return (e.g., summary,status,assignee)"),
    ] = None,
    expand: Annotated[
        str | None,
        Field(description="Comma-separated list of expansions (e.g., changelog,renderedFields)"),
    ] = None,
) -> dict[str, Any]:
    """Get issue details by key."""
    try:
        params: dict[str, str] = {}
        if fields:
            params["fields"] = fields
        if expand:
            params["expand"] = expand

        result = await jira.get(
            f"/rest/api/3/issue/{issue_key}",
            params=params if params else None,
        )
        return {"success": True, "issue": result}
    except JiraError as e:
        return {"success": False, "error": str(e), "status_code": e.status_code}
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool(description="Search for JIRA issues using JQL (JIRA Query Language).")
async def search_issues(
    jql: Annotated[str, Field(description="JQL query string (e.g., project=PROJ AND status='In Progress')")],
    fields: Annotated[
        str | None,
        Field(description="Comma-separated list of fields to return (default: key,summary,status,assignee,priority)"),
    ] = "key,summary,status,assignee,priority",
    max_results: Annotated[
        int, Field(description="Maximum number of results to return", ge=1, le=100)
    ] = 50,
    start_at: Annotated[
        int, Field(description="Index of the first result to return", ge=0)
    ] = 0,
) -> dict[str, Any]:
    """Search for issues using JQL."""
    try:
        params: dict[str, Any] = {
            "jql": jql,
            "maxResults": max_results,
            "startAt": start_at,
        }
        if fields:
            params["fields"] = fields

        result = await jira.get("/rest/api/3/search", params=params)
        return {
            "success": True,
            "total": result.get("total"),
            "start_at": result.get("startAt"),
            "max_results": result.get("maxResults"),
            "issues": result.get("issues", []),
        }
    except JiraError as e:
        return {"success": False, "error": str(e), "status_code": e.status_code}
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool(description="Update fields on an existing JIRA issue.")
async def update_issue(
    issue_key: Annotated[str, Field(description="Issue key (e.g., PROJ-123)")],
    summary: Annotated[str | None, Field(description="New summary/title")] = None,
    description: Annotated[
        str | None, Field(description="New description (plain text)")
    ] = None,
    priority: Annotated[
        str | None, Field(description="New priority name (e.g., High, Medium, Low)")
    ] = None,
    labels: Annotated[
        list[str] | None, Field(description="New list of labels (replaces existing)")
    ] = None,
    assignee: Annotated[
        str | None, Field(description="New assignee account ID (use empty string to unassign)")
    ] = None,
) -> dict[str, Any]:
    """Update issue fields."""
    try:
        fields: dict[str, Any] = {}

        if summary is not None:
            fields["summary"] = summary

        if description is not None:
            fields["description"] = _build_adf_text(description)

        if priority is not None:
            fields["priority"] = {"name": priority}

        if labels is not None:
            fields["labels"] = labels

        if assignee is not None:
            if assignee == "":
                fields["assignee"] = None
            else:
                fields["assignee"] = {"accountId": assignee}

        if not fields:
            return {"success": False, "error": "No fields to update"}

        await jira.put(f"/rest/api/3/issue/{issue_key}", body={"fields": fields})
        return {"success": True, "issue_key": issue_key, "updated_fields": list(fields.keys())}
    except JiraError as e:
        return {"success": False, "error": str(e), "status_code": e.status_code}
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool(description="Delete a JIRA issue.")
async def delete_issue(
    issue_key: Annotated[str, Field(description="Issue key to delete (e.g., PROJ-123)")],
    delete_subtasks: Annotated[
        bool, Field(description="Whether to delete subtasks as well")
    ] = False,
) -> dict[str, Any]:
    """Delete an issue."""
    try:
        path = f"/rest/api/3/issue/{issue_key}"
        if delete_subtasks:
            path += "?deleteSubtasks=true"

        await jira.delete(path)
        return {"success": True, "deleted": issue_key}
    except JiraError as e:
        return {"success": False, "error": str(e), "status_code": e.status_code}
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool(description="Transition a JIRA issue to a new status.")
async def transition_issue(
    issue_key: Annotated[str, Field(description="Issue key (e.g., PROJ-123)")],
    transition_id: Annotated[
        str | None, Field(description="Transition ID to execute (use get_transitions to find available IDs)")
    ] = None,
    transition_name: Annotated[
        str | None, Field(description="Transition name to execute (e.g., 'Done', 'In Progress')")
    ] = None,
) -> dict[str, Any]:
    """Transition an issue to a new status."""
    try:
        if not transition_id and not transition_name:
            # Return available transitions
            result = await jira.get(f"/rest/api/3/issue/{issue_key}/transitions")
            transitions = result.get("transitions", [])
            return {
                "success": True,
                "available_transitions": [
                    {"id": t["id"], "name": t["name"], "to": t.get("to", {}).get("name")}
                    for t in transitions
                ],
            }

        # Find transition ID by name if needed
        if not transition_id and transition_name:
            result = await jira.get(f"/rest/api/3/issue/{issue_key}/transitions")
            transitions = result.get("transitions", [])
            for t in transitions:
                if t["name"].lower() == transition_name.lower():
                    transition_id = t["id"]
                    break
            if not transition_id:
                available = [t["name"] for t in transitions]
                return {
                    "success": False,
                    "error": f"Transition '{transition_name}' not found. Available: {available}",
                }

        # Execute transition
        await jira.post(
            f"/rest/api/3/issue/{issue_key}/transitions",
            body={"transition": {"id": transition_id}},
        )
        return {"success": True, "issue_key": issue_key, "transition_id": transition_id}
    except JiraError as e:
        return {"success": False, "error": str(e), "status_code": e.status_code}
    except Exception as e:
        return {"success": False, "error": str(e)}
