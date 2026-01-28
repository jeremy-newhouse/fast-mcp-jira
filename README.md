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
| `CACHE_ENCRYPTION_ENABLED` | `false` | Enable SQLCipher cache encryption |
| `CACHE_ENCRYPTION_KEY` | (none) | Encryption key (min 32 chars) |
| `CACHE_ENCRYPTION_KEY_FILE` | (none) | Path to file containing encryption key |
| `CUSTOM_FIELDS_ENABLED` | `false` | Enable custom field tools |
| `CUSTOM_FIELDS_CONFIG_FILE` | `~/.fast-mcp-jira/custom-fields.json` | Custom fields config |
| `GRACEFUL_SHUTDOWN_TIMEOUT` | `30` | Shutdown timeout in seconds |

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
- Automatic retry with Retry-After header for JIRA HTTP 429 responses

### SSRF Prevention

The server blocks JIRA URLs pointing to private/internal networks:
- RFC 1918 ranges (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16)
- Loopback addresses (127.0.0.0/8, ::1)
- Link-local addresses (169.254.0.0/16)

### Response Sanitization

All tool responses are sanitized to prevent XSS attacks. User-provided content in responses is escaped before being returned.

### Response Size Limits

API responses are limited to 50MB to prevent denial-of-service attacks from oversized payloads.

### Cache Encryption

Optionally encrypt the SQLite cache database using SQLCipher:

```bash
# Install with encryption support
pip install sqlcipher3-binary
```

#### Option 1: Environment Variable

```bash
# Generate a secure key
openssl rand -base64 32

# Add to .env
CACHE_ENCRYPTION_ENABLED=true
CACHE_ENCRYPTION_KEY=your-generated-key-here
```

#### Option 2: Key File (Recommended for Production)

```bash
# Create the config directory
mkdir -p ~/.fast-mcp-jira
chmod 700 ~/.fast-mcp-jira

# Generate encryption key file
openssl rand -base64 32 > ~/.fast-mcp-jira/cache.key
chmod 600 ~/.fast-mcp-jira/cache.key

# Configure in .env
CACHE_ENCRYPTION_ENABLED=true
CACHE_ENCRYPTION_KEY_FILE=~/.fast-mcp-jira/cache.key
```

**Important:** The cache database (`cache.db`) and encryption key file (`cache.key`) are excluded from git via `.gitignore`. Never commit these files to version control.

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

## Custom Fields

Configure custom JIRA fields to generate dedicated MCP tools. Each field creates `get_<name>` and `set_<name>` tools.

### Configuration

1. Create `~/.fast-mcp-jira/custom-fields.json`:
```json
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
```

2. Enable in `.env`:
```bash
CUSTOM_FIELDS_ENABLED=true
```

### Supported Field Types

| Type | Description | JIRA Format |
|------|-------------|-------------|
| `text` | Plain text | String |
| `rich_text` | Markdown (converts to ADF) | ADF document |
| `number` | Integer or decimal | Number |
| `date` | Date (YYYY-MM-DD) | String |
| `datetime` | ISO 8601 datetime | String |
| `select` | Single select | `{"value": "..."}` |
| `multi_select` | Multiple selection | `[{"value": "..."}]` |
| `checkbox` | Boolean | Boolean |
| `user_picker` | User (account ID) | `{"accountId": "..."}` |

See `custom-fields.example.json` for a complete example.

## Markdown Support

Descriptions and comments support markdown formatting that converts to JIRA's Atlassian Document Format (ADF):

| Feature | Syntax |
|---------|--------|
| Bold | `**text**` |
| Italic | `*text*` or `_text_` |
| Inline code | `` `code` `` |
| Headings | `#`, `##`, `###` |
| Bullet lists | `- item` or `* item` |
| Numbered lists | `1. item` |
| Checklists | `[] task` / `[x] done` |
| Code blocks | ` ```language ` |
| @Mentions | `[~accountId:ID]` or `[~accountId:ID\|Name]` |

**Example:**
```python
create_issue(
    project_key="PROJ",
    summary="Fix login timeout",
    description="""**Bug:** Login page times out after 30 seconds

## Steps to Reproduce
1. Go to /login
2. Enter credentials
3. Wait 30 seconds

## Root Cause
```sql
-- Missing index on users.email
CREATE INDEX idx_users_email ON users(email);
```

## Checklist
[] Deploy fix to staging
[] Verify performance
[x] Root cause identified
"""
)
```

See [JIRA_USER_GUIDE.md](JIRA_USER_GUIDE.md) for complete markdown documentation.

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
