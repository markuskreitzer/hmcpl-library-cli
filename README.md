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

# Headless mode (for server environments like OpenClaw)
uv run hmcpl bootstrap           # First: run once to save browser state
uv run hmcpl --headless status   # Then: use headless mode for all commands
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

### Headless Mode (Server Environments)

For server environments without a display (like OpenClaw), you can use headless mode:

1. **Bootstrap once** on a machine with a display:
   ```bash
   uv run hmcpl bootstrap
   ```
   This opens a browser, logs in, and saves the full browser state (cookies, localStorage, etc.) to `~/.hmcpl_browser_state.json`.

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

Note: If the session expires, you'll need to re-run bootstrap on a machine with a display.

## Architecture

The tool uses a hybrid approach:
- **Playwright** for login and search (Cloudflare bypass requires real browser)
- **httpx** for AJAX API calls (faster for authenticated requests)

Session cookies are extracted after Playwright login and reused with httpx for subsequent API calls.

## Claude Code / OpenClaw Integration

This project includes a Claude Code plugin that allows you to manage your library account using natural language commands.

### Installation as Claude Code Plugin

1. Clone this repository to a local directory
2. Install the CLI tool:
   ```bash
   cd /path/to/hmcpl-library-cli
   uv sync
   uv run playwright install chromium
   ```

3. Create your `.env` file with credentials

4. Symlink the plugin to your Claude Code plugins directory:
   ```bash
   ln -s /path/to/hmcpl-library-cli ~/.claude/plugins/hmcpl-library
   ```

5. Enable the plugin in Claude Code settings or restart Claude Code

6. **For server environments** (headless mode):
   ```bash
   # Bootstrap once on a machine with a display
   uv run hmcpl bootstrap

   # Copy state file to server and set headless mode
   export HMCPL_HEADLESS=1
   ```

### Available Slash Commands

Once installed, you can use these commands in Claude Code:

| Command | Description |
|---------|-------------|
| `/library` | Full account overview (status, checkouts, holds) |
| `/library-status` | Account status, fines, expiration |
| `/library-checkouts` | View checked out items |
| `/library-holds` | View holds and their status |
| `/library-search` | Search the catalog |
| `/library-hold` | Place a hold on an item |
| `/library-renew` | Renew checked out items |

### Example Usage

```
You: /library
Claude: [Shows your complete library account overview]

You: /library-search python programming books
Claude: [Searches catalog and shows results]

You: /library-hold
Claude: What would you like to place a hold on?
You: The first Python book from the search
Claude: [Places hold and confirms]
```

### Natural Language

You can also just ask naturally:

- "What books do I have checked out?"
- "Do I have any holds ready for pickup?"
- "Search for books by Brandon Sanderson"
- "Renew all my books"
- "When does my library card expire?"
