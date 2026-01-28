"""Issue link tools for JIRA.

This module provides tools for managing links between JIRA issues:
- get_link_types: List available link types (Blocks, Duplicates, etc.)
- create_link: Create a link between two issues
- delete_link: Remove an issue link

Security Features:
- Issue keys are validated against JIRA format
- Link IDs are validated as numeric
- Link type names are validated
- Response sanitization prevents XSS

Caching:
- Link types are cached for 24 hours (rarely change)
"""

from typing import Annotated, Any

from pydantic import Field
from pydantic import ValidationError as PydanticValidationError

from ..logging_config import get_logger
from ..server import cache, jira, mcp
from ..services.cache import CacheService
from ..services.jira_client import JiraError
from ..utils.validation import (
    LinkTypeInput,
    NumericIdInput,
    ValidationError,
    build_response,
    validate_issue_key,
)

logger = get_logger(__name__)


@mcp.tool(description="Get all issue link types available in JIRA.")
async def get_link_types() -> dict[str, Any]:
    """Get list of all issue link types (e.g., blocks, duplicates, relates to).

    Results are cached for 24 hours. Use invalidate_cache to force refresh.
    """
    cache_key = CacheService.make_key("link_types")

    # Try cache first
    if cache:
        cached = await cache.get(cache_key, "link_types")
        if cached:
            cached["_cached"] = True
            return cached

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

        response = build_response(
            True,
            total=len(link_types),
            link_types=link_types,
        )

        # Cache the response
        if cache:
            await cache.set(cache_key, "link_types", response)

        return response
    except JiraError as e:
        return build_response(False, error=str(e), status_code=e.status_code)
    except Exception:
        logger.exception("Unexpected error getting link types")
        return build_response(False, error="Internal error occurred")


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
        # Validate issue keys
        inward_issue = validate_issue_key(inward_issue)
        outward_issue = validate_issue_key(outward_issue)

        # Validate link type
        validated_link_type = LinkTypeInput(link_type=link_type)

        body = {
            "type": {"name": validated_link_type.link_type},
            "inwardIssue": {"key": inward_issue},
            "outwardIssue": {"key": outward_issue},
        }
        await jira.post("/rest/api/3/issueLink", body=body)
        return build_response(
            True,
            inward_issue=inward_issue,
            outward_issue=outward_issue,
            link_type=validated_link_type.link_type,
        )
    except ValidationError as e:
        return build_response(False, error=str(e), field=e.field)
    except PydanticValidationError as e:
        return build_response(False, error=str(e.errors()[0]["msg"]), field="link_type")
    except JiraError as e:
        return build_response(False, error=str(e), status_code=e.status_code)
    except Exception:
        logger.exception(
            "Unexpected error creating link between %s and %s", inward_issue, outward_issue
        )
        return build_response(False, error="Internal error occurred")


@mcp.tool(description="Delete an issue link by its ID.")
async def delete_link(
    link_id: Annotated[str, Field(description="Issue link ID to delete")],
) -> dict[str, Any]:
    """Delete an issue link."""
    try:
        # Validate link_id is numeric
        validated_id = NumericIdInput(id=link_id)

        await jira.delete(f"/rest/api/3/issueLink/{validated_id.id}")
        return build_response(
            True,
            deleted_link_id=validated_id.id,
        )
    except PydanticValidationError as e:
        return build_response(False, error=str(e.errors()[0]["msg"]), field="link_id")
    except JiraError as e:
        return build_response(False, error=str(e), status_code=e.status_code)
    except Exception:
        logger.exception("Unexpected error deleting link %s", link_id)
        return build_response(False, error="Internal error occurred")
