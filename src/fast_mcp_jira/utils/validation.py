"""Input validation utilities for JIRA API parameters.

This module provides two validation approaches:
1. Pydantic models (IssueKeyInput, AttachmentInput, etc.) for type-safe validation
2. Standalone functions (validate_issue_key, etc.) for backward compatibility

Security Features:
- Path traversal prevention in filenames
- Dangerous file extension blocking
- JQL injection pattern detection
- Input length limits to prevent DoS
- Account ID format validation
"""

import re
from typing import Any

import bleach
from pydantic import BaseModel, ConfigDict, Field, field_validator

# =============================================================================
# XSS Sanitization Configuration (using bleach allowlist approach)
# =============================================================================

# Safe HTML tags that are allowed in responses
ALLOWED_HTML_TAGS = [
    "p",
    "br",
    "b",
    "i",
    "u",
    "strong",
    "em",
    "a",
    "ul",
    "ol",
    "li",
    "code",
    "pre",
    "blockquote",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "span",
    "div",
]

# Safe attributes for allowed tags
ALLOWED_HTML_ATTRIBUTES = {
    "a": ["href", "title"],
    "span": ["class"],
    "div": ["class"],
    "code": ["class"],
    "pre": ["class"],
}

# Safe URL protocols
ALLOWED_PROTOCOLS = ["http", "https", "mailto"]

# =============================================================================
# Pydantic Validation Models
# =============================================================================


class IssueKeyInput(BaseModel):
    """Validated JIRA issue key input.

    Validates that issue keys match the JIRA format: PROJECT-123
    where PROJECT is uppercase letters/numbers/underscores starting with a letter.

    Example:
        >>> validated = IssueKeyInput(issue_key="proj-123")
        >>> validated.issue_key
        'PROJ-123'
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    issue_key: str = Field(..., description="Issue key (e.g., PROJ-123)")

    @field_validator("issue_key")
    @classmethod
    def validate_format(cls, v: str) -> str:
        """Validate and normalize issue key format."""
        v = v.strip().upper()
        if not re.match(r"^[A-Z][A-Z0-9_]+-\d+$", v):
            raise ValueError(f"Invalid issue key format '{v}'. Expected: PROJECT-123")
        return v


class ProjectKeyInput(BaseModel):
    """Validated JIRA project key input.

    Validates that project keys are uppercase letters/numbers/underscores
    starting with a letter, max 10 characters.

    Example:
        >>> validated = ProjectKeyInput(project_key="myproj")
        >>> validated.project_key
        'MYPROJ'
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    project_key: str = Field(..., max_length=10, description="Project key (e.g., PROJ)")

    @field_validator("project_key")
    @classmethod
    def validate_format(cls, v: str) -> str:
        """Validate and normalize project key format."""
        v = v.strip().upper()
        if not re.match(r"^[A-Z][A-Z0-9_]*$", v):
            raise ValueError(
                f"Invalid project key '{v}'. Must start with letter, "
                "contain only letters/numbers/underscores"
            )
        return v


