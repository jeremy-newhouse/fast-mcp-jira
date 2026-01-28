# Fast MCP JIRA - User Guide

This guide provides comprehensive documentation for using the Fast MCP JIRA tools (47 tools available).

## Quick Reference

| Tool | Purpose | Key Parameters |
|------|---------|----------------|
| `create_issue` | Create new issues | project_key, summary, issue_type |
| `get_issue` | Fetch issue details | issue_key |
| `search_issues` | Query with JQL | jql, max_results |
| `update_issue` | Modify issue fields | issue_key, summary, description |
| `delete_issue` | Remove an issue | issue_key |
| `transition_issue` | Change issue status | issue_key, transition_name |
| `get_transitions` | List available statuses | issue_key |
| `add_comment` | Add comments | issue_key, body |
| `get_comments` | List comments | issue_key |
| `add_attachment` | Upload files | issue_key, filename, content_base64 |
| `get_boards` | List Scrum/Kanban boards | - |
| `get_sprints` | List sprints | board_id |
| `get_sprint_issues` | Issues in a sprint | sprint_id |

---

## Markdown Formatting

Issue descriptions and comments support markdown that automatically converts to JIRA's Atlassian Document Format (ADF).

### Supported Markdown Features

| Feature | Syntax | Example |
|---------|--------|---------|
| **Bold** | `**text**` | **bold text** |
| **Italic** | `*text*` or `_text_` | *italic text* |
| **Inline code** | `` `code` `` | `inline code` |
| **Headings** | `# H1`, `## H2`, `### H3` | Headings 1-6 |
| **Bullet lists** | `- item` or `* item` | Bulleted list |
| **Numbered lists** | `1. item` | Numbered list |
| **Checklists** | `[] task` or `[x] done` | Task list |
| **Code blocks** | ` ```language ` | Syntax-highlighted code |
| **@Mentions** | `[~accountId:ID]` | Mention a user by account ID |

### @Mentions

Mention users in descriptions and comments using JIRA's mention syntax:

| Syntax | Description |
|--------|-------------|
| `[~accountId:557058:xyz123]` | Mention by account ID |
| `[~accountId:557058:xyz123\|John Smith]` | Mention with display name |

Use `search_users(query="name")` to find account IDs. Example:

```
add_comment(
    issue_key="PROJ-123",
    body="[~accountId:557058:abc123|Jane] Can you review this? cc [~accountId:557058:def456|Bob]"
)
```

### Code Block Languages

Supported syntax highlighting languages include:
`python`, `javascript`, `typescript`, `java`, `go`, `rust`, `ruby`, `php`, `csharp`, `cpp`, `c`, `bash`, `shell`, `sql`, `json`, `yaml`, `xml`, `html`, `css`, `markdown`, and [many more](https://confluence.atlassian.com/doc/code-block-macro-139390.html).

### Example: Full-Featured Description

```
**Bug Report: Login Page Timeout**

This issue affects all users trying to log in during peak hours.

## Environment
- **Browser:** Chrome 120
- **OS:** macOS Sonoma

## Steps to Reproduce
1. Navigate to /login
2. Enter valid credentials
3. Wait 30+ seconds
4. Observe 504 Gateway Timeout error

## Expected vs Actual
- **Expected:** Login completes within 5 seconds
- **Actual:** Request times out after 30 seconds

## Technical Details

The issue appears to be in the authentication service:

```python
async def authenticate(username: str, password: str):
    # This query is missing an index
    user = await db.query("SELECT * FROM users WHERE email = ?", username)
    return verify_password(password, user.password_hash)
```

## Checklist
[] Verify database indexes
[x] Confirmed reproduction steps
[] Deploy fix to staging
```

### Example: Using Markdown in Code

```python
# Create issue with markdown description
create_issue(
    project_key="PROJ",
    summary="Fix database query performance",
    description="""**Problem:** Slow authentication queries

## Analysis
The `users` table is missing an index on the `email` column.

## Solution
```sql
CREATE INDEX idx_users_email ON users(email);
```

## Testing
- [ ] Run migration on staging
- [ ] Verify query performance
- [ ] Load test with 1000 concurrent users
"""
)

