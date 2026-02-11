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

### System Dependencies (headless servers)

Headless Chromium requires system libraries. Install with:

```bash
sudo apt-get install -y libnspr4 libnss3 libatk1.0-0t64 libatk-bridge2.0-0t64 \
  libcups2t64 libxkbcommon0 libxdamage1 libgbm1 libpango-1.0-0 libcairo2 \
  libasound2t64 libxcomposite1 libxfixes3 libxrandr2
```

To check for missing libraries: `ldd ~/.cache/ms-playwright/chromium_headless_shell-*/chrome-headless-shell-linux64/chrome-headless-shell | grep "not found"`

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

# Set browser timeout (default 60s, useful for slow connections or Cloudflare delays)
uv run hmcpl --timeout 300 bootstrap
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
  "name": "MARK AARON ROBERT K."
}
```

## Headless Mode (Server Environments)

For server environments without a display (e.g. OpenClaw, CI), use headless mode. Headless mode scrapes rendered pages via a headless Chromium browser instead of calling AJAX APIs (which Cloudflare blocks).

### Setup

1. **Bootstrap once** on a machine with a display:
   ```bash
   uv run hmcpl bootstrap
   # Use --timeout 300 if Cloudflare challenges take a while
   ```
   This opens a browser, logs in, and saves the full browser state to `~/.hmcpl_browser_state.json`.

2. **Copy the state file** to your server:
   ```bash
   scp ~/.hmcpl_browser_state.json server:~/.hmcpl_browser_state.json
   ```

3. **Use headless mode** on the server:
   ```bash
   uv run hmcpl --headless status
   ```

   Or set the environment variable for all commands:
   ```bash
   export HMCPL_HEADLESS=1
   uv run hmcpl status  # Now runs headless automatically
   ```

### Headless Mode Limitations

- **Holds detail**: The `/MyAccount/Holds` URL is blocked by Cloudflare WAF (the word "Hold" triggers a rule). The `holds` command returns `[]` in headless mode. Use `status` for hold counts.
- **Session expiry**: If the saved browser state expires, re-run `bootstrap` on a machine with a display and copy the state file again.

## Architecture

### Non-headless mode
- **Playwright** for login (Cloudflare bypass requires real browser)
- **httpx** for AJAX API calls (faster for authenticated requests)

### Headless mode
Cloudflare blocks httpx entirely (TLS fingerprinting) and even blocks `fetch()` from within Playwright pages to AJAX endpoints. Headless mode uses a completely different approach:

- **Single persistent Playwright page** for all operations
- **Page scraping** of rendered HTML instead of AJAX calls
- **`_navigate()` helper** that skips navigation if already on the target URL (Cloudflare blocks repeated `page.goto()` to the same URL)
- **`page.evaluate()`** for JS-loaded content like the user's name

Key files:
| File | Purpose |
|------|---------|
| `hmcpl/client.py` | Main client with headless/non-headless branching |
| `hmcpl/parser.py` | HTML parsers for both AJAX responses and full pages |
| `hmcpl/cli.py` | CLI argument parsing and command dispatch |
| `hmcpl/models.py` | Pydantic data models |
| `~/.hmcpl_state.json` | Cached session cookies (simple format) |
| `~/.hmcpl_browser_state.json` | Full Playwright browser state for headless mode |

### Cloudflare Constraints (important for contributors)

These behaviors are specific to `catalog.hmcpl.org` and must be preserved:

1. **httpx is always blocked** - Cloudflare does TLS fingerprinting; only real browser engines pass
2. **`fetch()` inside Playwright is blocked** for AJAX endpoints - Cloudflare treats XHR differently from page navigations
3. **`/MyAccount/Holds` is blocked** by Cloudflare WAF - the word "Hold" in the URL triggers a firewall rule
4. **Repeated `page.goto()` to the same URL is blocked** - Cloudflare rate-limits or flags repeat navigations on the same page
5. **Opening multiple pages in one context is blocked** after the first - use a single persistent page
6. **User's name is loaded via async JS** - not in the initial HTML; must use `page.evaluate()` to read it

## OpenClaw Integration

This project is registered as an OpenClaw skill at `~/.openclaw/workspace/skills/hmcpl-library/`. OpenClaw can invoke library commands via natural language through Telegram or WhatsApp.

## Claude Code Integration

This project includes a Claude Code plugin (`.claude-plugin/plugin.json`) with slash commands in the `commands/` directory.

### Available Slash Commands

| Command | Description |
|---------|-------------|
| `/library` | Full account overview (status, checkouts, holds) |
| `/library-status` | Account status, fines, expiration |
| `/library-checkouts` | View checked out items |
| `/library-holds` | View holds and their status |
| `/library-search` | Search the catalog |
| `/library-hold` | Place a hold on an item |
| `/library-renew` | Renew checked out items |

---

## Guide for AI Coding Agents

This section is for AI agents (Claude Code, OpenClaw, Cursor, etc.) that need to understand or modify this codebase.

### Quick Start

```bash
cd /home/clawdine/library_manager
uv run hmcpl --headless status          # test it works
uv run hmcpl --headless checkouts       # list checked out books
uv run hmcpl --headless search "query"  # search catalog
```

All commands require `uv run` from this directory. All output is JSON on stdout, errors on stderr.

### Project Structure

```
hmcpl/
  client.py    # Core: HMCPLClient class, login, API methods, headless page scraping
  parser.py    # HTML parsers: parse_account_summary_page(), parse_checkouts_page(), etc.
  cli.py       # CLI: argparse setup, command handlers, --headless/--timeout flags
  models.py    # Pydantic models: AccountSummary, Checkout, Hold, SearchResult, etc.
```

### How Headless Mode Works

In headless mode (`--headless` or `HMCPL_HEADLESS=1`):

1. A **single Playwright headless Chromium page** is created and reused for all operations
2. Login navigates to `/MyAccount/Home` using saved browser state (`~/.hmcpl_browser_state.json`)
3. API data is obtained by **scraping rendered HTML pages**, not AJAX calls
4. The `_navigate(path)` method skips navigation if the page is already at the target URL

The key methods to understand:
- `_get_page()` - returns the persistent page (creates once, reuses)
- `_navigate(path)` - navigates only if not already there
- `_headless_login()` - opens browser with saved state, fills login if needed
- `_get_account_summary_headless()` - scrapes `/MyAccount/Home`
- `get_checkouts()` in headless branch - scrapes `/MyAccount/CheckedOut`

### Modifying the Code

**Adding a new command:**
1. Add method to `HMCPLClient` in `client.py` (with headless branch if needed)
2. Add parser function in `parser.py` if scraping HTML
3. Add CLI handler in `cli.py`
4. Add command markdown in `commands/` for Claude Code plugin

**Testing Cloudflare behavior:** Before relying on a URL, test it:
```python
page = await client._navigate("/MyAccount/SomeNewPage")
title = await page.title()
if "Attention Required" in title:
    # Blocked by Cloudflare
```

**Common pitfall:** Do NOT open new pages (`context.new_page()`) for each operation in headless mode. Cloudflare blocks all pages after the first. Always use `self._get_page()`.

### Dependencies

Python 3.11+, managed via `uv`. Key packages:
- `playwright` - headless browser automation
- `httpx` - HTTP client (non-headless mode only)
- `beautifulsoup4` + `lxml` - HTML parsing
- `pydantic` - data models
- `python-dotenv` - credential loading from `.env`

System libraries for headless Chromium (see Installation section).
