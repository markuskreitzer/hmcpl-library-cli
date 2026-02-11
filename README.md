# HMCPL Library Manager

CLI tool for managing your Huntsville-Madison County Public Library account.

## Features

- View account status (checkouts, holds, fines, expiration)
- List checked out items with due dates
- List holds and their status
- Search the library catalog
- Place holds on items
- Renew checked out items

## Installation

```bash
# Install dependencies
uv sync

# Install Playwright browser
uv run playwright install chromium
```

## Configuration

Create a `.env` file with your library credentials:

```bash
HMCPL_BARCODE=your_library_card_number
HMCPL_PIN=your_pin
```

## Usage

```bash
# View account summary
uv run hmcpl status

# List checkouts
uv run hmcpl checkouts
uv run hmcpl checkouts --due-soon 3    # Items due within 3 days
uv run hmcpl checkouts --overdue       # Only overdue items

# List holds
uv run hmcpl holds
uv run hmcpl holds --ready             # Items ready for pickup
uv run hmcpl holds --pending           # Pending holds only

# Search catalog
uv run hmcpl search "python programming"
uv run hmcpl search "stephen king" --index Author --limit 10

# Place a hold
uv run hmcpl hold <record-id> --pickup "South Huntsville"

# Renew items
uv run hmcpl renew <item-id>
uv run hmcpl renew --all

# Force re-login (clear cached session)
uv run hmcpl --relogin status
```

## Output

All commands output JSON to stdout. Errors are written to stderr as JSON.

Example status output:
```json
{
  "num_checked_out": 3,
  "num_overdue": 0,
  "num_holds": 2,
  "num_available_holds": 1,
  "total_fines": 0.0,
  "expires": "2027-11-01",
  "name": null
}
```

## Notes

- First run will open a browser window for authentication (Cloudflare bypass)
- Subsequent runs use cached session cookies
- Session cookies are stored in `~/.hmcpl_state.json`
- Search requires a browser window due to Cloudflare protection

## Architecture

The tool uses a hybrid approach:
- **Playwright** for login and search (Cloudflare bypass requires real browser)
- **httpx** for AJAX API calls (faster for authenticated requests)

Session cookies are extracted after Playwright login and reused with httpx for subsequent API calls.
