---
allowed-tools: Bash(hmcpl holds:*), Bash(uv run hmcpl holds:*)
description: View your library holds and their status
---

## Your task

List the user's current library holds.

Run: `uv run hmcpl holds`

If the user only wants items ready for pickup: `uv run hmcpl holds --ready`
If the user only wants pending holds: `uv run hmcpl holds --pending`

Present the results showing:
- Title and author
- Status (ready for pickup, in transit, pending)
- Position in queue (if waiting)
- Pickup location
- Expiration date (if ready for pickup)
