---
allowed-tools: Bash(hmcpl hold:*), Bash(uv run hmcpl hold:*), Bash(hmcpl search:*), Bash(uv run hmcpl search:*)
description: Place a hold on a library item
---

## Your task

Help the user place a hold on a library item.

If the user provides a search query instead of a record ID:
1. First search: `uv run hmcpl search "QUERY" --limit 5`
2. Present the options and ask which one they want
3. Once confirmed, place the hold

To place a hold: `uv run hmcpl hold RECORD_ID`

If the user specifies a pickup location: `uv run hmcpl hold RECORD_ID --pickup "LOCATION"`

Common HMCPL pickup locations:
- Main Library
- Bailey Cove
- Madison
- Monrovia
- South Huntsville
- Gurley
- Hazel Green
- New Hope
- Harvest

Confirm success or report any errors.
