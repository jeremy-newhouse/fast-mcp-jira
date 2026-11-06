"""Dummy settings so importing the server never needs real credentials."""

import os

os.environ.setdefault("JIRA_URL", "https://example.atlassian.net")
os.environ.setdefault("JIRA_EMAIL", "test@example.com")
os.environ.setdefault("JIRA_API_TOKEN", "dummy")
os.environ.setdefault("CACHE_ENABLED", "false")
os.environ.setdefault("MCP_AUTH_ENABLED", "false")
