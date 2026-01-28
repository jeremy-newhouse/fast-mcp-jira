"""Input validation utilities for JIRA API parameters."""

import re
from typing import Any


class ValidationError(Exception):
    """Raised when input validation fails."""

    def __init__(self, field: str, message: str):
        self.field = field
        self.message = message
        super().__init__(f"{field}: {message}")


# JIRA limits
MAX_SUMMARY_LENGTH = 255
MAX_COMMENT_LENGTH = 32767
MAX_LABEL_LENGTH = 255
MAX_PROJECT_KEY_LENGTH = 10

# Patterns
ISSUE_KEY_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]+-\d+$")
PROJECT_KEY_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]*$")
LABEL_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")


def validate_issue_key(issue_key: str) -> str:
    """Validate JIRA issue key format.

    Args:
        issue_key: Issue key to validate (e.g., PROJ-123)

    Returns:
        The validated issue key (uppercase)

    Raises:
        ValidationError: If the issue key format is invalid
    """
    if not issue_key:
        raise ValidationError("issue_key", "Issue key is required")

    issue_key = issue_key.strip().upper()

    if not ISSUE_KEY_PATTERN.match(issue_key):
        raise ValidationError(
            "issue_key",
            f"Invalid issue key format '{issue_key}'. "
            "Expected format: PROJECT-123 (letters, optional numbers/underscore, dash, numbers)",
        )

    return issue_key


def validate_project_key(project_key: str) -> str:
    """Validate JIRA project key format.

    Args:
        project_key: Project key to validate (e.g., PROJ)

    Returns:
        The validated project key (uppercase)

    Raises:
        ValidationError: If the project key format is invalid
    """
    if not project_key:
        raise ValidationError("project_key", "Project key is required")

    project_key = project_key.strip().upper()

    if len(project_key) > MAX_PROJECT_KEY_LENGTH:
        raise ValidationError(
            "project_key",
            f"Project key exceeds maximum length of {MAX_PROJECT_KEY_LENGTH} characters",
        )

    if not PROJECT_KEY_PATTERN.match(project_key):
        raise ValidationError(
            "project_key",
            f"Invalid project key format '{project_key}'. "
            "Must start with a letter and contain only uppercase letters, numbers, and underscores",
        )

    return project_key


def validate_summary(summary: str) -> str:
    """Validate issue summary.

    Args:
        summary: Issue summary/title to validate

    Returns:
        The validated summary (trimmed)

    Raises:
        ValidationError: If the summary is invalid
    """
    if not summary:
        raise ValidationError("summary", "Summary is required")

    summary = summary.strip()

    if len(summary) > MAX_SUMMARY_LENGTH:
        raise ValidationError(
            "summary",
            f"Summary exceeds maximum length of {MAX_SUMMARY_LENGTH} characters "
            f"(got {len(summary)})",
        )

    if not summary:
        raise ValidationError("summary", "Summary cannot be empty or whitespace only")

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
    if not body:
        raise ValidationError("body", "Comment body is required")

    if len(body) > MAX_COMMENT_LENGTH:
        raise ValidationError(
            "body",
            f"Comment body exceeds maximum length of {MAX_COMMENT_LENGTH} characters "
            f"(got {len(body)})",
        )

    return body


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

    validated = []
    for i, label in enumerate(labels):
        if not label:
            continue

        label = label.strip()

        if len(label) > MAX_LABEL_LENGTH:
            raise ValidationError(
                f"labels[{i}]",
                f"Label exceeds maximum length of {MAX_LABEL_LENGTH} characters",
            )

        if not LABEL_PATTERN.match(label):
            raise ValidationError(
                f"labels[{i}]",
                f"Invalid label '{label}'. Labels can only contain letters, numbers, "
                "underscores, and hyphens",
            )

        validated.append(label)

    return validated if validated else None


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

    account_id = account_id.strip()

    # Account IDs are typically in format: 712020:uuid or 5xxxxxxxxxxxxx
    if len(account_id) < 10:
        raise ValidationError(
            field_name,
            f"Account ID appears too short: '{account_id}'",
        )

    return account_id


def sanitize_for_response(data: Any) -> Any:
    """Sanitize data for safe inclusion in responses.

    Removes potentially dangerous content from strings.

    Args:
        data: Data to sanitize (string, dict, list, or other)

    Returns:
        Sanitized data
    """
    if isinstance(data, str):
        # Remove script tags
        data = re.sub(r"<script[^>]*>.*?</script>", "", data, flags=re.IGNORECASE | re.DOTALL)
        # Remove other dangerous HTML
        data = re.sub(
            r"<(iframe|object|embed|form)[^>]*>.*?</\1>",
            "",
            data,
            flags=re.IGNORECASE | re.DOTALL,
        )
        return data
    elif isinstance(data, dict):
        return {k: sanitize_for_response(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [sanitize_for_response(item) for item in data]
    return data
