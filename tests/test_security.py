"""Security tests for input validation.

These tests verify that the Pydantic validators and validation functions
properly reject malicious or invalid inputs.
"""

import pytest
from pydantic import ValidationError as PydanticValidationError

from fast_mcp_jira.utils.validation import (
    AccountIdInput,
    AttachmentInput,
    IssueKeyInput,
    JqlInput,
    NumericIdInput,
    ProjectKeyInput,
    ValidationError,
    validate_issue_key,
    validate_project_key,
)


class TestIssueKeyValidation:
    """Tests for issue key validation."""

    def test_valid_issue_keys(self):
        """Valid issue keys should be accepted and normalized."""
        # Standard format
        result = IssueKeyInput(issue_key="PROJ-123")
        assert result.issue_key == "PROJ-123"

        # Lowercase should be normalized
        result = IssueKeyInput(issue_key="proj-456")
        assert result.issue_key == "PROJ-456"

        # With underscores in project
        result = IssueKeyInput(issue_key="MY_PROJ-789")
        assert result.issue_key == "MY_PROJ-789"

    def test_invalid_issue_key_formats(self):
        """Invalid formats should be rejected."""
        invalid_keys = [
            "",  # Empty
            "PROJ",  # No number
            "123",  # No project
            "PROJ-",  # No number after dash
            "-123",  # No project before dash
            "PROJ123",  # No dash
            "proj_123",  # Underscore instead of dash
            "P-1-2",  # Multiple dashes
        ]
        for key in invalid_keys:
            with pytest.raises(PydanticValidationError):
                IssueKeyInput(issue_key=key)

    def test_issue_key_injection_attempt(self):
        """Injection attempts in issue keys should be rejected."""
        injection_attempts = [
            "PROJ-123; DROP TABLE",
            "PROJ-123<script>",
            "PROJ-123/../../../etc/passwd",
            "PROJ-123\x00",
        ]
        for key in injection_attempts:
            with pytest.raises(PydanticValidationError):
                IssueKeyInput(issue_key=key)


class TestProjectKeyValidation:
    """Tests for project key validation."""

    def test_valid_project_keys(self):
        """Valid project keys should be accepted."""
        result = ProjectKeyInput(project_key="PROJ")
        assert result.project_key == "PROJ"

        result = ProjectKeyInput(project_key="my_proj")
        assert result.project_key == "MY_PROJ"

    def test_invalid_project_keys(self):
        """Invalid project keys should be rejected."""
        invalid_keys = [
            "",  # Empty
            "123PROJ",  # Starts with number
            "_PROJ",  # Starts with underscore
            "PROJ-123",  # Contains dash
            "PROJECT_KEY_TOO_LONG",  # Too long
        ]
        for key in invalid_keys:
            with pytest.raises(PydanticValidationError):
                ProjectKeyInput(project_key=key)


class TestAttachmentValidation:
    """Tests for attachment input validation."""

    def test_valid_filenames(self):
        """Valid filenames should be accepted."""
        valid_filenames = [
            "document.pdf",
            "my-file_v2.txt",
            "screenshot 2024.png",
            "report.docx",
        ]
        for filename in valid_filenames:
            result = AttachmentInput(
                filename=filename,
                content_base64="SGVsbG8gV29ybGQ=",
            )
            assert result.filename == filename

    def test_path_traversal_blocked(self):
        """Path traversal attempts should be blocked."""
        traversal_attempts = [
            "../etc/passwd",
            "..\\windows\\system32",
            "folder/../../../secret.txt",
            "/etc/passwd",
            "C:\\Windows\\System32\\cmd.exe",
        ]
        for filename in traversal_attempts:
            with pytest.raises(PydanticValidationError):
                AttachmentInput(
                    filename=filename,
                    content_base64="SGVsbG8=",
                )

    def test_dangerous_extensions_blocked(self):
        """Dangerous file extensions should be blocked."""
        dangerous_files = [
            "script.exe",
            "malware.bat",
            "virus.cmd",
            "exploit.sh",
            "payload.ps1",
            "library.dll",
            "module.so",
        ]
        for filename in dangerous_files:
            with pytest.raises(PydanticValidationError):
                AttachmentInput(
                    filename=filename,
                    content_base64="SGVsbG8=",
                )

    def test_null_byte_injection_blocked(self):
        """Null byte injection should be blocked."""
        with pytest.raises(PydanticValidationError):
            AttachmentInput(
                filename="file.txt\x00.exe",
                content_base64="SGVsbG8=",
            )

    def test_content_size_limit(self):
        """Large content should be rejected."""
        # Create content larger than 70MB limit
        huge_content = "A" * (70_000_001)
        with pytest.raises(PydanticValidationError):
            AttachmentInput(
                filename="large.txt",
                content_base64=huge_content,
            )