# Add markdown comment
add_comment(
    issue_key="PROJ-123",
    body="""**Investigation Complete**

Root cause identified:
1. Missing database index
2. N+1 query in auth middleware

*Fix deployed to staging for testing.*"""
)
```

---

## Tool Reference

### Issue Management

#### create_issue

Create a new JIRA issue.

**Parameters:**
| Parameter | Required | Description |
|-----------|----------|-------------|
| project_key | Yes | Project identifier (e.g., "PROJ") |
| summary | Yes | Issue title (max 255 chars) |
| issue_type | No | "Bug", "Task", "Story", "Epic" (default: "Task") |
| description | No | Markdown-formatted description |
| priority | No | "Highest", "High", "Medium", "Low", "Lowest" |
| labels | No | List of labels to apply |
| assignee | No | Account ID of assignee |

**Example:**
```
create_issue(
    project_key="PROJ",
    summary="Fix login page timeout",
    issue_type="Bug",
    description="Users report 504 errors after 30 seconds on login page.\n\n**Steps to reproduce:**\n1. Go to /login\n2. Wait 30 seconds\n3. See timeout error",
    priority="High",
    labels=["backend", "urgent"]
)
```

**Response:**
```json
{
    "success": true,
    "issue_key": "PROJ-456",
    "issue_id": "10001",
    "self": "https://your-site.atlassian.net/rest/api/3/issue/10001"
}
```

---

#### get_issue

Get details of a JIRA issue.

**Parameters:**
| Parameter | Required | Description |
|-----------|----------|-------------|
| issue_key | Yes | Issue key (e.g., "PROJ-123") |
| fields | No | Comma-separated fields (e.g., "summary,status,assignee") |
| expand | No | Comma-separated expansions (e.g., "changelog,renderedFields") |

**Example:**
```
get_issue(issue_key="PROJ-123")
```

---

#### search_issues

Find issues using JQL (JIRA Query Language).

**Parameters:**
| Parameter | Required | Description |
|-----------|----------|-------------|
| jql | Yes | JQL query string (max 10,000 chars) |
| fields | No | Comma-separated fields to return |
| max_results | No | Results per page, 1-100 (default: 50) |
| next_page_token | No | Token for pagination |

**Common JQL Patterns:**
```
# Issues in a project
project = PROJ

# Issues by status
status = "In Progress"

# My assigned issues
assignee = currentUser()

# Bugs created in last 7 days
project = PROJ AND type = Bug AND created >= -7d

# High priority unresolved issues
priority in (High, Highest) AND resolution = EMPTY

# Issues with specific labels
labels in (backend, api)

# Issues in current sprint
sprint in openSprints()

# Issues updated this week
updated >= startOfWeek()
```

**Example:**
```
search_issues(
    jql="project = PROJ AND type = Bug AND status != Done",
    fields="key,summary,status,priority,assignee",
    max_results=25
)
```

---

#### update_issue

Modify fields on an existing issue.

**Parameters:**
| Parameter | Required | Description |
|-----------|----------|-------------|
| issue_key | Yes | Issue key (e.g., "PROJ-123") |
| summary | No | New title |
| description | No | New description (markdown) |
| priority | No | New priority |
| labels | No | New labels (replaces existing) |
| assignee | No | New assignee account ID |

**Example:**
```
update_issue(
    issue_key="PROJ-123",
    summary="[URGENT] Fix login page timeout",
    priority="Highest"
)
```

---

#### transition_issue

Change issue status (e.g., move to "In Progress", "Done").

**Parameters:**
| Parameter | Required | Description |
|-----------|----------|-------------|
| issue_key | Yes | Issue key |
| transition_name | No* | Target status name (e.g., "Done") |
| transition_id | No* | Target transition ID |

*One of transition_name or transition_id is required.

**Example:**
```
# First, check available transitions
get_transitions(issue_key="PROJ-123")

