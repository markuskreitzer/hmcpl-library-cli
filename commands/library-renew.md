---
allowed-tools: Bash(hmcpl renew:*), Bash(uv run hmcpl renew:*), Bash(hmcpl checkouts:*), Bash(uv run hmcpl checkouts:*)
description: Renew checked out library items
---

## Your task

Help the user renew their checked out library items.

To renew all eligible items: `uv run hmcpl renew --all`

To renew a specific item: `uv run hmcpl renew ITEM_ID`

If the user doesn't specify which item:
1. First list checkouts: `uv run hmcpl checkouts`
2. Ask which item(s) to renew
3. Renew the selected item(s)

Report success or any errors (some items may not be renewable if they have holds or have been renewed too many times).
