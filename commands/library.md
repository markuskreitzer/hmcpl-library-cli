---
allowed-tools: Bash(hmcpl:*), Bash(uv run hmcpl:*)
description: Manage your HMCPL library account - quick overview of checkouts, holds, and account status
---

## Your task

Provide a comprehensive overview of the user's HMCPL library account.

Run these commands and summarize the results:

1. Account status: `uv run hmcpl status`
2. Current checkouts: `uv run hmcpl checkouts`
3. Current holds: `uv run hmcpl holds`

Present a friendly summary including:
- Account status (fines, expiration)
- Items checked out with due dates (highlight anything due soon)
- Holds and their status (highlight anything ready for pickup)

If nothing is checked out or on hold, let the user know and offer to help them search for something.

## Available library commands

Mention that the user can also use these specific commands:
- `/library-status` - Account overview
- `/library-checkouts` - View checked out items
- `/library-holds` - View holds
- `/library-search` - Search the catalog
- `/library-hold` - Place a hold
- `/library-renew` - Renew items