# Then transition
transition_issue(issue_key="PROJ-123", transition_name="In Progress")
```

---

### Comments

#### add_comment

Add a comment to an issue. Supports markdown formatting.

**Parameters:**
| Parameter | Required | Description |
|-----------|----------|-------------|
| issue_key | Yes | Issue key |
| body | Yes | Comment text (max 32,767 chars). Supports: **bold**, *italic*, `code`, ```code blocks```, - lists, 1. numbered lists |

**Example:**
```
add_comment(
    issue_key="PROJ-123",
    body="Investigated this issue:\n\n**Root cause:** Database connection pool exhaustion\n\n**Fix:** Increased pool size from 10 to 50 in `config/database.yml`"
)
```

---

#### get_comments

Get all comments on an issue.

**Parameters:**
| Parameter | Required | Description |
|-----------|----------|-------------|
| issue_key | Yes | Issue key |
| max_results | No | Max comments to return (default: 50) |
| order_by | No | "created" or "-created" for descending |

---

### Attachments

#### add_attachment

Upload a file attachment to an issue.

**Security:** Filenames are validated to prevent path traversal. Dangerous extensions (.exe, .bat, etc.) are blocked.

**Parameters:**
| Parameter | Required | Description |
|-----------|----------|-------------|
| issue_key | Yes | Issue key |
| filename | Yes | File name (max 255 chars, no path separators) |
| content_base64 | Yes | Base64-encoded file content (max ~50MB) |
| content_type | No | MIME type (default: "application/octet-stream") |

**Example:**
```python
import base64

# Encode file content
with open("screenshot.png", "rb") as f:
    content = base64.b64encode(f.read()).decode()

add_attachment(
    issue_key="PROJ-123",
    filename="screenshot.png",
    content_base64=content,
    content_type="image/png"
)
```

---

#### get_attachments

List all attachments on an issue.

**Parameters:**
| Parameter | Required | Description |
|-----------|----------|-------------|
| issue_key | Yes | Issue key |

---

### Sprint Management

#### get_boards

List all JIRA boards (Scrum/Kanban).

**Parameters:**
| Parameter | Required | Description |
|-----------|----------|-------------|
| name | No | Filter by board name |
| project_key | No | Filter by project |
| board_type | No | "scrum", "kanban", or "simple" |

**Example:**
```
get_boards(project_key="PROJ", board_type="scrum")
```

---

#### get_sprints

Get sprints for a board.

**Parameters:**
| Parameter | Required | Description |
|-----------|----------|-------------|
| board_id | Yes | Board ID (from get_boards) |
| state | No | "active", "future", or "closed" |

**Example:**
```
get_sprints(board_id=42, state="active")
```

---

#### get_sprint_issues

Get all issues in a sprint.

**Parameters:**
| Parameter | Required | Description |
|-----------|----------|-------------|
| sprint_id | Yes | Sprint ID (from get_sprints) |
| fields | No | Comma-separated fields |
| jql | No | Additional JQL filter |

**Example:**
```
get_sprint_issues(
    sprint_id=123,
    fields="summary,status,assignee,priority",
    jql="type = Bug"
)
```

---

#### create_sprint

Create a new sprint on a Scrum board.

**Parameters:**
| Parameter | Required | Description |
|-----------|----------|-------------|
| board_id | Yes | Board ID (Scrum boards only) |
| name | Yes | Sprint name |
| start_date | No | ISO 8601 date (e.g., "2024-01-15") |
| end_date | No | ISO 8601 date |
| goal | No | Sprint goal description |

**Example:**
```
create_sprint(
    board_id=42,
    name="Sprint 16",
    start_date="2024-02-01",
    end_date="2024-02-14",
    goal="Complete user authentication feature"
)
```

---

#### start_sprint

Start a future sprint (activates it).

**Parameters:**
| Parameter | Required | Description |
|-----------|----------|-------------|
| sprint_id | Yes | Sprint ID |
| start_date | No | Override start date |
| end_date | No | Override end date |

**Example:**
```
start_sprint(sprint_id=123, start_date="2024-02-01", end_date="2024-02-14")
```

---

#### complete_sprint

Complete an active sprint.

**Parameters:**
| Parameter | Required | Description |
|-----------|----------|-------------|
| sprint_id | Yes | Sprint ID |

**Example:**
```
complete_sprint(sprint_id=123)
```

---

#### move_issues_to_sprint

Move issues to a sprint or backlog.

**Parameters:**
| Parameter | Required | Description |
|-----------|----------|-------------|
| sprint_id | Yes | Sprint ID (use 0 for backlog) |
| issue_keys | Yes | List of issue keys to move |

**Example:**
```
# Move to sprint
move_issues_to_sprint(sprint_id=123, issue_keys=["PROJ-1", "PROJ-2", "PROJ-3"])

