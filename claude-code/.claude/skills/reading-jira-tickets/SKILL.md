---
name: reading-jira-tickets
description: Use when needing to read, view, or search JIRA tickets/issues/work items from the command line
---

# Reading JIRA Tickets with acli

Use the Atlassian CLI (`acli`) to read JIRA tickets.

## View a Ticket

```bash
acli jira workitem view TICKET-123
```

Default fields: key, type, summary, status, assignee, description

### More Fields

```bash
acli jira workitem view TICKET-123 --fields '*all'
```

### JSON Output

```bash
acli jira workitem view TICKET-123 --json
```

## Read Comments

```bash
acli jira workitem comment list --key TICKET-123
```

## Search Tickets

```bash
acli jira workitem search --jql "project = PROJ AND status = 'In Progress'"
acli jira workitem search --jql "assignee = currentUser()"
```

### Useful Flags

- `--limit N` - max results
- `--json` - JSON output
- `--fields "key,summary,status"` - specific fields

## Authentication

If you get auth errors:

```bash
acli jira auth login --web
```