class AttachmentInput(BaseModel):
    """Validated attachment input with security checks.

    Security features:
    - Filename path traversal prevention (blocks .., /, \\)
    - Dangerous extension blocking (.exe, .bat, .cmd, .sh, .ps1, .dll, .so)
    - Size limit of ~50MB for base64 content

    Example:
        >>> att = AttachmentInput(
        ...     filename="report.pdf",
        ...     content_base64="SGVsbG8gV29ybGQ="
        ... )
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    filename: str = Field(..., max_length=255, description="Attachment filename")
    content_base64: str = Field(
        ...,
        max_length=70_000_000,  # ~50MB after base64 encoding
        description="Base64-encoded file content",
    )
    content_type: str = Field(
        default="application/octet-stream",
        description="MIME type (e.g., 'text/plain', 'image/png')",
    )

    @field_validator("filename")
    @classmethod
    def validate_filename(cls, v: str) -> str:
        """Prevent path traversal and dangerous extensions."""
        v = v.strip()
        # Block path traversal attempts
        if ".." in v or "/" in v or "\\" in v:
            raise ValueError("Filename contains invalid path characters")
        # Block null bytes
        if "\x00" in v:
            raise ValueError("Filename contains invalid characters")
        # Block hidden/dotfiles (e.g., .bashrc, .env, .gitignore)
        if v.startswith("."):
            raise ValueError("Hidden files (starting with dot) are not allowed")
        # Block dangerous extensions
        dangerous_extensions = {".exe", ".bat", ".cmd", ".sh", ".ps1", ".dll", ".so"}
        ext = ("." + v.rsplit(".", 1)[-1].lower()) if "." in v else ""
        if ext in dangerous_extensions:
            raise ValueError(f"File type {ext} is not allowed for security reasons")
        # Validate characters (alphanumeric, dots, hyphens, underscores, spaces)
        if not re.match(r"^[\w\-. ]+$", v):
            raise ValueError("Filename contains invalid characters")
        return v


class JqlInput(BaseModel):
    """Validated JQL query input with injection prevention.

    Security features:
    - Maximum length of 10,000 characters
    - Blocks SQL-like injection patterns (;, --, /*, */)

    Example:
        >>> query = JqlInput(jql="project = PROJ AND status = 'Open'")
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    jql: str = Field(..., max_length=10000, description="JQL query string")

    @field_validator("jql")
    @classmethod
    def validate_jql(cls, v: str) -> str:
        """Check for potential injection patterns."""
        v = v.strip()
        # Check for SQL-like injection patterns
        # Block semicolons anywhere (not just at end) to prevent statement chaining
        dangerous_patterns = [r";", r"--", r"/\*", r"\*/"]
        v_lower = v.lower()
        for pattern in dangerous_patterns:
            if re.search(pattern, v_lower):
                raise ValueError("JQL contains potentially dangerous characters")
        return v


class NumericIdInput(BaseModel):
    """Validated numeric ID input.

    Used for attachment IDs, comment IDs, worklog IDs, link IDs, etc.

    Example:
        >>> id_input = NumericIdInput(id="12345")
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    id: str = Field(..., description="Numeric ID")

    @field_validator("id")
    @classmethod
    def validate_numeric(cls, v: str) -> str:
        """Ensure ID is purely numeric."""
        v = v.strip()
        if not v.isdigit():
            raise ValueError("ID must be numeric")
        return v


class AccountIdInput(BaseModel):
    """Validated JIRA account ID input.

    Account IDs are typically in format: 712020:uuid or 5xxxxxxxxxxxxx

    Example:
        >>> account = AccountIdInput(account_id="712020:abc-def-123")
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    account_id: str = Field(..., min_length=10, max_length=128, description="JIRA account ID")

    @field_validator("account_id")
    @classmethod
    def validate_format(cls, v: str) -> str:
        """Validate account ID format."""
        v = v.strip()
        # Allow alphanumeric, colons, hyphens, underscores
        if not re.match(r"^[a-zA-Z0-9:_-]+$", v):
            raise ValueError("Account ID contains invalid characters")
        return v


class CommentInput(BaseModel):
    """Validated comment body input.

    Supports markdown formatting. Maximum 32,767 characters (JIRA limit).

    Example:
        >>> comment = CommentInput(body="This is a **bold** comment")
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    body: str = Field(
        ...,
        max_length=32767,
        description="Comment text with markdown support",
    )

    @field_validator("body")
    @classmethod
    def validate_not_empty(cls, v: str) -> str:
        """Ensure comment is not empty."""
        if not v.strip():
            raise ValueError("Comment body cannot be empty")
        return v


class LabelListInput(BaseModel):
    """Validated list of issue labels.

    Labels can only contain letters, numbers, underscores, and hyphens.

    Example:
        >>> labels = LabelListInput(labels=["backend", "high-priority"])
    """

    labels: list[str] = Field(default_factory=list, description="List of labels")

    @field_validator("labels")
    @classmethod
    def validate_labels(cls, v: list[str]) -> list[str]:
        """Validate each label format."""
        validated = []
        for i, label in enumerate(v):
            label = label.strip()
            if not label:
                continue
            if len(label) > 255:
                raise ValueError(f"Label {i} exceeds 255 character limit")
            if not re.match(r"^[a-zA-Z0-9_-]+$", label):
                raise ValueError(
                    f"Label '{label}' contains invalid characters. "
                    "Use only letters, numbers, underscores, hyphens"
                )
            validated.append(label)
        return validated


class TimeSpentInput(BaseModel):
    """Validated JIRA time spent format.

    JIRA accepts formats like: 2h, 30m, 1d, 2h 30m, 1w 2d 3h

    Example:
        >>> time = TimeSpentInput(time_spent="2h 30m")
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    time_spent: str = Field(..., max_length=50, description="Time in JIRA format (e.g., 2h 30m)")

    @field_validator("time_spent")
    @classmethod
    def validate_format(cls, v: str) -> str:
        """Validate time spent format."""
        v = v.strip()
        # JIRA time format: combinations of weeks, days, hours, minutes
        # e.g., "1w", "2d", "3h", "30m", "1w 2d 3h 30m", "2h30m"
        if not re.match(r"^(\d+[wdhm]\s*)+$", v.lower()):
            raise ValueError(
                f"Invalid time format '{v}'. Use JIRA format like '2h', '30m', '1d 2h 30m'"
            )
        return v


