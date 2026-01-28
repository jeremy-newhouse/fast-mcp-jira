# Fast MCP JIRA

A Fast MCP server for Atlassian JIRA Cloud using Streamable HTTP transport.

## Installation

```bash
uv sync
```

## Configuration

Copy `.env.example` to `.env` and configure:

```bash
cp .env.example .env
```

Required environment variables:
- `JIRA_URL` - Your JIRA Cloud URL (e.g., `mycompany.atlassian.net`)
- `JIRA_EMAIL` - Your Atlassian account email
- `JIRA_API_TOKEN` - Your Atlassian API token

Optional:
- `JIRA_SSL_VERIFY` - Set to `false` to disable SSL verification (default: `true`)
- `HOST` - Server bind address (default: `0.0.0.0`)
- `PORT` - Server port (default: `8000`)
- `LOG_LEVEL` - Logging level (default: `INFO`)

## Running

```bash
uv run python -m fast_mcp_jira
```

The MCP server will be available at `http://localhost:8000/mcp`

## Available Tools

### Generic HTTP Tools
- `jira_get` - Make GET requests to any JIRA API endpoint
- `jira_post` - Make POST requests with JSON body
- `jira_put` - Make PUT requests for full resource updates
- `jira_patch` - Make PATCH requests for partial updates
- `jira_delete` - Make DELETE requests

### Issue Tools
- `create_issue` - Create a new JIRA issue
- `get_issue` - Get issue details by key
- `search_issues` - Search issues using JQL
- `update_issue` - Update issue fields
- `delete_issue` - Delete an issue
- `transition_issue` - Change issue status

### Comment Tools
- `add_comment` - Add a comment to an issue
- `get_comments` - Get comments on an issue
- `delete_comment` - Delete a comment

### Worklog Tools
- `add_worklog` - Log time on an issue
- `get_worklogs` - Get worklogs for an issue
- `delete_worklog` - Delete a worklog entry

### Attachment Tools
- `get_attachments` - List attachments on an issue
- `get_attachment` - Get attachment metadata
- `delete_attachment` - Delete an attachment

### Agile Tools
- `get_boards` - List all boards
- `get_board` - Get board details
- `get_sprints` - Get sprints for a board
- `get_sprint_issues` - Get issues in a sprint
