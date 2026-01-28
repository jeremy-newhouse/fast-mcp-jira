"""Issue tools for JIRA.

This module provides tools for managing JIRA issues:
- create_issue: Create new issues with project, summary, type, description
- get_issue: Fetch issue details by key
- search_issues: Query issues using JQL (JIRA Query Language)
- update_issue: Modify issue fields
- delete_issue: Remove an issue
- transition_issue: Change issue status
- get_transitions: List available status transitions
- get_changelog: View issue history

Security Features:
- JQL queries are validated to prevent injection attacks
- Issue keys are validated against JIRA format
- Input lengths are enforced to prevent DoS
"""

from typing import Annotated, Any

from pydantic import Field
from pydantic import ValidationError as PydanticValidationError

from ..server import jira, mcp
from ..services.jira_client import JiraError
from ..utils.adf import markdown_to_adf
from ..utils.validation import (
    JqlInput,
    ValidationError,
    validate_issue_key,
    validate_labels,
    validate_project_key,
    validate_summary,
)


@mcp.tool(description="Create a new JIRA issue.")
async def create_issue(
    project_key: Annotated[str, Field(description="Project key (e.g., PROJ)")],
    summary: Annotated[str, Field(description="Issue summary/title (max 255 chars)")],
    issue_type: Annotated[
        str, Field(description="Issue type name (e.g., Bug, Task, Story, Epic)")
    ] = "Task",
    description: Annotated[
        str | None,
        Field(
            description="Issue description. Supports markdown: **bold**, *italic*, "
            "- bullet lists, 1. numbered lists, [] checklists, ```code blocks```"
        ),
    ] = None,
    priority: Annotated[
        str | None, Field(description="Priority name (e.g., High, Medium, Low)")
    ] = None,
    labels: Annotated[list[str] | None, Field(description="List of labels to apply")] = None,
    assignee: Annotated[str | None, Field(description="Assignee account ID")] = None,
) -> dict[str, Any]:
    """Create a new issue in JIRA."""
    try:
        # Validate inputs
        project_key = validate_project_key(project_key)
        summary = validate_summary(summary)
        labels = validate_labels(labels)

        fields: dict[str, Any] = {
            "project": {"key": project_key},
            "summary": summary,
            "issuetype": {"name": issue_type},
        }

        if description:
            fields["description"] = markdown_to_adf(description)

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
    except ValidationError as e:
        return {"success": False, "error": str(e), "field": e.field}
    except JiraError as e:
        return {"success": False, "error": str(e), "status_code": e.status_code}
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool(description="Get details of a JIRA issue by its key.")
async def get_issue(
    issue_key: Annotated[str, Field(description="Issue key (e.g., PROJ-123)")],
    fields: Annotated[
        str | None,
        Field(description="Comma-separated fields to return (e.g., summary,status,assignee)"),
    ] = None,
    expand: Annotated[
        str | None,
        Field(description="Comma-separated list of expansions (e.g., changelog,renderedFields)"),
    ] = None,
) -> dict[str, Any]:
    """Get issue details by key."""
    try:
        issue_key = validate_issue_key(issue_key)
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
    except ValidationError as e:
        return {"success": False, "error": str(e), "field": e.field}
    except JiraError as e:
        return {"success": False, "error": str(e), "status_code": e.status_code}
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool(description="Search for JIRA issues using JQL (JIRA Query Language).")
async def search_issues(
    jql: Annotated[
        str, Field(description="JQL query string (e.g., project=PROJ AND status='In Progress')")
    ],
    fields: Annotated[
        str | None,
        Field(description="Comma-separated fields (default: key,summary,status,assignee,priority)"),
    ] = "key,summary,status,assignee,priority",
    max_results: Annotated[
        int, Field(description="Maximum number of results to return", ge=1, le=100)
    ] = 50,
    next_page_token: Annotated[
        str | None, Field(description="Token for fetching next page of results")
    ] = None,
) -> dict[str, Any]:
    """Search for JIRA issues using JQL (JIRA Query Language).

    JQL is a powerful query language for finding issues. Common patterns:
    - project = PROJ: Issues in a project
    - status = "In Progress": Issues by status
    - assignee = currentUser(): Your assigned issues
    - created >= -7d: Issues from last 7 days
    - labels in (bug, urgent): Issues with specific labels

    Security: JQL is validated to prevent injection attacks.

    Args:
        jql: JQL query string. Max 10,000 characters.
        fields: Comma-separated field names to return.
            Default: key,summary,status,assignee,priority
        max_results: Number of results per page (1-100). Default: 50.
        next_page_token: Pagination token from previous response.

    Returns:
        dict containing:
            - success (bool): Whether query succeeded
            - issues (list): Matching issues with requested fields
            - next_page_token (str|None): Token for next page, if more results
            - is_last (bool): True if this is the last page

    Example:
        >>> await search_issues(jql="project = PROJ AND type = Bug")
        {
            "success": True,
            "issues": [{"key": "PROJ-123", "fields": {...}}, ...],
            "next_page_token": None,
            "is_last": True
        }
    """
    try:
        # Validate JQL to prevent injection
        validated_jql = JqlInput(jql=jql)

        params: dict[str, Any] = {
            "jql": validated_jql.jql,
            "maxResults": max_results,
        }
        if fields:
            params["fields"] = fields
        if next_page_token:
            params["nextPageToken"] = next_page_token

        result = await jira.get("/rest/api/3/search/jql", params=params)
        return {
            "success": True,
            "issues": result.get("issues", []),
            "next_page_token": result.get("nextPageToken"),
            "is_last": result.get("isLast", True),
        }
    except PydanticValidationError as e:
        return {"success": False, "error": str(e.errors()[0]["msg"]), "field": "jql"}
    except JiraError as e:
        return {"success": False, "error": str(e), "status_code": e.status_code}
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool(description="Update fields on an existing JIRA issue.")
async def update_issue(
    issue_key: Annotated[str, Field(description="Issue key (e.g., PROJ-123)")],
    summary: Annotated[str | None, Field(description="New summary/title (max 255 chars)")] = None,
    description: Annotated[
        str | None,
        Field(
            description="New description. Supports markdown: **bold**, *italic*, "
            "- bullet lists, 1. numbered lists, [] checklists, ```code blocks```"
        ),
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
        issue_key = validate_issue_key(issue_key)
        fields: dict[str, Any] = {}

        # Build update fields
        if summary is not None:
            fields["summary"] = validate_summary(summary)

        if description is not None:
            fields["description"] = markdown_to_adf(description)

        if priority is not None:
            fields["priority"] = {"name": priority}

        if labels is not None:
            validated_labels = validate_labels(labels)
            fields["labels"] = validated_labels if validated_labels else []

        if assignee is not None:
            fields["assignee"] = None if assignee == "" else {"accountId": assignee}

        if not fields:
            return {"success": False, "error": "No fields to update"}

        await jira.put(f"/rest/api/3/issue/{issue_key}", body={"fields": fields})
        return {"success": True, "issue_key": issue_key, "updated_fields": list(fields.keys())}
    except ValidationError as e:
        return {"success": False, "error": str(e), "field": e.field}
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
        issue_key = validate_issue_key(issue_key)
        params = {"deleteSubtasks": "true"} if delete_subtasks else None
        await jira.delete(f"/rest/api/3/issue/{issue_key}", params=params)
        return {"success": True, "deleted": issue_key}
    except ValidationError as e:
        return {"success": False, "error": str(e), "field": e.field}
    except JiraError as e:
        return {"success": False, "error": str(e), "status_code": e.status_code}
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool(description="Transition a JIRA issue to a new status.")
async def transition_issue(
    issue_key: Annotated[str, Field(description="Issue key (e.g., PROJ-123)")],
    transition_id: Annotated[
        str | None, Field(description="Transition ID to execute (from get_transitions)")
    ] = None,
    transition_name: Annotated[
        str | None, Field(description="Transition name to execute (e.g., 'Done', 'In Progress')")
    ] = None,
) -> dict[str, Any]:
    """Transition an issue to a new status."""
    try:
        issue_key = validate_issue_key(issue_key)

        # Fetch available transitions
        result = await jira.get(f"/rest/api/3/issue/{issue_key}/transitions")
        transitions = result.get("transitions", [])

        # If no transition specified, return available options
        if not transition_id and not transition_name:
            return {
                "success": True,
                "available_transitions": [
                    {"id": t["id"], "name": t["name"], "to": t.get("to", {}).get("name")}
                    for t in transitions
                ],
            }

        # Find transition ID by name if needed
        if not transition_id:
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
    except ValidationError as e:
        return {"success": False, "error": str(e), "field": e.field}
    except JiraError as e:
        return {"success": False, "error": str(e), "status_code": e.status_code}
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool(description="Get available transitions for a JIRA issue.")
async def get_transitions(
    issue_key: Annotated[str, Field(description="Issue key (e.g., PROJ-123)")],
) -> dict[str, Any]:
    """Get available workflow transitions for an issue."""
    try:
        issue_key = validate_issue_key(issue_key)
        result = await jira.get(f"/rest/api/3/issue/{issue_key}/transitions")
        transitions = result.get("transitions", [])
        return {
            "success": True,
            "issue_key": issue_key,
            "transitions": [
                {
                    "id": t["id"],
                    "name": t["name"],
                    "to_status": t.get("to", {}).get("name"),
                    "to_status_category": t.get("to", {}).get("statusCategory", {}).get("name"),
                }
                for t in transitions
            ],
        }
    except ValidationError as e:
        return {"success": False, "error": str(e), "field": e.field}
    except JiraError as e:
        return {"success": False, "error": str(e), "status_code": e.status_code}
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool(description="Get changelog/history for a JIRA issue.")
async def get_changelog(
    issue_key: Annotated[str, Field(description="Issue key (e.g., PROJ-123)")],
    max_results: Annotated[
        int, Field(description="Maximum number of changelog entries to return", ge=1, le=100)
    ] = 50,
    start_at: Annotated[
        int, Field(description="Index of the first changelog entry to return", ge=0)
    ] = 0,
) -> dict[str, Any]:
    """Get issue changelog showing field changes over time."""
    try:
        issue_key = validate_issue_key(issue_key)
        params = {"maxResults": max_results, "startAt": start_at}
        result = await jira.get(f"/rest/api/3/issue/{issue_key}/changelog", params=params)

        histories = []
        for history in result.get("values", []):
            changes = []
            for item in history.get("items", []):
                changes.append(
                    {
                        "field": item.get("field"),
                        "from": item.get("fromString"),
                        "to": item.get("toString"),
                    }
                )
            histories.append(
                {
                    "id": history.get("id"),
                    "author": history.get("author", {}).get("displayName"),
                    "created": history.get("created"),
                    "changes": changes,
                }
            )

        return {
            "success": True,
            "issue_key": issue_key,
            "total": result.get("total", len(histories)),
            "start_at": result.get("startAt", start_at),
            "max_results": result.get("maxResults", max_results),
            "histories": histories,
        }
    except ValidationError as e:
        return {"success": False, "error": str(e), "field": e.field}
    except JiraError as e:
        return {"success": False, "error": str(e), "status_code": e.status_code}
    except Exception as e:
        return {"success": False, "error": str(e)}