# Move to backlog
move_issues_to_sprint(sprint_id=0, issue_keys=["PROJ-4"])
```

---

#### delete_sprint

Delete a sprint (issues return to backlog).

**Parameters:**
| Parameter | Required | Description |
|-----------|----------|-------------|
| sprint_id | Yes | Sprint ID |

**Example:**
```
delete_sprint(sprint_id=123)
```

---

### Issue Links

#### create_link

Link two issues together.

**Parameters:**
| Parameter | Required | Description |
|-----------|----------|-------------|
| inward_issue | Yes | Issue that receives the link |
| outward_issue | Yes | Issue being linked to |
| link_type | Yes | "Blocks", "Duplicate", "Relates", etc. |

**Example:**
```
create_link(
    inward_issue="PROJ-123",
    outward_issue="PROJ-456",
    link_type="Blocks"
)
```

---

### Bulk Operations

#### bulk_update_issues

Update multiple issues at once with the same field values.

**Parameters:**
| Parameter | Required | Description |
|-----------|----------|-------------|
| issue_keys | Yes | List of issue keys (max 100) |
| updates | Yes | Field updates to apply to all issues |

**Example:**
```
bulk_update_issues(
    issue_keys=["PROJ-1", "PROJ-2", "PROJ-3"],
    updates={
        "priority": {"name": "High"},
        "labels": ["urgent", "review"]
    }
)
```

**Response:**
```json
{
    "success": true,
    "total": 3,
    "updated": 3,
    "failed": 0,
    "results": [
        {"issue_key": "PROJ-1", "success": true},
        {"issue_key": "PROJ-2", "success": true},
        {"issue_key": "PROJ-3", "success": true}
    ]
}
```

---

#### bulk_transition_issues

Transition multiple issues to a new status.

**Parameters:**
| Parameter | Required | Description |
|-----------|----------|-------------|
| issue_keys | Yes | List of issue keys (max 100) |
| transition_name | Yes | Target status name (e.g., "Done") |

**Example:**
```
bulk_transition_issues(
    issue_keys=["PROJ-1", "PROJ-2", "PROJ-3"],
    transition_name="Done"
)
```

---

#### bulk_add_comments

Add the same comment to multiple issues.

**Parameters:**
| Parameter | Required | Description |
|-----------|----------|-------------|
| issue_keys | Yes | List of issue keys (max 100) |
| body | Yes | Comment text (supports markdown) |

**Example:**
```
bulk_add_comments(
    issue_keys=["PROJ-1", "PROJ-2", "PROJ-3"],
    body="Deployed in release v1.2.0"
)
```

---

### Cache Management

The server caches JIRA metadata (issue types, priorities, projects, boards) to improve performance. Cache entries have configurable TTLs.

#### get_cache_stats

Get cache statistics including hit rates.

**Example:**
```
get_cache_stats()
```

**Response:**
```json
{
    "success": true,
    "enabled": true,
    "entries": {"total": 150, "valid": 142, "expired": 8},
    "overall": {"hits": 500, "misses": 50, "hit_rate": 90.91},
    "by_entity_type": {
        "issue_types": {"hits": 100, "misses": 1, "hit_rate": 99.01},
        "projects": {"hits": 200, "misses": 10, "hit_rate": 95.24}
    }
}
```

---

#### invalidate_cache

Clear cache entries manually.

**Parameters:**
| Parameter | Required | Description |
|-----------|----------|-------------|
| entity_type | No | Clear specific type (e.g., "projects", "boards") |
| cache_key | No | Clear specific key |
| invalidate_all | No | Clear entire cache (default: false) |

**Example:**
```
# Clear all project data
invalidate_cache(entity_type="projects")

