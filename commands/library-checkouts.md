---
allowed-tools: Bash(hmcpl checkouts:*), Bash(uv run hmcpl checkouts:*)
description: View your checked out library items and their due dates
---

## Your task

List the user's currently checked out library items.

Run: `uv run hmcpl checkouts`

If the user asks about items due soon, use: `uv run hmcpl checkouts --due-soon 7`
If the user asks about overdue items, use: `uv run hmcpl checkouts --overdue`

Present the results showing:
- Title and author
- Due date (highlight if due soon or overdue)
- Format (book, ebook, audiobook, etc.)
- Whether the item can be renewed
