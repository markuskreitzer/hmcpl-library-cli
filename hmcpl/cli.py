"""CLI interface for HMCPL Library Manager."""

import argparse
import asyncio
import json
import os
import sys
from datetime import date, timedelta
from pathlib import Path

from dotenv import load_dotenv

from hmcpl.client import HMCPLClient, BROWSER_STATE_FILE
from hmcpl.models import AccountSummary, Checkout, Hold, SearchResult


def json_serializer(obj):
    """JSON serializer for objects not serializable by default."""
    if isinstance(obj, date):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")


def output_json(data):
    """Output data as JSON to stdout."""
    if hasattr(data, "model_dump"):
        data = data.model_dump()
    elif isinstance(data, list) and data and hasattr(data[0], "model_dump"):
        data = [item.model_dump() for item in data]
    print(json.dumps(data, default=json_serializer, indent=2))


def error(message: str):
    """Output error to stderr and exit."""
    print(json.dumps({"error": message}), file=sys.stderr)
    sys.exit(1)


async def cmd_status(client: HMCPLClient, args):
    """Show account status summary."""
    summary = await client.get_account_summary()
    output_json(summary)


async def cmd_checkouts(client: HMCPLClient, args):
    """List checked out items."""
    checkouts = await client.get_checkouts()

    # Filter by due soon if requested
    if args.due_soon:
        cutoff = date.today() + timedelta(days=args.due_soon)
        checkouts = [c for c in checkouts if c.due_date and c.due_date <= cutoff]

    # Filter overdue if requested
    if args.overdue:
        today = date.today()
        checkouts = [c for c in checkouts if c.due_date and c.due_date < today]

    output_json(checkouts)


async def cmd_holds(client: HMCPLClient, args):
    """List holds."""
    holds = await client.get_holds()

    # Filter by ready/available if requested
    if args.ready:
        holds = [h for h in holds if h.status == "available"]

    # Filter by pending if requested
    if args.pending:
        holds = [h for h in holds if h.status == "pending"]

    output_json(holds)


async def cmd_search(client: HMCPLClient, args):
    """Search the catalog."""
    results = await client.search(
        query=args.query,
        index=args.index,
        limit=args.limit,
    )
    output_json(results)


async def cmd_hold(client: HMCPLClient, args):
    """Place a hold on an item."""
    result = await client.place_hold(
        record_id=args.record_id,
        pickup_location=args.pickup,
    )
    output_json(result)


async def cmd_renew(client: HMCPLClient, args):
    """Renew checked out items."""
    if args.all:
        results = await client.renew_all()
        output_json(results)
    elif args.item_id:
        result = await client.renew_item(args.item_id)
        output_json(result)
    else:
        error("Must specify --all or an item ID")


async def cmd_locations(client: HMCPLClient, args):
    """List pickup locations."""
    locations = await client.get_pickup_locations()
    output_json({"locations": locations})


async def cmd_bootstrap(args):
    """Bootstrap browser state for headless mode (requires headed browser)."""
    load_dotenv()

    barcode = os.getenv("HMCPL_BARCODE")
    pin = os.getenv("HMCPL_PIN")

    if not barcode or not pin:
        error("HMCPL_BARCODE and HMCPL_PIN environment variables must be set")

    # Force headed mode for bootstrap
    client = HMCPLClient(barcode, pin, headless=False)

    try:
        print("Opening browser for login... Please complete any challenges if prompted.", file=sys.stderr)
        if await client.login(force=True):
            if BROWSER_STATE_FILE.exists():
                output_json({
                    "success": True,
                    "message": "Browser state saved. You can now use --headless mode.",
                    "state_file": str(BROWSER_STATE_FILE),
                })
            else:
                error("Login succeeded but browser state was not saved")
        else:
            error("Failed to login to HMCPL")
    finally:
        await client.close()


async def run_command(args):
    """Run the specified command."""
    load_dotenv()

    barcode = os.getenv("HMCPL_BARCODE")
    pin = os.getenv("HMCPL_PIN")

    if not barcode or not pin:
        error("HMCPL_BARCODE and HMCPL_PIN environment variables must be set")

    # Headless mode: CLI flag or environment variable
    headless = getattr(args, "headless", False) or os.getenv("HMCPL_HEADLESS", "").lower() in ("1", "true", "yes")
    client = HMCPLClient(barcode, pin, headless=headless)

    try:
        # Login
        if not await client.login(force=args.relogin if hasattr(args, "relogin") else False):
            error("Failed to login to HMCPL")

        # Run the command
        await args.func(client, args)

    finally:
        await client.close()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        prog="hmcpl",
        description="HMCPL Library Manager - CLI for Huntsville-Madison County Public Library",
    )
    parser.add_argument("--relogin", action="store_true", help="Force re-login (ignore cached session)")
    parser.add_argument("--headless", action="store_true", help="Run browser in headless mode (requires bootstrap first)")

    subparsers = parser.add_subparsers(dest="command", required=True)

    # status command
    status_parser = subparsers.add_parser("status", help="Show account status summary")
    status_parser.set_defaults(func=cmd_status)

    # checkouts command
    checkouts_parser = subparsers.add_parser("checkouts", help="List checked out items")
    checkouts_parser.add_argument("--due-soon", type=int, metavar="DAYS", help="Only show items due within N days")
    checkouts_parser.add_argument("--overdue", action="store_true", help="Only show overdue items")
    checkouts_parser.set_defaults(func=cmd_checkouts)

    # holds command
    holds_parser = subparsers.add_parser("holds", help="List holds")
    holds_parser.add_argument("--ready", action="store_true", help="Only show holds ready for pickup")
    holds_parser.add_argument("--pending", action="store_true", help="Only show pending holds")
    holds_parser.set_defaults(func=cmd_holds)

    # search command
    search_parser = subparsers.add_parser("search", help="Search the library catalog")
    search_parser.add_argument("query", help="Search query")
    search_parser.add_argument("--index", default="Keyword", help="Search index (Keyword, Title, Author, Subject)")
    search_parser.add_argument("--limit", type=int, default=20, help="Maximum results to return")
    search_parser.set_defaults(func=cmd_search)

    # hold command
    hold_parser = subparsers.add_parser("hold", help="Place a hold on an item")
    hold_parser.add_argument("record_id", help="Record ID of the item to hold")
    hold_parser.add_argument("--pickup", help="Pickup location name")
    hold_parser.set_defaults(func=cmd_hold)

    # renew command
    renew_parser = subparsers.add_parser("renew", help="Renew checked out items")
    renew_parser.add_argument("item_id", nargs="?", help="Item ID to renew")
    renew_parser.add_argument("--all", action="store_true", help="Renew all eligible items")
    renew_parser.set_defaults(func=cmd_renew)

    # locations command
    locations_parser = subparsers.add_parser("locations", help="List pickup locations")
    locations_parser.set_defaults(func=cmd_locations)

    # bootstrap command (for headless mode setup)
    bootstrap_parser = subparsers.add_parser(
        "bootstrap",
        help="Bootstrap browser state for headless mode (opens browser for login)",
    )
    bootstrap_parser.set_defaults(func=None, is_bootstrap=True)

    args = parser.parse_args()

    try:
        # Bootstrap is a special command that doesn't need the normal client flow
        if getattr(args, "is_bootstrap", False):
            asyncio.run(cmd_bootstrap(args))
        else:
            asyncio.run(run_command(args))
    except KeyboardInterrupt:
        sys.exit(130)
    except Exception as e:
        error(str(e))


if __name__ == "__main__":
    main()