# Clear entire cache
invalidate_cache(invalidate_all=True)
```

---

## Use-Case Cookbook

### Create and Assign a Bug Report

```
# 1. Create the bug
create_issue(
    project_key="PROJ",
    summary="Login fails with special characters in password",
    issue_type="Bug",
    description="**Environment:** Production\n\n**Steps:**\n1. Create account with password containing @#$\n2. Try to log in\n3. See 'Invalid credentials' error",
    priority="High"
)

# 2. Assign to developer (use search_users to find account ID)
update_issue(
    issue_key="PROJ-789",
    assignee="712020:abcd-1234-..."
)

# 3. Add additional context
add_comment(
    issue_key="PROJ-789",
    body="Stack trace attached. Appears to be SQL injection prevention being too aggressive."
)
```

---

### Move Issue Through Workflow

```
# 1. Check what transitions are available
get_transitions(issue_key="PROJ-123")
# Returns: [{"id": "21", "name": "In Progress"}, {"id": "31", "name": "Done"}]

# 2. Start work on issue
transition_issue(issue_key="PROJ-123", transition_name="In Progress")

# 3. Mark as complete
transition_issue(issue_key="PROJ-123", transition_name="Done")
```

---

### Sprint Management Workflow

```
# 1. Find your board
get_boards(project_key="PROJ")
# Returns: [{"id": 42, "name": "PROJ Board", "type": "scrum"}]

# 2. Get active sprint
get_sprints(board_id=42, state="active")
# Returns: [{"id": 123, "name": "Sprint 15", "state": "active"}]

# 3. View sprint issues
get_sprint_issues(sprint_id=123)

# 4. Check sprint progress (bugs only)
get_sprint_issues(
    sprint_id=123,
    jql="type = Bug AND status != Done",
    fields="summary,status,priority"
)
```

### Sprint Planning

```
# View future sprints
get_sprints(board_id=42, state="future")

# Get backlog items (not in any sprint)
search_issues(jql="project = PROJ AND sprint is EMPTY AND status != Done")
```

### Sprint Review (End of Sprint)

```
# Get completed issues
get_sprint_issues(sprint_id=123, jql="status = Done")

# Get incomplete issues (carryover)
get_sprint_issues(sprint_id=123, jql="status != Done")

# View closed sprints for velocity
get_sprints(board_id=42, state="closed")
```

### Daily Standup Queries

```
# My in-progress work
search_issues(jql="assignee = currentUser() AND status = 'In Progress'")

# Blocked issues in sprint
get_sprint_issues(sprint_id=123, jql="status = Blocked")

# What changed today
search_issues(jql="project = PROJ AND updated >= startOfDay()")
```

---

### Bulk Issue Query Examples

```
# Find all unresolved bugs assigned to me
search_issues(
    jql="assignee = currentUser() AND type = Bug AND resolution = EMPTY ORDER BY priority DESC"
)

# Find issues blocking release
search_issues(
    jql="fixVersion = '2.0' AND status != Done ORDER BY priority DESC"
)

# Find stale issues (no updates in 30 days)
search_issues(
    jql="project = PROJ AND updated < -30d AND status != Done"
)