class TransitionNameInput(BaseModel):
    """Validated workflow transition name.

    Example:
        >>> transition = TransitionNameInput(name="In Progress")
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(..., max_length=255, description="Transition name")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate transition name."""
        v = v.strip()
        if not v:
            raise ValueError("Transition name cannot be empty")
        # Allow alphanumeric, spaces, hyphens, underscores
        if not re.match(r"^[\w\s\-]+$", v):
            raise ValueError("Transition name contains invalid characters")
        return v


class LinkTypeInput(BaseModel):
    """Validated issue link type name.

    Example:
        >>> link = LinkTypeInput(link_type="Blocks")
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    link_type: str = Field(..., max_length=255, description="Link type name")

    @field_validator("link_type")
    @classmethod
    def validate_link_type(cls, v: str) -> str:
        """Validate link type name."""
        v = v.strip()
        if not v:
            raise ValueError("Link type cannot be empty")
        # Allow alphanumeric, spaces, hyphens
        if not re.match(r"^[\w\s\-]+$", v):
            raise ValueError("Link type contains invalid characters")
        return v


class FieldListInput(BaseModel):
    """Validated comma-separated field list.

    Example:
        >>> fields = FieldListInput(fields="summary,status,assignee")
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    fields: str = Field(..., max_length=1000, description="Comma-separated field names")

    @field_validator("fields")
    @classmethod
    def validate_fields(cls, v: str) -> str:
        """Validate field list format."""
        v = v.strip()
        if not v:
            return v
        # Each field should be alphanumeric with underscores (for custom fields)
        for field in v.split(","):
            field = field.strip()
            if field and not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", field):
                raise ValueError(f"Invalid field name: '{field}'")
        return v


class SprintNameInput(BaseModel):
    """Validated sprint name.

    Example:
        >>> sprint = SprintNameInput(name="Sprint 1")
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(..., max_length=30, description="Sprint name (max 30 chars)")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate sprint name."""
        v = v.strip()
        if not v:
            raise ValueError("Sprint name cannot be empty")
        return v


