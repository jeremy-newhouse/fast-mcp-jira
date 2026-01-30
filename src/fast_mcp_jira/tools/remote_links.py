"""Remote link tools for JIRA.

This module provides tools for managing remote links on JIRA issues.
Remote links are external URL references shown in the issue sidebar.

Tools:
- get_remote_links: List remote links on an issue
- add_remote_link: Create a remote link (e.g., to Confluence)
- delete_remote_link: Remove a remote link

Security Features:
- Issue keys are validated against JIRA format
- Link IDs are validated as numeric
- URLs are validated (http/https only)
- Response sanitization prevents XSS
"""

from typing import Annotated, Any

from pydantic import Field
from pydantic import ValidationError as PydanticValidationError

from ..logging_config import get_logger
from ..server import jira, mcp
from ..services.jira_client import JiraError
from ..utils.validation import (
    NumericIdInput,
    ValidationError,
    build_response,
    validate_issue_key,
    validate_remote_link_url,
)

logger = get_logger(__name__)


@mcp.tool(description="Get all remote links on a JIRA issue.")
async def get_remote_links(
    issue_key: Annotated[str, Field(description="Issue key (e.g., PROJ-123)")],
) -> dict[str, Any]:
    """Get list of remote links (external URLs) on an issue.

    Remote links appear in the issue sidebar and can link to external
    resources like Confluence pages, documentation, or other systems.
    """
    try:
        issue_key = validate_issue_key(issue_key)

        result = await jira.get(f"/rest/api/3/issue/{issue_key}/remotelink")

        # Handle both list response and empty response
        links_data = result if isinstance(result, list) else []

        remote_links = []
        for link in links_data:
            obj = link.get("object", {})
            app = link.get("application", {})
            icon = obj.get("icon", {})

            remote_links.append(
                {
                    "id": link.get("id"),
                    "global_id": link.get("globalId"),
                    "relationship": link.get("relationship"),
                    "url": obj.get("url"),
                    "title": obj.get("title"),
                    "summary": obj.get("summary"),
                    "icon_url": icon.get("url16x16"),
                    "icon_title": icon.get("title"),
                    "application_type": app.get("type"),
                    "application_name": app.get("name"),
                }
            )

        return build_response(
            True,
            issue_key=issue_key,
            total=len(remote_links),
            remote_links=remote_links,
        )
    except ValidationError as e:
        return build_response(False, error=str(e), field=e.field)
    except JiraError as e:
        return build_response(False, error=str(e), status_code=e.status_code)
    except Exception:
        logger.exception("Unexpected error getting remote links for %s", issue_key)
        return build_response(False, error="Internal error occurred")


@mcp.tool(description="Add a remote link to a JIRA issue.")
async def add_remote_link(
    issue_key: Annotated[str, Field(description="Issue key (e.g., PROJ-123)")],
    url: Annotated[str, Field(description="Target URL for the remote link")],
    title: Annotated[str, Field(description="Display title for the link")],
    relationship: Annotated[
        str | None,
        Field(description="Relationship label (e.g., 'Documentation', 'Design')"),
    ] = None,
    icon_url: Annotated[
        str | None,
        Field(description="URL for 16x16 icon (optional)"),
    ] = None,
    application_type: Annotated[
        str | None,
        Field(description="Application type (e.g., 'com.atlassian.confluence')"),
    ] = None,
    application_name: Annotated[
        str | None,
        Field(description="Application display name (e.g., 'Confluence')"),
    ] = None,
) -> dict[str, Any]:
    """Add a remote link to an issue.

    Remote links appear in the issue sidebar and can link to external resources.

    For Confluence pages, use:
    - application_type: "com.atlassian.confluence"
    - application_name: "Confluence"
    """
    try:
        issue_key = validate_issue_key(issue_key)
        url = validate_remote_link_url(url)

        # Validate title
        title = title.strip() if title else ""
        if not title:
            return build_response(False, error="Title cannot be empty", field="title")
        if len(title) > 255:
            return build_response(False, error="Title exceeds 255 character limit", field="title")

        # Build the request body
        body: dict[str, Any] = {
            "object": {
                "url": url,
                "title": title,
            }
        }

        # Add optional relationship
        if relationship:
            relationship = relationship.strip()
            if len(relationship) > 255:
                return build_response(
                    False,
                    error="Relationship exceeds 255 character limit",
                    field="relationship",
                )
            body["relationship"] = relationship

        # Add optional icon
        if icon_url:
            icon_url = validate_remote_link_url(icon_url)
            body["object"]["icon"] = {
                "url16x16": icon_url,
                "title": application_name or title,
            }

        # Add optional application info
        if application_type or application_name:
            body["application"] = {}
            if application_type:
                body["application"]["type"] = application_type.strip()
            if application_name:
                body["application"]["name"] = application_name.strip()

        result = await jira.post(f"/rest/api/3/issue/{issue_key}/remotelink", body=body)

        return build_response(
            True,
            issue_key=issue_key,
            remote_link_id=result.get("id"),
            url=url,
            title=title,
        )
    except ValidationError as e:
        return build_response(False, error=str(e), field=e.field)
    except PydanticValidationError as e:
        return build_response(False, error=str(e.errors()[0]["msg"]), field="url")
    except JiraError as e:
        return build_response(False, error=str(e), status_code=e.status_code)
    except Exception:
        logger.exception("Unexpected error adding remote link to %s", issue_key)
        return build_response(False, error="Internal error occurred")


@mcp.tool(description="Delete a remote link from a JIRA issue.")
async def delete_remote_link(
    issue_key: Annotated[str, Field(description="Issue key (e.g., PROJ-123)")],
    link_id: Annotated[str, Field(description="Remote link ID to delete")],
) -> dict[str, Any]:
    """Delete a remote link from an issue."""
    try:
        issue_key = validate_issue_key(issue_key)

        # Validate link_id is numeric
        validated_id = NumericIdInput(id=link_id)

        await jira.delete(f"/rest/api/3/issue/{issue_key}/remotelink/{validated_id.id}")

        return build_response(
            True,
            issue_key=issue_key,
            deleted_link_id=validated_id.id,
        )
    except ValidationError as e:
        return build_response(False, error=str(e), field=e.field)
    except PydanticValidationError as e:
        return build_response(False, error=str(e.errors()[0]["msg"]), field="link_id")
    except JiraError as e:
        return build_response(False, error=str(e), status_code=e.status_code)
    except Exception:
        logger.exception("Unexpected error deleting remote link %s from %s", link_id, issue_key)
        return build_response(False, error="Internal error occurred")
