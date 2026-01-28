"""Dynamic custom field tools for JIRA.

This module provides dynamic tool registration for custom JIRA fields.
Fields are configured via JSON file and generate get_<name> and set_<name>
MCP tools at server startup.

Configuration is loaded from ~/.fast-mcp-jira/custom-fields.json when
CUSTOM_FIELDS_ENABLED=true is set in the environment.

Example config:
    {
        "custom_fields": [
            {
                "id": "customfield_10300",
                "name": "acceptance_criteria",
                "type": "rich_text",
                "label": "Acceptance Criteria",
                "description": "Acceptance criteria (supports markdown)",
                "enabled": true
            }
        ]
    }

Security Features:
- Issue keys are validated against JIRA format
- Field values are validated based on field type
- Rich text fields use ADF conversion (markdown support)
"""

from typing import Annotated, Any

from fastmcp import FastMCP
from pydantic import Field

from ..config import CustomFieldConfig, FieldType
from ..logging_config import get_logger
from ..services.jira_client import JiraClient, JiraError
from ..utils.adf import adf_to_markdown, markdown_to_adf
from ..utils.validation import ValidationError, build_response, validate_issue_key

logger = get_logger(__name__)


def _convert_value_to_jira(value: Any, field_type: FieldType) -> Any:
    """Convert a tool input value to JIRA API format.

    Args:
        value: The input value from the tool.
        field_type: The type of the custom field.

    Returns:
        Value formatted for JIRA API.
    """
    if field_type == "rich_text":
        # Convert markdown to ADF
        return markdown_to_adf(value) if value else None

    if field_type == "select":
        # Single select needs {"value": "..."} format
        return {"value": value} if value else None

    if field_type == "multi_select":
        # Multi-select needs [{"value": "..."}, ...] format
        return [{"value": v} for v in value] if value else []

    if field_type == "user_picker":
        # User picker needs {"accountId": "..."} format
        return {"accountId": value} if value else None

    if field_type == "checkbox":
        # Some JIRA checkbox fields use [{"value": "Yes/No"}]
        # Others use simple array, return the boolean for now
        return value

    # text, number, date, datetime - pass through
    return value


def _convert_value_from_jira(value: Any, field_type: FieldType) -> Any:
    """Convert a JIRA API value to a user-friendly format.

    Args:
        value: The value from JIRA API.
        field_type: The type of the custom field.

    Returns:
        Value formatted for user consumption.
    """
    if value is None:
        return None

    if field_type == "rich_text":
        # Convert ADF to markdown
        if isinstance(value, dict):
            return adf_to_markdown(value)
        return value

    if field_type == "select":
        # Extract value from {"value": "...", "id": "..."}
        if isinstance(value, dict):
            return value.get("value")
        return value

    if field_type == "multi_select":
        # Extract values from [{"value": "..."}, ...]
        if isinstance(value, list):
            return [v.get("value") if isinstance(v, dict) else v for v in value]
        return value

    if field_type == "user_picker":
        # Extract display name or account ID
        if isinstance(value, dict):
            return value.get("displayName") or value.get("accountId")
        return value

    # text, number, date, datetime, checkbox - pass through
    return value


def register_custom_field_tools(
    mcp: FastMCP,
    jira: JiraClient,
    fields: list[CustomFieldConfig],
) -> int:
    """Register get/set tools for each enabled custom field.

    Creates MCP tools dynamically based on field configuration:
    - get_<field_name>: Get field value for an issue
    - set_<field_name>: Set field value for an issue (unless read_only)

    Args:
        mcp: FastMCP server instance.
        jira: JIRA client instance.
        fields: List of custom field configurations.

    Returns:
        Number of tools registered.
    """
    count = 0

    for field in fields:
        if not field.enabled:
            continue

        # Register getter
        _register_getter(mcp, jira, field)
        count += 1

        # Register setter (unless read-only)
        if not field.read_only:
            _register_setter(mcp, jira, field)
            count += 1

    if count > 0:
        logger.info(
            "Custom field tools registered",
            extra={
                "tool_count": count,
                "fields": [f.name for f in fields if f.enabled],
            },
        )

    return count


def _register_getter(mcp: FastMCP, jira: JiraClient, field: CustomFieldConfig) -> None:
    """Register a getter tool for a custom field."""
    tool_name = f"get_{field.name}"

    async def get_field_value(
        issue_key: Annotated[str, Field(description="Issue key (e.g., PROJ-123)")],
    ) -> dict[str, Any]:
        try:
            validated_key = validate_issue_key(issue_key)

            result = await jira.get(
                f"/rest/api/3/issue/{validated_key}",
                params={"fields": field.id},
            )

            raw_value = result.get("fields", {}).get(field.id)
            converted_value = _convert_value_from_jira(raw_value, field.type)

            return build_response(
                True,
                issue_key=validated_key,
                field_id=field.id,
                field_name=field.name,
                value=converted_value,
            )
        except ValidationError as e:
            return build_response(False, error=str(e), field=e.field)
        except JiraError as e:
            return build_response(False, error=str(e), status_code=e.status_code)
        except Exception:
            logger.exception("Error getting custom field %s for %s", field.name, issue_key)
            return build_response(False, error="Internal error occurred")

    # Set function name for better debugging
    get_field_value.__name__ = tool_name
    get_field_value.__doc__ = f"Get {field.label} for a JIRA issue."

    # Register with MCP
    mcp.tool(name=tool_name, description=f"Get {field.label} for a JIRA issue")(get_field_value)


def _register_setter(mcp: FastMCP, jira: JiraClient, field: CustomFieldConfig) -> None:
    """Register a setter tool for a custom field."""
    tool_name = f"set_{field.name}"

    # Build description with options if available
    description = f"Set {field.label} for a JIRA issue"
    if field.options:
        description += f". Valid options: {', '.join(field.options)}"
    if field.type == "rich_text":
        description += ". Supports markdown formatting."

    async def set_field_value(
        issue_key: Annotated[str, Field(description="Issue key (e.g., PROJ-123)")],
        value: Annotated[Any, Field(description=field.description)],
    ) -> dict[str, Any]:
        try:
            validated_key = validate_issue_key(issue_key)

            # Validate options for select fields
            if field.options and field.type in ("select", "multi_select"):
                values_to_check = [value] if field.type == "select" else value
                invalid = [v for v in values_to_check if v not in field.options]
                if invalid:
                    return build_response(
                        False,
                        error=f"Invalid option(s): {invalid}. Valid: {field.options}",
                        field="value",
                    )

            # Convert to JIRA format
            jira_value = _convert_value_to_jira(value, field.type)

            await jira.put(
                f"/rest/api/3/issue/{validated_key}",
                body={"fields": {field.id: jira_value}},
            )

            return build_response(
                True,
                issue_key=validated_key,
                field_id=field.id,
                field_name=field.name,
                updated=True,
            )
        except ValidationError as e:
            return build_response(False, error=str(e), field=e.field)
        except JiraError as e:
            return build_response(False, error=str(e), status_code=e.status_code)
        except Exception:
            logger.exception("Error setting custom field %s for %s", field.name, issue_key)
            return build_response(False, error="Internal error occurred")

    # Set function name for better debugging
    set_field_value.__name__ = tool_name
    set_field_value.__doc__ = f"Set {field.label} for a JIRA issue."

    # Register with MCP
    mcp.tool(name=tool_name, description=description)(set_field_value)
