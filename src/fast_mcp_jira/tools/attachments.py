"""Attachment tools for JIRA issues.

This module provides tools for managing file attachments on JIRA issues:
- get_attachments: List all attachments on an issue
- get_attachment: Get metadata for a specific attachment
- delete_attachment: Remove an attachment
- add_attachment: Upload a new attachment

Security Features:
- Filename validation prevents path traversal attacks
- Dangerous file extensions (.exe, .bat, etc.) are blocked
- Base64 content size is limited to ~50MB
- Attachment IDs are validated as numeric only
- Response sanitization prevents XSS
"""

import base64 as b64
from typing import Annotated, Any

from pydantic import Field
from pydantic import ValidationError as PydanticValidationError

from ..logging_config import get_logger
from ..server import jira, mcp
from ..services.jira_client import JiraError
from ..utils.validation import (
    AttachmentInput,
    NumericIdInput,
    ValidationError,
    build_response,
    validate_issue_key,
)

logger = get_logger(__name__)


@mcp.tool(description="Get list of attachments on a JIRA issue.")
async def get_attachments(
    issue_key: Annotated[str, Field(description="Issue key (e.g., PROJ-123)")],
) -> dict[str, Any]:
    """Get all attachments for a JIRA issue.

    Retrieves metadata for all files attached to the specified issue,
    including filename, size, MIME type, and download URL.

    Args:
        issue_key: The JIRA issue key (e.g., "PROJ-123"). Case-insensitive.

    Returns:
        dict containing:
            - success (bool): Whether the operation succeeded
            - issue_key (str): The normalized issue key
            - count (int): Number of attachments found
            - attachments (list): List of attachment metadata dicts with:
                - id: Attachment ID for use with other attachment tools
                - filename: Original filename
                - size: File size in bytes
                - mime_type: MIME type of the file
                - content_url: URL to download the file content
                - author: Display name of uploader
                - created: ISO timestamp of upload

    Example:
        >>> await get_attachments(issue_key="PROJ-123")
        {
            "success": True,
            "issue_key": "PROJ-123",
            "count": 2,
            "attachments": [
                {"id": "10001", "filename": "screenshot.png", ...},
                {"id": "10002", "filename": "logs.txt", ...}
            ]
        }
    """
    try:
        # Validate issue key format
        validated_key = validate_issue_key(issue_key)

        result = await jira.get(
            f"/rest/api/3/issue/{validated_key}",
            params={"fields": "attachment"},
        )
        attachments = result.get("fields", {}).get("attachment", [])
        return build_response(
            True,
            issue_key=validated_key,
            count=len(attachments),
            attachments=[
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
        )
    except ValidationError as e:
        return build_response(False, error=str(e), field=e.field)
    except JiraError as e:
        return build_response(False, error=str(e), status_code=e.status_code)
    except Exception:
        logger.exception("Unexpected error getting attachments for %s", issue_key)
        return build_response(False, error="Internal error occurred")


@mcp.tool(description="Get metadata for a specific attachment by ID.")
async def get_attachment(
    attachment_id: Annotated[str, Field(description="Attachment ID")],
) -> dict[str, Any]:
    """Get detailed metadata for a specific attachment.

    Retrieves full metadata for a single attachment by its ID.
    Use get_attachments first to find attachment IDs.

    Args:
        attachment_id: Numeric attachment ID (e.g., "10001").

    Returns:
        dict containing:
            - success (bool): Whether the operation succeeded
            - attachment (dict): Attachment metadata with:
                - id: Attachment ID
                - filename: Original filename
                - size: File size in bytes
                - mime_type: MIME type
                - content_url: Download URL
                - author: Uploader's display name
                - created: Upload timestamp

    Example:
        >>> await get_attachment(attachment_id="10001")
        {
            "success": True,
            "attachment": {
                "id": "10001",
                "filename": "screenshot.png",
                "size": 45678,
                "mime_type": "image/png",
                ...
            }
        }
    """
    try:
        # Validate attachment ID is numeric
        validated = NumericIdInput(id=attachment_id)

        result = await jira.get(f"/rest/api/3/attachment/{validated.id}")
        return build_response(
            True,
            attachment={
                "id": result.get("id"),
                "filename": result.get("filename"),
                "size": result.get("size"),
                "mime_type": result.get("mimeType"),
                "content_url": result.get("content"),
                "author": result.get("author", {}).get("displayName"),
                "created": result.get("created"),
            },
        )
    except PydanticValidationError as e:
        return build_response(False, error=str(e.errors()[0]["msg"]), field="attachment_id")
    except JiraError as e:
        return build_response(False, error=str(e), status_code=e.status_code)
    except Exception:
        logger.exception("Unexpected error getting attachment %s", attachment_id)
        return build_response(False, error="Internal error occurred")


@mcp.tool(description="Delete an attachment from JIRA.")
async def delete_attachment(
    attachment_id: Annotated[str, Field(description="Attachment ID to delete")],
) -> dict[str, Any]:
    """Delete an attachment from JIRA.

    Permanently removes an attachment. This action cannot be undone.
    Requires appropriate permissions on the issue.

    Args:
        attachment_id: Numeric attachment ID to delete (e.g., "10001").

    Returns:
        dict containing:
            - success (bool): Whether deletion succeeded
            - deleted_attachment_id (str): ID of deleted attachment

    Example:
        >>> await delete_attachment(attachment_id="10001")
        {"success": True, "deleted_attachment_id": "10001"}
    """
    try:
        # Validate attachment ID is numeric
        validated = NumericIdInput(id=attachment_id)

        await jira.delete(f"/rest/api/3/attachment/{validated.id}")
        return build_response(
            True,
            deleted_attachment_id=validated.id,
        )
    except PydanticValidationError as e:
        return build_response(False, error=str(e.errors()[0]["msg"]), field="attachment_id")
    except JiraError as e:
        return build_response(False, error=str(e), status_code=e.status_code)
    except Exception:
        logger.exception("Unexpected error deleting attachment %s", attachment_id)
        return build_response(False, error="Internal error occurred")


@mcp.tool(description="Add an attachment to a JIRA issue.")
async def add_attachment(
    issue_key: Annotated[str, Field(description="Issue key (e.g., PROJ-123)")],
    filename: Annotated[str, Field(description="Name of the file to attach")],
    content_base64: Annotated[str, Field(description="Base64-encoded file content")],
    content_type: Annotated[
        str, Field(description="MIME type of the file (e.g., 'text/plain', 'image/png')")
    ] = "application/octet-stream",
) -> dict[str, Any]:
    """Upload an attachment to a JIRA issue.

    Adds a file attachment to the specified issue. The file content must
    be provided as a base64-encoded string.

    Security restrictions:
    - Filenames cannot contain path separators (/, \\) or traversal (..)
    - Dangerous extensions are blocked: .exe, .bat, .cmd, .sh, .ps1, .dll, .so
    - Maximum file size is approximately 50MB

    Args:
        issue_key: Target issue key (e.g., "PROJ-123"). Case-insensitive.
        filename: Name for the attached file (e.g., "report.pdf").
            Must be a simple filename without path components.
        content_base64: File content encoded as base64 string.
        content_type: MIME type for the file. Defaults to
            "application/octet-stream" if not specified.

    Returns:
        dict containing:
            - success (bool): Whether upload succeeded
            - issue_key (str): The normalized issue key
            - attachments (list): Created attachment(s) with id, filename,
              size, and mime_type

    Example:
        >>> import base64
        >>> content = base64.b64encode(b"Hello World").decode()
        >>> await add_attachment(
        ...     issue_key="PROJ-123",
        ...     filename="hello.txt",
        ...     content_base64=content,
        ...     content_type="text/plain"
        ... )
        {
            "success": True,
            "issue_key": "PROJ-123",
            "attachments": [{"id": "10003", "filename": "hello.txt", ...}]
        }
    """
    try:
        # Validate issue key
        validated_key = validate_issue_key(issue_key)

        # Validate attachment input (filename, size, content_type)
        validated_attachment = AttachmentInput(
            filename=filename,
            content_base64=content_base64,
            content_type=content_type,
        )

        # Decode base64 content
        content = b64.b64decode(validated_attachment.content_base64)

        result = await jira.post_multipart(
            f"/rest/api/3/issue/{validated_key}/attachments",
            filename=validated_attachment.filename,
            content=content,
            content_type=validated_attachment.content_type,
        )

        # Result is a list of created attachments
        attachments = result if isinstance(result, list) else [result]
        return build_response(
            True,
            issue_key=validated_key,
            attachments=[
                {
                    "id": a.get("id"),
                    "filename": a.get("filename"),
                    "size": a.get("size"),
                    "mime_type": a.get("mimeType"),
                }
                for a in attachments
            ],
        )
    except ValidationError as e:
        return build_response(False, error=str(e), field=e.field)
    except PydanticValidationError as e:
        # Extract field name and message from Pydantic error
        err = e.errors()[0]
        field = err.get("loc", ["unknown"])[0]
        msg = err.get("msg", str(e))
        return build_response(False, error=msg, field=str(field))
    except JiraError as e:
        return build_response(False, error=str(e), status_code=e.status_code)
    except Exception:
        logger.exception("Unexpected error adding attachment to %s", issue_key)
        return build_response(False, error="Internal error occurred")