class TestJqlValidation:
    """Tests for JQL query validation."""

    def test_valid_jql_queries(self):
        """Valid JQL queries should be accepted."""
        valid_queries = [
            "project = PROJ",
            "status = 'In Progress'",
            "assignee = currentUser()",
            "created >= -7d",
            "priority in (High, Highest) AND resolution = EMPTY",
            "labels in (backend, api)",
            "sprint in openSprints()",
        ]
        for jql in valid_queries:
            result = JqlInput(jql=jql)
            assert result.jql == jql

    def test_sql_injection_blocked(self):
        """SQL-like injection patterns should be blocked."""
        injection_attempts = [
            "project = PROJ;",  # Semicolon at end
            "project = PROJ; ",  # Semicolon with trailing space
            "project = PROJ--comment",  # Double dash
            "project = PROJ /* comment */",  # Block comment open
            "project = PROJ */",  # Block comment close
        ]
        for jql in injection_attempts:
            with pytest.raises(PydanticValidationError):
                JqlInput(jql=jql)

    def test_jql_length_limit(self):
        """Very long JQL should be rejected."""
        long_jql = "project = " + "A" * 10001
        with pytest.raises(PydanticValidationError):
            JqlInput(jql=long_jql)


class TestNumericIdValidation:
    """Tests for numeric ID validation."""

    def test_valid_numeric_ids(self):
        """Valid numeric IDs should be accepted."""
        valid_ids = ["1", "123", "10001", "999999999"]
        for id_val in valid_ids:
            result = NumericIdInput(id=id_val)
            assert result.id == id_val

    def test_non_numeric_rejected(self):
        """Non-numeric IDs should be rejected."""
        invalid_ids = [
            "abc",
            "12a34",
            "12.34",
            "-123",
            "123/456",
            "123; DELETE",
        ]
        for id_val in invalid_ids:
            with pytest.raises(PydanticValidationError):
                NumericIdInput(id=id_val)


class TestAccountIdValidation:
    """Tests for account ID validation."""

    def test_valid_account_ids(self):
        """Valid account IDs should be accepted."""
        valid_ids = [
            "712020:abcd-1234-efgh-5678",
            "5a1234567890abcdef123456",
            "user_account_id_12345",
        ]
        for account_id in valid_ids:
            result = AccountIdInput(account_id=account_id)
            assert result.account_id == account_id

    def test_short_account_id_rejected(self):
        """Too short account IDs should be rejected."""
        with pytest.raises(PydanticValidationError):
            AccountIdInput(account_id="abc")

    def test_invalid_characters_rejected(self):
        """Invalid characters in account ID should be rejected."""
        invalid_ids = [
            "account<script>",
            "account; DROP",
            "account/../../../",
        ]
        for account_id in invalid_ids:
            with pytest.raises(PydanticValidationError):
                AccountIdInput(account_id=account_id)


class TestLegacyValidationFunctions:
    """Tests for backward-compatible validation functions."""

    def test_validate_issue_key(self):
        """Legacy validate_issue_key function should work."""
        assert validate_issue_key("proj-123") == "PROJ-123"

        with pytest.raises(ValidationError) as exc:
            validate_issue_key("")
        assert exc.value.field == "issue_key"

    def test_validate_project_key(self):
        """Legacy validate_project_key function should work."""
        assert validate_project_key("proj") == "PROJ"

        with pytest.raises(ValidationError) as exc:
            validate_project_key("")
        assert exc.value.field == "project_key"
