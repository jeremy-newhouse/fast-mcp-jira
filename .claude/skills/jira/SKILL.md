---
name: jira
description: JIRA issue management - create, search, update, and manage issues, sprints, comments, and projects. Use when interacting with JIRA for issue tracking, sprint planning, or project management.
argument-hint: [action] [parameters]
---

# JIRA MCP Tools

This skill provides access to 47 JIRA tools via MCP. Use the `mcp__jira__*` tool names.

## Quick Reference

| Action | Tool | Key Parameters |
|--------|------|----------------|
| Create issue | `mcp__jira__create_issue` | project_key, summary, issue_type |
| Get issue | `mcp__jira__get_issue` | issue_key |
| Search issues | `mcp__jira__search_issues` | jql, fields, max_results |
| Update issue | `mcp__jira__update_issue` | issue_key, summary, description |
| Delete issue | `mcp__jira__delete_issue` | issue_key |
| Transition issue | `mcp__jira__transition_issue` | issue_key, transition_name |
| Get transitions | `mcp__jira__get_transitions` | issue_key |
| Add comment | `mcp__jira__add_comment` | issue_key, body |
| Get comments | `mcp__jira__get_comments` | issue_key |
| List boards | `mcp__jira__get_boards` | project_key (optional) |
| Get sprints | `mcp__jira__get_sprints` | board_id, state |
| Sprint issues | `mcp__jira__get_sprint_issues` | sprint_id |
| Create sprint | `mcp__jira__create_sprint` | board_id, name |
| Start sprint | `mcp__jira__start_sprint` | sprint_id |
| Complete sprint | `mcp__jira__complete_sprint` | sprint_id |
| Move to sprint | `mcp__jira__move_issues_to_sprint` | sprint_id, issue_keys |
| List projects | `mcp__jira__get_projects` | - |
| Bulk update | `mcp__jira__bulk_update_issues` | issue_keys, updates |
| Bulk transition | `mcp__jira__bulk_transition_issues` | issue_keys, transition_name |
| Bulk comment | `mcp__jira__bulk_add_comments` | issue_keys, body |

## Common Workflows

### Create and assign a bug
```
1. mcp__jira__create_issue(project_key="PROJ", summary="Bug title", issue_type="Bug", priority="High")
2. mcp__jira__update_issue(issue_key="PROJ-123", assignee="<account_id>")
3. mcp__jira__add_comment(issue_key="PROJ-123", body="Additional context...")
```

### Move issue through workflow
```
1. mcp__jira__get_transitions(issue_key="PROJ-123")  # See available transitions
2. mcp__jira__transition_issue(issue_key="PROJ-123", transition_name="In Progress")
3. mcp__jira__transition_issue(issue_key="PROJ-123", transition_name="Done")
```

### Add label (preserving existing)
```
# Labels are replaced, not appended - fetch existing first
1. mcp__jira__get_issue(issue_key="PROJ-123", fields="labels")
2. # Extract labels from response.fields.labels, add your new label
3. mcp__jira__update_issue(issue_key="PROJ-123", labels=["existing1", "existing2", "new-label"])
```

### Sprint Planning
```
# Find your board
mcp__jira__get_boards(project_key="PROJ")

# View future sprints to plan
mcp__jira__get_sprints(board_id=42, state="future")

# View active sprint
mcp__jira__get_sprints(board_id=42, state="active")

# Get issues in backlog (not in any sprint)
mcp__jira__search_issues(jql="project = PROJ AND sprint is EMPTY AND status != Done")
```

### Sprint Progress Monitoring
```
# Get active sprint details
mcp__jira__get_sprints(board_id=42, state="active")

# View all sprint issues with status
mcp__jira__get_sprint_issues(sprint_id=123, fields="summary,status,assignee,priority")

# Find incomplete issues in sprint
mcp__jira__get_sprint_issues(sprint_id=123, jql="status != Done")

# Find bugs blocking the sprint
mcp__jira__get_sprint_issues(sprint_id=123, jql="type = Bug AND status != Done")
```

### Sprint Review (End of Sprint)
```
# Get completed issues
mcp__jira__get_sprint_issues(sprint_id=123, jql="status = Done")

# Get incomplete issues (carryover candidates)
mcp__jira__get_sprint_issues(sprint_id=123, jql="status != Done")

# View closed sprints for velocity tracking
mcp__jira__get_sprints(board_id=42, state="closed")
```

### Daily Standup Queries
```
# My in-progress issues
mcp__jira__search_issues(jql="assignee = currentUser() AND status = 'In Progress'")

# Blocked issues in sprint
mcp__jira__get_sprint_issues(sprint_id=123, jql="status = Blocked")

# Issues updated today
mcp__jira__search_issues(jql="project = PROJ AND updated >= startOfDay()")
```