# Find issues by label
search_issues(
    jql="labels = 'tech-debt' AND project = PROJ"
)
```

---

## Best Practices

1. **Always specify project_key** - Required for creating issues and helpful for filtering searches.

2. **Use JQL for complex queries** - More flexible than filtering by individual fields.

3. **Check transitions before changing status** - Available transitions depend on current state and workflow configuration.

4. **Use markdown in descriptions** - Renders nicely in JIRA. Support includes bold, italic, code blocks, lists, and headings.

5. **Validate issue keys** - Must match format `PROJECT-123`. The tools will normalize case automatically.

6. **Handle pagination** - For large result sets, check `next_page_token` and `is_last` in responses.

7. **Rate limiting** - The server limits requests to 10/second with burst of 20. Heavy operations may be throttled.

---

## Error Handling

All tools return a consistent response structure:

**Success:**
```json
{
    "success": true,
    "...additional fields..."
}
```

**Error:**
```json
{
    "success": false,
    "error": "Error message",
    "field": "field_name",  // If validation error
    "status_code": 404      // If JIRA API error
}
```

Common errors:
- `status_code: 401` - Invalid credentials or API key
- `status_code: 403` - Permission denied
- `status_code: 404` - Issue/resource not found
- `status_code: 429` - Rate limited (server will auto-retry)
- `field: "jql"` - Invalid JQL syntax
- `field: "filename"` - Invalid filename (path traversal blocked)
- `field: "expand"` - Invalid expand parameter
- `field: "order_by"` - Invalid order_by parameter
- `field: "datetime"` - Invalid ISO 8601 datetime format

---

## Authentication

### MCP Endpoint Authentication

When `MCP_API_KEY` is configured on the server, clients must include the API key:

```
Authorization: Bearer your-api-key
```

### JIRA Authentication

The server uses JIRA Cloud API tokens for authentication. Configure in `.env`:
- `JIRA_URL`: Your Atlassian domain (e.g., `mycompany.atlassian.net`)
- `JIRA_EMAIL`: Your Atlassian account email
- `JIRA_API_TOKEN`: API token from [id.atlassian.com](https://id.atlassian.com/manage-profile/security/api-tokens)

---

## Security Features

The server includes several security hardening measures:

### Input Validation

All inputs are validated before being sent to JIRA:

| Field | Validation |
|-------|------------|
| `issue_key` | Format: `PROJECT-123` (uppercase) |
| `project_key` | Uppercase letters/numbers, max 10 chars |
| `jql` | Checked for SQL injection patterns, max 10,000 chars |
| `filename` | Path traversal blocked, dangerous extensions blocked |
| `expand` | Whitelist of allowed JIRA expand fields |
| `order_by` | Whitelist of allowed order fields |
| `datetime` | ISO 8601 format validation |

### SSRF Prevention

JIRA URLs are validated to block internal/private network access:
- Private IP ranges (10.x.x.x, 172.16-31.x.x, 192.168.x.x)
- Loopback (127.x.x.x, localhost)
- Link-local (169.254.x.x)

### Response Sanitization

All tool responses are sanitized to prevent XSS. User-provided content is escaped before being returned.

### Rate Limiting

- Client-side: 10 requests/second with burst of 20
- Server-side: Automatic retry with Retry-After header for HTTP 429 responses

### Response Size Limits

API responses are limited to 50MB to prevent memory exhaustion.

### Cache Encryption

Optional SQLCipher encryption for the cache database:

```bash
# Generate a key file (recommended)
mkdir -p ~/.fast-mcp-jira && chmod 700 ~/.fast-mcp-jira
openssl rand -base64 32 > ~/.fast-mcp-jira/cache.key
chmod 600 ~/.fast-mcp-jira/cache.key

# Configure in .env
CACHE_ENCRYPTION_ENABLED=true
CACHE_ENCRYPTION_KEY_FILE=~/.fast-mcp-jira/cache.key
```

**Note:** Cache database and key files are excluded from git via `.gitignore`.