class SprintGoalInput(BaseModel):
    """Validated sprint goal.

    Example:
        >>> goal = SprintGoalInput(goal="Complete authentication feature")
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    goal: str = Field(..., max_length=1000, description="Sprint goal")


# Allowed fields for bulk updates (security: prevent updating sensitive fields)
ALLOWED_BULK_UPDATE_FIELDS = {
    "summary",
    "description",
    "priority",
    "labels",
    "assignee",
    "reporter",
    "components",
    "fixVersions",
    "versions",
    "duedate",
    "environment",
    # Custom fields are allowed if they start with customfield_
}


class BulkUpdateFieldsInput(BaseModel):
    """Validated bulk update fields.

    Only allows updates to safe, known fields.

    Example:
        >>> updates = BulkUpdateFieldsInput(
        ...     updates={"priority": {"name": "High"}, "labels": ["urgent"]}
        ... )
    """

    updates: dict[str, Any] = Field(..., description="Field updates")

    @field_validator("updates")
    @classmethod
    def validate_fields(cls, v: dict[str, Any]) -> dict[str, Any]:
        """Validate that only allowed fields are being updated."""
        if not v:
            raise ValueError("No updates provided")

        for field_name in v.keys():
            # Allow known safe fields
            if field_name in ALLOWED_BULK_UPDATE_FIELDS:
                continue
            # Allow custom fields
            if field_name.startswith("customfield_"):
                # Validate custom field ID format
                if not re.match(r"^customfield_\d+$", field_name):
                    raise ValueError(f"Invalid custom field format: '{field_name}'")
                continue
            raise ValueError(
                f"Field '{field_name}' is not allowed in bulk updates. "
                f"Allowed fields: {', '.join(sorted(ALLOWED_BULK_UPDATE_FIELDS))}"
            )
        return v


# =============================================================================
# Legacy Validation Functions (for backward compatibility)
# =============================================================================


class ValidationError(Exception):
    """Raised when input validation fails."""

    def __init__(self, field: str, message: str):
        self.field = field
        self.message = message
        super().__init__(f"{field}: {message}")


# Legacy constants for backward compatibility
MAX_SUMMARY_LENGTH = 255


def validate_issue_key(issue_key: str) -> str:
    """Validate JIRA issue key format.

    Args:
        issue_key: Issue key to validate (e.g., PROJ-123)

    Returns:
        The validated issue key (uppercase)

    Raises:
        ValidationError: If the issue key format is invalid
    """
    try:
        validated = IssueKeyInput(issue_key=issue_key)
        return validated.issue_key
    except ValueError as e:
        raise ValidationError("issue_key", str(e))


def validate_project_key(project_key: str) -> str:
    """Validate JIRA project key format.

    Args:
        project_key: Project key to validate (e.g., PROJ)

    Returns:
        The validated project key (uppercase)

    Raises:
        ValidationError: If the project key format is invalid
    """
    try:
        validated = ProjectKeyInput(project_key=project_key)
        return validated.project_key
    except ValueError as e:
        raise ValidationError("project_key", str(e))


def validate_summary(summary: str) -> str:
    """Validate issue summary.

    Args:
        summary: Issue summary/title to validate

    Returns:
        The validated summary (trimmed)

    Raises:
        ValidationError: If the summary is invalid
    """
    summary = summary.strip() if summary else ""

    if not summary:
        raise ValidationError("summary", "Summary is required")

    if len(summary) > MAX_SUMMARY_LENGTH:
        raise ValidationError(
            "summary",
            f"Summary exceeds maximum length of {MAX_SUMMARY_LENGTH} characters "
            f"(got {len(summary)})",
        )

    return summary


def validate_comment_body(body: str) -> str:
    """Validate comment body.

    Args:
        body: Comment body text to validate

    Returns:
        The validated body

    Raises:
        ValidationError: If the body is invalid
    """
    try:
        validated = CommentInput(body=body)
        return validated.body
    except ValueError as e:
        raise ValidationError("body", str(e))


def validate_labels(labels: list[str] | None) -> list[str] | None:
    """Validate issue labels.

    Args:
        labels: List of labels to validate

    Returns:
        The validated labels list or None

    Raises:
        ValidationError: If any label is invalid
    """
    if not labels:
        return labels

    try:
        validated = LabelListInput(labels=labels)
        return validated.labels if validated.labels else None
    except ValueError as e:
        raise ValidationError("labels", str(e))


def validate_account_id(account_id: str | None, field_name: str = "account_id") -> str | None:
    """Validate JIRA account ID.

    Args:
        account_id: Account ID to validate
        field_name: Name of the field for error messages

    Returns:
        The validated account ID or None

    Raises:
        ValidationError: If the account ID format is invalid
    """
    if account_id is None or account_id == "":
        return account_id

    try:
        validated = AccountIdInput(account_id=account_id)
        return validated.account_id
    except ValueError as e:
        raise ValidationError(field_name, str(e))


def sanitize_for_response(data: Any) -> Any:
    """Sanitize data for safe inclusion in responses.

    Uses bleach library with allowlist approach for robust XSS prevention:
    - Only allows safe HTML tags (p, br, a, ul, ol, li, code, pre, etc.)
    - Only allows safe attributes (href, title on links)
    - Only allows safe URL protocols (http, https, mailto)
    - Strips all other HTML content

    Args:
        data: Data to sanitize (string, dict, list, or other)

    Returns:
        Sanitized data with dangerous HTML removed
    """
    if isinstance(data, str):
        return bleach.clean(
            data,
            tags=ALLOWED_HTML_TAGS,
            attributes=ALLOWED_HTML_ATTRIBUTES,
            protocols=ALLOWED_PROTOCOLS,
            strip=True,
        )

    if isinstance(data, dict):
        return {k: sanitize_for_response(v) for k, v in data.items()}

    if isinstance(data, list):
        return [sanitize_for_response(item) for item in data]

    return data


def build_response(success: bool, **data: Any) -> dict[str, Any]:
    """Build a sanitized tool response.

    This is the standard way to build responses from MCP tools.
    All data values are automatically sanitized to remove potentially
    dangerous HTML content (XSS prevention).

    Args:
        success: Whether the operation succeeded.
        **data: Response data fields to include.

    Returns:
        Dict with 'success' field and sanitized data.

    Example:
        >>> build_response(True, issue_key="PROJ-123", data={"summary": "Test"})
        {"success": True, "issue_key": "PROJ-123", "data": {"summary": "Test"}}
    """
    sanitized = {k: sanitize_for_response(v) for k, v in data.items()}
    return {"success": success, **sanitized}


# =============================================================================
# Additional Validators for Security Hardening
# =============================================================================


# Allowed values for order_by parameters
ALLOWED_ORDER_BY_VALUES = {
    "created",
    "-created",
    "updated",
    "-updated",
    "name",
    "-name",
    "releaseDate",
    "-releaseDate",
    "sequence",
    "-sequence",
}


class OrderByInput(BaseModel):
    """Validated order_by parameter.

    Only allows known safe ordering values to prevent unexpected API behavior.

    Example:
        >>> validated = OrderByInput(order_by="-created")
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    order_by: str = Field(..., max_length=50, description="Order by field")

    @field_validator("order_by")
    @classmethod
    def validate_order_by(cls, v: str) -> str:
        """Validate order_by against whitelist."""
        v = v.strip()
        if v not in ALLOWED_ORDER_BY_VALUES:
            raise ValueError(
                f"Invalid order_by value: '{v}'. "
                f"Allowed: {', '.join(sorted(ALLOWED_ORDER_BY_VALUES))}"
            )
        return v


