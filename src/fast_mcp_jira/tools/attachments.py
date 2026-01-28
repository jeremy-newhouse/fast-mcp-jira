"""Attachment tools for JIRA issues."""

from typing import Annotated, Any

from pydantic import Field

from ..server import jira, mcp
from ..services.jira_client import JiraError


@mcp.tool(description="Get list of attachments on a JIRA issue.")
async def get_attachments(
    issue_key: Annotated[str, Field(description="Issue key (e.g., PROJ-123)")],
) -> dict[str, Any]:
    """Get all attachments for an issue."""
    try:
        result = await jira.get(
            f"/rest/api/3/issue/{issue_key}",
            params={"fields": "attachment"},
        )
        attachments = result.get("fields", {}).get("attachment", [])
        return {
            "success": True,
            "issue_key": issue_key,
            "count": len(attachments),
            "attachments": [
                {
                    "id": a.get("id"),
                    "filename": a.get("filename"),
                    "size": a.get("size"),
                    "mime_type": a.get("mimeType"),
                    "content_url": a.get("content"),
                    "author": a.get("author", {}).get("displayName"),
                    "created": a.get("created"),
                }
                for a in attachments
            ],
        }
    except JiraError as e:
        return {"success": False, "error": str(e), "status_code": e.status_code}
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool(description="Get metadata for a specific attachment by ID.")
async def get_attachment(
    attachment_id: Annotated[str, Field(description="Attachment ID")],
) -> dict[str, Any]:
    """Get attachment metadata by ID."""
    try:
        result = await jira.get(f"/rest/api/3/attachment/{attachment_id}")
        return {
            "success": True,
            "attachment": {
                "id": result.get("id"),
                "filename": result.get("filename"),
                "size": result.get("size"),
                "mime_type": result.get("mimeType"),
                "content_url": result.get("content"),
                "author": result.get("author", {}).get("displayName"),
                "created": result.get("created"),
            },
        }
    except JiraError as e:
        return {"success": False, "error": str(e), "status_code": e.status_code}
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool(description="Delete an attachment from JIRA.")
async def delete_attachment(
    attachment_id: Annotated[str, Field(description="Attachment ID to delete")],
) -> dict[str, Any]:
    """Delete an attachment by ID."""
    try:
        await jira.delete(f"/rest/api/3/attachment/{attachment_id}")
        return {
            "success": True,
            "deleted_attachment_id": attachment_id,
        }
    except JiraError as e:
        return {"success": False, "error": str(e), "status_code": e.status_code}
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool(description="Add an attachment to a JIRA issue.")
async def add_attachment(
    issue_key: Annotated[str, Field(description="Issue key (e.g., PROJ-123)")],
    filename: Annotated[str, Field(description="Name of the file to attach")],
    content_base64: Annotated[str, Field(description="Base64-encoded file content")],
    content_type: Annotated[
        str, Field(description="MIME type of the file (e.g., 'text/plain', 'image/png')")
    ] = "application/octet-stream",
) -> dict[str, Any]:
    """Add an attachment to an issue.

    The file content must be provided as a base64-encoded string.
    """
    import base64 as b64

    try:
        content = b64.b64decode(content_base64)
        result = await jira.post_multipart(
            f"/rest/api/3/issue/{issue_key}/attachments",
            filename=filename,
            content=content,
            content_type=content_type,
        )

        # Result is a list of created attachments
        attachments = result if isinstance(result, list) else [result]
        return {
            "success": True,
            "issue_key": issue_key,
            "attachments": [
                {
                    "id": a.get("id"),
                    "filename": a.get("filename"),
                    "size": a.get("size"),
                    "mime_type": a.get("mimeType"),
                }
                for a in attachments
            ],
        }
    except JiraError as e:
        return {"success": False, "error": str(e), "status_code": e.status_code}
    except Exception as e:
        return {"success": False, "error": str(e)}
