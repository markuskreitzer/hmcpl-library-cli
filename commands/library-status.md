---
allowed-tools: Bash(hmcpl status:*), Bash(uv run hmcpl status:*)
description: Check your library account status including checkouts, holds, fines, and card expiration
---

## Your task

Check the user's HMCPL library account status and present a friendly summary.

Run: `uv run hmcpl status`

Present the results in a clear, human-readable format including:
- Number of items checked out
- Any overdue items
- Number of holds (and how many are ready for pickup)
- Outstanding fines
- Library card expiration date
