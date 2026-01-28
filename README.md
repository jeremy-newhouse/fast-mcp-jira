# Fast MCP JIRA

A Fast MCP server for Atlassian JIRA Cloud using Streamable HTTP transport.

## Features

- **47 MCP tools** covering all major JIRA operations
- **Markdown support** in descriptions and comments (bullet lists, checklists, code blocks, bold/italic)
- **Input validation** with clear error messages
- **Pagination** for large result sets
- **Async HTTP** client for high performance

## Installation

```bash
uv sync
```

## Configuration

Copy `.env.example` to `.env` and configure:

```bash
cp .env.example .env
```

### Required Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `JIRA_URL` | Your JIRA Cloud URL | `mycompany.atlassian.net` |
| `JIRA_EMAIL` | Your Atlassian account email | `user@example.com` |
| `JIRA_API_TOKEN` | Your Atlassian API token | (from id.atlassian.com) |

### Optional Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `JIRA_SSL_VERIFY` | `true` | SSL certificate verification |
| `HOST` | `0.0.0.0` | Server bind address |
| `PORT` | `5472` | Server port (JIRA on phone keypad) |
| `LOG_LEVEL` | `INFO` | Logging level |

## Running

```bash
uv run python -m fast_mcp_jira
```

The MCP server will be available at `http://localhost:5472/mcp`

## Claude Code Integration

To use this MCP server with Claude Code, create a `.mcp.json` file in your project root:

```json
{
  "mcpServers": {
    "jira": {
      "type": "http",
      "url": "http://localhost:5472/mcp"
    }
  }
}
```

Then start the server and Claude Code will automatically connect to it.

## Available Tools (47 total)

### Generic HTTP Tools (5)
Low-level tools for direct JIRA API access:

| Tool | Description |
|------|-------------|
| `jira_get` | Make GET requests to any JIRA API endpoint |
| `jira_post` | Make POST requests with JSON body |
| `jira_put` | Make PUT requests for full resource updates |
| `jira_patch` | Make PATCH requests (limited JIRA support) |
| `jira_delete` | Make DELETE requests |

### Issue Tools (8)
Create, read, update, delete, and transition issues:

| Tool | Description |
|------|-------------|
| `create_issue` | Create a new JIRA issue |
| `get_issue` | Get issue details by key |
| `search_issues` | Search issues using JQL with pagination |
| `update_issue` | Update issue fields |
| `delete_issue` | Delete an issue |
| `transition_issue` | Change issue status |
| `get_transitions` | Get available workflow transitions |
| `get_changelog` | Get issue change history |

### Comment Tools (3)

| Tool | Description |
|------|-------------|
| `add_comment` | Add a comment to an issue |
| `get_comments` | Get comments on an issue |
| `delete_comment` | Delete a comment |

### Worklog Tools (3)

| Tool | Description |
|------|-------------|
| `add_worklog` | Log time on an issue |
| `get_worklogs` | Get worklogs for an issue |
| `delete_worklog` | Delete a worklog entry |

### Attachment Tools (4)

| Tool | Description |
|------|-------------|
| `add_attachment` | Upload a file to an issue |
| `get_attachments` | List attachments on an issue |
| `get_attachment` | Get attachment metadata |
| `delete_attachment` | Delete an attachment |

### Agile Tools (4)

| Tool | Description |
|------|-------------|
| `get_boards` | List all boards |
| `get_board` | Get board details |
| `get_sprints` | Get sprints for a board |
| `get_sprint_issues` | Get issues in a sprint |

### Project Tools (4)

| Tool | Description |
|------|-------------|
| `get_projects` | List all projects |
| `get_project` | Get project details |
| `get_components` | Get project components |
| `get_versions` | Get project versions/releases |

### Link Tools (3)

| Tool | Description |
|------|-------------|
| `get_link_types` | Get available issue link types |
| `create_link` | Create a link between issues |
| `delete_link` | Delete an issue link |

### Watcher Tools (3)

| Tool | Description |
|------|-------------|
| `get_watchers` | Get issue watchers |
| `add_watcher` | Add a watcher to an issue |
| `remove_watcher` | Remove a watcher from an issue |

### Metadata Tools (5)

| Tool | Description |
|------|-------------|
| `get_issue_types` | Get all issue types |
| `get_priorities` | Get all priority levels |
| `get_statuses` | Get all workflow statuses |
| `search_users` | Search for users |
| `get_fields` | Get all available fields |

## Markdown Support

Descriptions and comments support markdown formatting that converts to JIRA's Atlassian Document Format (ADF):

```markdown
# Heading 1
## Heading 2

**bold text**
*italic text*
`inline code`

- Bullet item 1
- Bullet item 2

1. Numbered item 1
2. Numbered item 2

[] Unchecked task
[x] Checked task

```python
code block
```
```

## Pagination

Tools that return lists support pagination:

**Offset-based pagination** (most endpoints):
```python
# Get first page
result = get_projects(max_results=50, start_at=0)

# Get next page
result = get_projects(max_results=50, start_at=50)
```

**Cursor-based pagination** (search_issues):
```python
# Get first page
result = search_issues(jql="project=PROJ", max_results=50)

# Get next page using token
result = search_issues(
    jql="project=PROJ",
    max_results=50,
    next_page_token=result["next_page_token"]
)
```

## Input Validation

The server validates inputs before sending to JIRA:

| Field | Validation |
|-------|------------|
| `issue_key` | Format: `PROJECT-123` |
| `project_key` | Uppercase letters/numbers, max 10 chars |
| `summary` | Max 255 characters |
| `comment body` | Max 32,767 characters |
| `labels` | Alphanumeric, underscores, hyphens only |

Invalid inputs return clear error messages:
```json
{
  "success": false,
  "error": "issue_key: Invalid issue key format 'invalid'. Expected format: PROJECT-123",
  "field": "issue_key"
}
```

## Architecture

```
src/fast_mcp_jira/
├── __init__.py
├── __main__.py          # Entry point
├── config.py            # Settings from environment
├── server.py            # FastMCP server instance
├── services/
│   └── jira_client.py   # Async HTTP client
├── tools/
│   ├── agile.py         # Boards, sprints
│   ├── attachments.py   # File attachments
│   ├── comments.py      # Issue comments
│   ├── generic.py       # Raw HTTP methods
│   ├── issues.py        # Issue CRUD
│   ├── links.py         # Issue links
│   ├── metadata.py      # Types, priorities, statuses
│   ├── projects.py      # Projects, components, versions
│   ├── watchers.py      # Issue watchers
│   └── worklogs.py      # Time tracking
└── utils/
    ├── adf.py           # Markdown to ADF conversion
    └── validation.py    # Input validation
```

## Error Handling

All tools return consistent response structures:

**Success:**
```json
{
  "success": true,
  "data": { ... }
}
```

**JIRA API Error:**
```json
{
  "success": false,
  "error": "JIRA API error (404): Issue not found",
  "status_code": 404
}
```

**Validation Error:**
```json
{
  "success": false,
  "error": "summary: Summary exceeds maximum length of 255 characters",
  "field": "summary"
}
```

## Development

```bash
# Install dependencies
uv sync

# Run the server
uv run python -m fast_mcp_jira

# Lint
uv run ruff check src/
uv run ruff format --check src/

# Format code
uv run ruff format src/

# Run tests
uv run pytest
```

## License

MIT