### Search with JQL
```
# My open bugs
mcp__jira__search_issues(jql="assignee = currentUser() AND type = Bug AND resolution = EMPTY")

# High priority issues in project
mcp__jira__search_issues(jql="project = PROJ AND priority in (High, Highest) AND status != Done")

# Issues updated this week
mcp__jira__search_issues(jql="project = PROJ AND updated >= startOfWeek()")

# Issues in current sprint
mcp__jira__search_issues(jql="project = PROJ AND sprint in openSprints()")

# Unassigned issues
mcp__jira__search_issues(jql="project = PROJ AND assignee is EMPTY AND status != Done")
```

### Link Related Issues
```
# Get available link types
mcp__jira__get_link_types()

# Create a "blocks" relationship
mcp__jira__create_link(inward_issue="PROJ-124", outward_issue="PROJ-123", link_type="Blocks")

# Create a duplicate link
mcp__jira__create_link(inward_issue="PROJ-125", outward_issue="PROJ-123", link_type="Duplicate")
```

### Time Tracking
```
# Log time on an issue
mcp__jira__add_worklog(issue_key="PROJ-123", time_spent="2h 30m", comment="Implemented feature X")

# View logged time
mcp__jira__get_worklogs(issue_key="PROJ-123")
```

### Sprint Management
```
# Create a new sprint
mcp__jira__create_sprint(board_id=42, name="Sprint 5", goal="Complete authentication feature")

# Start a future sprint with dates
mcp__jira__start_sprint(sprint_id=123, start_date="2024-01-15", end_date="2024-01-29")

# Move issues into a sprint
mcp__jira__move_issues_to_sprint(sprint_id=123, issue_keys=["PROJ-1", "PROJ-2", "PROJ-3"])

# Move issues to backlog (sprint_id=0)
mcp__jira__move_issues_to_sprint(sprint_id=0, issue_keys=["PROJ-4"])

# Complete an active sprint
mcp__jira__complete_sprint(sprint_id=123)

# Update sprint details
mcp__jira__update_sprint(sprint_id=123, name="Sprint 5 - Extended", goal="Updated goal")

# Delete a sprint (issues return to backlog)
mcp__jira__delete_sprint(sprint_id=123)
```

### Bulk Operations
```
# Update multiple issues at once (set priority and add labels)
mcp__jira__bulk_update_issues(
    issue_keys=["PROJ-1", "PROJ-2", "PROJ-3"],
    updates={"priority": {"name": "High"}, "labels": ["urgent", "review"]}
)

# Transition multiple issues to a new status
mcp__jira__bulk_transition_issues(
    issue_keys=["PROJ-1", "PROJ-2", "PROJ-3"],
    transition_name="Done"
)

# Add the same comment to multiple issues
mcp__jira__bulk_add_comments(
    issue_keys=["PROJ-1", "PROJ-2", "PROJ-3"],
    body="Deployed in release v1.2.0"
)
```

## Tool Categories

### Issues (8 tools)
- create_issue, get_issue, search_issues, update_issue, delete_issue
- transition_issue, get_transitions, get_changelog

### Comments (3 tools)
- add_comment, get_comments, delete_comment

### Worklogs (3 tools)
- add_worklog, get_worklogs, delete_worklog

### Attachments (4 tools)
- add_attachment, get_attachments, get_attachment, delete_attachment

### Agile/Sprints (10 tools)
- get_boards, get_board, get_sprints, get_sprint_issues
- create_sprint, update_sprint, start_sprint, complete_sprint
- move_issues_to_sprint, delete_sprint

### Projects (4 tools)
- get_projects, get_project, get_components, get_versions

### Links (3 tools)
- get_link_types, create_link, delete_link

### Watchers (3 tools)
- get_watchers, add_watcher, remove_watcher

### Metadata (5 tools)
- get_issue_types, get_priorities, get_statuses, search_users, get_fields

### Bulk Operations (3 tools)
- bulk_update_issues, bulk_transition_issues, bulk_add_comments

### Cache Management (2 tools)
- get_cache_stats, invalidate_cache

## Input Validation

All tools validate inputs:
- **Issue keys**: Format `PROJECT-123` (uppercase)
- **Project keys**: Uppercase letters/numbers, max 10 chars
- **JQL**: Injection patterns blocked
- **Filenames**: Path traversal blocked, dangerous extensions blocked

## Markdown Support

Descriptions and comments support markdown that converts to JIRA format:
- **bold**, *italic*, `code`
- Bullet lists (- item), numbered lists (1. item)
- Checklists ([] unchecked, [x] checked)
- Code blocks (```language)
- Headings (# ## ###)

## Error Handling

All tools return consistent structure:
```json
// Success
{"success": true, "data": {...}}

// Error
{"success": false, "error": "message", "status_code": 404}
```

Common errors:
- 401: Invalid credentials
- 403: Permission denied
- 404: Issue/resource not found
