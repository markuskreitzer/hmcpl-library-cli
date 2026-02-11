---
allowed-tools: Bash(hmcpl search:*), Bash(uv run hmcpl search:*)
description: Search the HMCPL library catalog for books, ebooks, audiobooks, and more
---

## Your task

Search the Huntsville-Madison County Public Library catalog based on the user's query.

Run: `uv run hmcpl search "QUERY" --limit 10`

Available search indexes (use --index flag):
- Keyword (default)
- Title
- Author
- Subject
- Series

Examples:
- `uv run hmcpl search "python programming"`
- `uv run hmcpl search "Stephen King" --index Author`
- `uv run hmcpl search "Harry Potter" --index Series`

Present the results showing:
- Title and author
- Format (Book, eBook, Audiobook, etc.)
- Availability status
- The record ID (in case the user wants to place a hold)