def validate_order_by(order_by: str) -> str:
    """Validate order_by parameter.

    Args:
        order_by: Order by value to validate.

    Returns:
        The validated order_by value.

    Raises:
        ValidationError: If the order_by value is not allowed.
    """
    try:
        validated = OrderByInput(order_by=order_by)
        return validated.order_by
    except ValueError as e:
        raise ValidationError("order_by", str(e))


# Allowed values for expand parameters
ALLOWED_EXPAND_VALUES = {
    # Issue expansions
    "changelog",
    "renderedFields",
    "names",
    "schema",
    "transitions",
    "operations",
    "editmeta",
    "versionedRepresentations",
    # Project expansions
    "description",
    "lead",
    "issueTypes",
    "url",
    "projectKeys",
    "permissions",
    "insight",
}


class ExpandInput(BaseModel):
    """Validated expand parameter.

    Only allows known safe expand fields to prevent exposure of internal data.

    Example:
        >>> validated = ExpandInput(expand="changelog,renderedFields")
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    expand: str = Field(..., max_length=500, description="Comma-separated expand fields")

    @field_validator("expand")
    @classmethod
    def validate_expand(cls, v: str) -> str:
        """Validate each expand field against whitelist."""
        v = v.strip()
        if not v:
            return v
        for field in v.split(","):
            field = field.strip()
            if field and field not in ALLOWED_EXPAND_VALUES:
                raise ValueError(
                    f"Invalid expand field: '{field}'. "
                    f"Allowed: {', '.join(sorted(ALLOWED_EXPAND_VALUES))}"
                )
        return v


def validate_expand(expand: str) -> str:
    """Validate expand parameter.

    Args:
        expand: Comma-separated expand fields to validate.

    Returns:
        The validated expand value.

    Raises:
        ValidationError: If any expand field is not allowed.
    """
    try:
        validated = ExpandInput(expand=expand)
        return validated.expand
    except ValueError as e:
        raise ValidationError("expand", str(e))


class DateTimeInput(BaseModel):
    """Validated ISO 8601 datetime parameter.

    Validates datetime strings in ISO 8601 format as used by JIRA API.

    Example:
        >>> validated = DateTimeInput(datetime="2024-01-15T09:00:00.000+0000")
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    datetime: str = Field(..., max_length=50, description="ISO 8601 datetime")

    @field_validator("datetime")
    @classmethod
    def validate_iso8601(cls, v: str) -> str:
        """Validate ISO 8601 datetime format."""
        v = v.strip()
        # ISO 8601 formats:
        # - 2024-01-15T09:00:00.000Z
        # - 2024-01-15T09:00:00.000+0000
        # - 2024-01-15T09:00:00Z
        # - 2024-01-15T09:00:00+00:00
        pattern = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d{1,3})?(Z|[+-]\d{2}:?\d{2})?$"
        if not re.match(pattern, v):
            raise ValueError(
                f"Invalid ISO 8601 datetime: '{v}'. "
                "Expected format: YYYY-MM-DDTHH:MM:SS.sss+HHMM or YYYY-MM-DDTHH:MM:SSZ"
            )
        return v


