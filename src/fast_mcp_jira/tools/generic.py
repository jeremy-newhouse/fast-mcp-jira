"""Generic HTTP tools for JIRA API access."""

import json
from typing import Annotated, Any

from pydantic import Field

from ..server import jira, mcp
from ..services.jira_client import JiraError


def _parse_json_body(body: str | None) -> dict[str, Any] | None:
    """Parse JSON body string into dict."""
    if not body:
        return None
    try:
        parsed = json.loads(body)
        if not isinstance(parsed, dict):
            raise ValueError("Body must be a JSON object")
        return parsed
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON body: {e}")


def _parse_query_params(params: str | None) -> dict[str, str] | None:
    """Parse query params string (key=value&key2=value2) into dict."""
    if not params:
        return None
    result = {}
    for pair in params.split("&"):
        if "=" in pair:
            key, value = pair.split("=", 1)
            result[key.strip()] = value.strip()
    return result if result else None


@mcp.tool(
    description="Make a GET request to any JIRA API endpoint. "
    "Use this for flexible access to JIRA's REST API."
)
async def jira_get(
    path: Annotated[str, Field(description="API path (e.g., /rest/api/3/project)")],
    query_params: Annotated[
        str | None,
        Field(description="Query parameters as key=value pairs separated by & (e.g., maxResults=50&startAt=0)"),
    ] = None,
) -> dict[str, Any]:
    """Make a GET request to any JIRA API endpoint."""
    try:
        params = _parse_query_params(query_params)
        result = await jira.get(path, params=params)
        return {"success": True, "data": result}
    except JiraError as e:
        return {"success": False, "error": str(e), "status_code": e.status_code}
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool(
    description="Make a POST request to any JIRA API endpoint. "
    "Use this to create resources or perform actions."
)
async def jira_post(
    path: Annotated[str, Field(description="API path (e.g., /rest/api/3/issue)")],
    body: Annotated[
        str | None,
        Field(description="Request body as JSON string"),
    ] = None,
    query_params: Annotated[
        str | None,
        Field(description="Query parameters as key=value pairs separated by &"),
    ] = None,
) -> dict[str, Any]:
    """Make a POST request to any JIRA API endpoint."""
    try:
        parsed_body = _parse_json_body(body)
        params = _parse_query_params(query_params)
        result = await jira.post(path, body=parsed_body, params=params)
        return {"success": True, "data": result}
    except (JiraError, ValueError) as e:
        return {"success": False, "error": str(e), "status_code": getattr(e, "status_code", None)}
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool(
    description="Make a PUT request to any JIRA API endpoint. "
    "Use this to replace an entire resource."
)
async def jira_put(
    path: Annotated[str, Field(description="API path (e.g., /rest/api/3/issue/PROJ-123)")],
    body: Annotated[
        str | None,
        Field(description="Request body as JSON string"),
    ] = None,
) -> dict[str, Any]:
    """Make a PUT request to any JIRA API endpoint."""
    try:
        parsed_body = _parse_json_body(body)
        result = await jira.put(path, body=parsed_body)
        return {"success": True, "data": result}
    except (JiraError, ValueError) as e:
        return {"success": False, "error": str(e), "status_code": getattr(e, "status_code", None)}
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool(
    description="Make a PATCH request to any JIRA API endpoint. "
    "Use this to partially update a resource."
)
async def jira_patch(
    path: Annotated[str, Field(description="API path (e.g., /rest/api/3/issue/PROJ-123)")],
    body: Annotated[
        str | None,
        Field(description="Request body as JSON string"),
    ] = None,
) -> dict[str, Any]:
    """Make a PATCH request to any JIRA API endpoint."""
    try:
        parsed_body = _parse_json_body(body)
        result = await jira.patch(path, body=parsed_body)
        return {"success": True, "data": result}
    except (JiraError, ValueError) as e:
        return {"success": False, "error": str(e), "status_code": getattr(e, "status_code", None)}
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool(
    description="Make a DELETE request to any JIRA API endpoint. "
    "Use this to remove resources."
)
async def jira_delete(
    path: Annotated[str, Field(description="API path (e.g., /rest/api/3/issue/PROJ-123)")],
) -> dict[str, Any]:
    """Make a DELETE request to any JIRA API endpoint."""
    try:
        result = await jira.delete(path)
        return {"success": True, "data": result}
    except JiraError as e:
        return {"success": False, "error": str(e), "status_code": e.status_code}
    except Exception as e:
        return {"success": False, "error": str(e)}
