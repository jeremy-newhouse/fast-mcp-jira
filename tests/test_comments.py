"""Tests for update_comment (jira client mocked, no network)."""

from unittest.mock import AsyncMock

import pytest

from fast_mcp_jira.services.jira_client import JiraError
from fast_mcp_jira.tools import comments


@pytest.fixture
def jira_put(monkeypatch):
    put = AsyncMock(
        return_value={
            "id": "10001",
            "updated": "2026-11-06T10:00:00.000+0000",
            "author": {"displayName": "Phil"},
        }
    )
    monkeypatch.setattr(comments.jira, "put", put)
    return put


async def test_update_comment_success(jira_put):
    r = await comments.update_comment(issue_key="SMAI-1", comment_id="10001", body="**hi**")
    jira_put.assert_awaited_once()
    args, kwargs = jira_put.call_args
    assert args[0] == "/rest/api/3/issue/SMAI-1/comment/10001"
    assert kwargs["body"] == {"body": comments.markdown_to_adf("**hi**")}
    assert r["success"] is True
    assert r["comment_id"] == "10001"
    assert r["issue_key"] == "SMAI-1"
    assert r["updated"] == "2026-11-06T10:00:00.000+0000"
    assert r["author"] == "Phil"


async def test_update_comment_bad_issue_key(jira_put):
    r = await comments.update_comment(issue_key="nope", comment_id="1", body="x")
    assert r["success"] is False
    jira_put.assert_not_awaited()


async def test_update_comment_non_numeric_id(jira_put):
    r = await comments.update_comment(issue_key="SMAI-1", comment_id="abc", body="x")
    assert r["success"] is False
    assert r["field"] == "comment_id"
    jira_put.assert_not_awaited()


async def test_update_comment_jira_error(jira_put):
    jira_put.side_effect = JiraError("not found", status_code=404)
    r = await comments.update_comment(issue_key="SMAI-1", comment_id="1", body="x")
    assert r["success"] is False
    assert r["status_code"] == 404