def validate_datetime(datetime_str: str) -> str:
    """Validate ISO 8601 datetime string.

    Args:
        datetime_str: Datetime string to validate.

    Returns:
        The validated datetime string.

    Raises:
        ValidationError: If the datetime format is invalid.
    """
    try:
        validated = DateTimeInput(datetime=datetime_str)
        return validated.datetime
    except ValueError as e:
        raise ValidationError("datetime", str(e))


class RemoteLinkUrlInput(BaseModel):
    """Validated URL for remote links.

    Security features:
    - Only http and https protocols allowed
    - Maximum length of 2000 characters
    - Basic URL format validation

    Example:
        >>> validated = RemoteLinkUrlInput(url="https://example.com/page")
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    url: str = Field(..., max_length=2000, description="Remote link URL")

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        """Validate URL format and protocol."""
        v = v.strip()
        if not v:
            raise ValueError("URL cannot be empty")

        # Only allow http and https
        if not v.startswith(("http://", "https://")):
            raise ValueError("URL must start with http:// or https://")

        # Basic URL format check
        url_pattern = r"^https?://[^\s/$.?#].[^\s]*$"
        if not re.match(url_pattern, v):
            raise ValueError("Invalid URL format")

        return v


def validate_remote_link_url(url: str) -> str:
    """Validate URL for remote links.

    Args:
        url: URL to validate.

    Returns:
        The validated URL.

    Raises:
        ValidationError: If the URL is invalid.
    """
    try:
        validated = RemoteLinkUrlInput(url=url)
        return validated.url
    except ValueError as e:
        raise ValidationError("url", str(e))


def validate_custom_fields(custom_fields: dict[str, Any] | None) -> dict[str, Any] | None:
    """Validate custom fields dictionary.

    Ensures all field names follow the customfield_XXXXX format.

    Args:
        custom_fields: Dictionary of custom field ID to value mappings.

    Returns:
        The validated custom fields dictionary or None.

    Raises:
        ValidationError: If any custom field name is invalid.

    Example:
        >>> validate_custom_fields({"customfield_10001": "value"})
        {"customfield_10001": "value"}
    """
    if not custom_fields:
        return custom_fields

    for field_name in custom_fields.keys():
        if not field_name.startswith("customfield_"):
            raise ValidationError(
                "custom_fields",
                f"Field '{field_name}' is not a custom field. "
                "Custom field names must start with 'customfield_'",
            )
        if not re.match(r"^customfield_\d+$", field_name):
            raise ValidationError(
                "custom_fields",
                f"Invalid custom field format: '{field_name}'. "
                "Expected format: customfield_XXXXX (where X is a digit)",
            )

    return custom_fields
