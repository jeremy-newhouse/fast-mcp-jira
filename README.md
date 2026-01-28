# Fast MCP JIRA

A Fast MCP server for Atlassian JIRA Cloud using Streamable HTTP transport.

## Features

- **47 MCP tools** covering all major JIRA operations
- **SQLite caching** for metadata with configurable TTLs
- **Bulk operations** for updating multiple issues at once
- **Sprint management** - create, start, complete, and delete sprints
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
| `HOST` | `127.0.0.1` | Server bind address |
| `PORT` | `5472` | Server port (JIRA on phone keypad) |
| `LOG_LEVEL` | `INFO` | Logging level |
| `LOG_FORMAT` | `console` | Log format: `console` or `json` |
| `MCP_API_KEY` | (none) | API key for endpoint authentication |
| `CACHE_ENABLED` | `true` | Enable SQLite caching |
| `CACHE_DB_PATH` | `~/.fast-mcp-jira/cache.db` | Cache database location |
| `CACHE_TTL_METADATA` | `86400` | Metadata cache TTL (24h) |
| `CACHE_TTL_PROJECTS` | `21600` | Projects cache TTL (6h) |
| `CACHE_TTL_AGILE` | `1800` | Boards/sprints cache TTL (30m) |

## Security

### API Key Authentication

When `MCP_API_KEY` is set, all MCP requests must include the key in the Authorization header:

```
Authorization: Bearer your-api-key
```

#### Generating a Secure API Key

Generate a cryptographically secure API key using one of these methods:

```bash
# Using openssl (recommended)
openssl rand -base64 32

# Using Python
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Using uuidgen
uuidgen | tr -d '-'
```

Add the generated key to your `.env` file:

```bash
MCP_API_KEY=your-generated-key-here
```

Leave `MCP_API_KEY` unset for unauthenticated access (suitable for local development only).

### Input Validation

All tools validate inputs before sending to JIRA:
- Issue keys must match format `PROJECT-123`
- Project keys are validated (uppercase, max 10 chars)
- JQL queries are checked for injection patterns
- Filenames are validated against path traversal and dangerous extensions
- Numeric IDs are validated

### Rate Limiting

Built-in rate limiting protects against API abuse:
- Default: 10 requests/second with burst of 20
- Configurable via `RATE_LIMIT_PER_SECOND` and `RATE_LIMIT_BURST`

## Running

```bash
uv run python -m fast_mcp_jira
```

The MCP server will be available at `http://localhost:5472/mcp`

## Claude Code Integration

To use this MCP server with Claude Code:

### 1. Configure MCP Server

Create a `.mcp.json` file in your project root. Use the included `.mcp.json` as a template:

**Without authentication** (local development):
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

**With authentication** (recommended for shared environments):
```json
{
  "mcpServers": {
    "jira": {
      "type": "http",
      "url": "http://localhost:5472/mcp",
      "headers": {
        "Authorization": "Bearer ${MCP_API_KEY}"
      }
    }
  }
}
```

The `${MCP_API_KEY}` syntax references the environment variable, keeping your API key out of version control.

### 2. Install the /jira Skill (Optional)

Copy the skill to your Claude Code skills directory for the `/jira` command:

```bash
mkdir -p ~/.claude/skills/jira
cp .claude/skills/jira/SKILL.md ~/.claude/skills/jira/
```

Then use `/jira` to invoke the skill directly.

### 3. Start the Server

```bash
uv run python -m fast_mcp_jira
```

Claude Code will automatically connect to the MCP server.

See [JIRA_USER_GUIDE.md](JIRA_USER_GUIDE.md) for detailed tool documentation and examples.

## Available Tools (47 total)

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

### Agile Tools (10)

| Tool | Description |
|------|-------------|
| `get_boards` | List all boards |
| `get_board` | Get board details |
| `get_sprints` | Get sprints for a board |
| `get_sprint_issues` | Get issues in a sprint |
| `create_sprint` | Create a new sprint on a Scrum board |
| `update_sprint` | Update sprint name, dates, goal, or state |
| `start_sprint` | Start a future sprint |
| `complete_sprint` | Complete an active sprint |
| `move_issues_to_sprint` | Move issues to a sprint or backlog |
| `delete_sprint` | Delete a sprint |

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

### Bulk Operations (3)

| Tool | Description |
|------|-------------|
| `bulk_update_issues` | Update multiple issues with the same field values |
| `bulk_transition_issues` | Transition multiple issues to a new status |
| `bulk_add_comments` | Add the same comment to multiple issues |

### Cache Management (2)

| Tool | Description |
|------|-------------|
| `get_cache_stats` | Get cache statistics and hit rates |
| `invalidate_cache` | Clear cache entries by type or entirely |

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
├── auth.py              # API key authentication
├── config.py            # Settings from environment
├── errors.py            # Standardized error types
├── logging_config.py    # Structured logging configuration
├── server.py            # FastMCP server instance
├── services/
│   ├── cache.py         # SQLite cache with TTL expiration
│   └── jira_client.py   # Async HTTP client with rate limiting
├── tools/
│   ├── agile.py         # Boards, sprints, sprint management
│   ├── attachments.py   # File attachments
│   ├── bulk.py          # Bulk operations
│   ├── cache.py         # Cache management tools
│   ├── comments.py      # Issue comments
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
