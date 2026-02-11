"""HMCPL Library Client - handles authentication and API calls."""

import asyncio
import json
import re
from datetime import date
from pathlib import Path

import httpx
from playwright.async_api import async_playwright, Browser, BrowserContext

from hmcpl.models import AccountSummary, Checkout, Hold, SearchResult, HoldResult, RenewResult
from hmcpl.parser import parse_checkouts_html, parse_holds_html, parse_search_results_html, parse_date


BASE_URL = "https://catalog.hmcpl.org"
STATE_FILE = Path.home() / ".hmcpl_state.json"
BROWSER_STATE_FILE = Path.home() / ".hmcpl_browser_state.json"


class HMCPLClient:
    """Client for interacting with HMCPL library system."""

    def __init__(self, barcode: str, pin: str, headless: bool = False):
        self.barcode = barcode
        self.pin = pin
        self.headless = headless
        self.cookies: dict[str, str] = {}
        self._http_client: httpx.AsyncClient | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._playwright = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def close(self):
        """Clean up resources."""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None
        if self._context:
            await self._context.close()
            self._context = None
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None

    def _save_cookies(self):
        """Save cookies to state file."""
        STATE_FILE.write_text(json.dumps({"cookies": self.cookies}))

    def _load_cookies(self) -> bool:
        """Load cookies from state file."""
        if STATE_FILE.exists():
            try:
                data = json.loads(STATE_FILE.read_text())
                self.cookies = data.get("cookies", {})
                return bool(self.cookies)
            except (json.JSONDecodeError, KeyError):
                pass
        return False

    @property
    def http_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client with current cookies."""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(
                base_url=BASE_URL,
                cookies=self.cookies,
                headers={
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                    "Accept": "application/json, text/html, */*",
                    "X-Requested-With": "XMLHttpRequest",
                },
                follow_redirects=True,
                timeout=30.0,
            )
        return self._http_client

    async def _save_browser_state(self):
        """Save browser state (cookies, localStorage, etc.) for headless reuse."""
        if self._context:
            await self._context.storage_state(path=str(BROWSER_STATE_FILE))

    def _has_browser_state(self) -> bool:
        """Check if saved browser state exists."""
        return BROWSER_STATE_FILE.exists()

    async def _get_browser_context(self) -> BrowserContext:
        """Get or create a browser context."""
        if self._context is None:
            self._playwright = await async_playwright().start()

            # In headless mode, try to use saved browser state
            # If no state exists, will need to bootstrap with headed mode first
            use_headless = self.headless and self._has_browser_state()

            self._browser = await self._playwright.chromium.launch(
                headless=use_headless,
                args=["--disable-blink-features=AutomationControlled"],
            )

            # Load saved state if available (for headless mode)
            storage_state = str(BROWSER_STATE_FILE) if self._has_browser_state() else None

            self._context = await self._browser.new_context(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 1920, "height": 1080},
                locale="en-US",
                storage_state=storage_state,
            )
            # Hide webdriver property
            await self._context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
            """)
        return self._context

    async def login(self, force: bool = False) -> bool:
        """
        Login to HMCPL using Playwright, extract session cookies.

        Returns True if login successful, False otherwise.
        """
        # Try to use cached cookies first
        if not force and self._load_cookies():
            # Verify cookies are still valid
            if await self._verify_session():
                return True

        context = await self._get_browser_context()
        page = await context.new_page()
        page.set_default_timeout(60000)  # 60 second timeout

        try:
            # Navigate to login page - use 'load' instead of 'networkidle' for reliability
            await page.goto(f"{BASE_URL}/MyAccount/Home", wait_until="load", timeout=60000)

            # Wait for login form
            await page.wait_for_selector("#username", timeout=30000)

            # Fill in credentials
            await page.fill("#username", self.barcode)
            await page.fill("#password", self.pin)

            # Check "remember me" if available
            remember_me = await page.query_selector("#rememberMe")
            if remember_me:
                await remember_me.check()

            # Submit form and wait for navigation to complete
            submit_btn = await page.query_selector("#loginFormSubmit")
            if submit_btn:
                async with page.expect_navigation():
                    await submit_btn.click()
            else:
                # Try pressing Enter in the password field
                async with page.expect_navigation():
                    await page.press("#password", "Enter")

            # Wait for page to fully load
            await page.wait_for_load_state("load")
            await page.wait_for_timeout(3000)

            # Check if login was successful
            login_success = False

            # Check for "My Account" in page title
            title = await page.title()
            if "My Account" in title or "Checked Out" in title:
                login_success = True

            # Check for logout link
            if not login_success:
                try:
                    await page.wait_for_selector(
                        "a[href*='Logout'], .logoutLink, #logoutLink",
                        timeout=5000,
                    )
                    login_success = True
                except Exception:
                    pass

            # Check for error message
            if not login_success:
                error = await page.query_selector(".alert-danger, .error, .loginError, .alert-warning")
                if error:
                    error_text = await error.inner_text()
                    if error_text.strip():
                        raise Exception(f"Login failed: {error_text}")

            if login_success:
                # Extract cookies
                cookies = await context.cookies()
                self.cookies = {c["name"]: c["value"] for c in cookies}
                self._save_cookies()

                # Save full browser state for headless reuse
                await self._save_browser_state()

                # Reset HTTP client to use new cookies
                if self._http_client:
                    await self._http_client.aclose()
                    self._http_client = None

                return True

            return False

        finally:
            await page.close()

    async def _verify_session(self) -> bool:
        """Verify that current session cookies are still valid."""
        try:
            resp = await self.http_client.get("/MyAccount/AJAX", params={"method": "getMenuDataIls"})
            if resp.status_code == 200:
                data = resp.json()
                # If we get a valid response with account info, session is valid
                return data.get("success", False) or "numCheckedOut" in str(data)
        except Exception:
            pass
        return False

    async def get_account_summary(self) -> AccountSummary:
        """Get account summary (checkouts, holds, fines, expiration)."""
        resp = await self.http_client.get("/MyAccount/AJAX", params={"method": "getMenuDataIls"})
        resp.raise_for_status()

        data = resp.json()

        # Parse response - the data is nested under "summary" key
        result = AccountSummary()

        if isinstance(data, dict):
            # Data may be nested under "summary" key
            summary = data.get("summary", data)

            result.num_checked_out = int(summary.get("numCheckedOut", 0))
            result.num_overdue = int(summary.get("numOverdue", 0))
            result.num_holds = int(summary.get("numHolds", 0))
            result.num_available_holds = int(summary.get("numAvailableHolds", 0))

            # Fines - might be string like "$5.00" or float
            fines = summary.get("totalFines", summary.get("fines", 0))
            if isinstance(fines, str):
                fines = fines.replace("$", "").replace(",", "")
                try:
                    result.total_fines = float(fines)
                except ValueError:
                    result.total_fines = 0.0
            else:
                result.total_fines = float(fines or 0)

            # Expiration date - format is "Nov 1, 2027"
            exp_str = summary.get("expires", summary.get("expirationDate"))
            if exp_str:
                result.expires = parse_date(exp_str)

            # Name
            result.name = summary.get("name", summary.get("displayName"))

        return result

    async def get_checkouts(self) -> list[Checkout]:
        """Get list of checked out items."""
        resp = await self.http_client.get(
            "/MyAccount/AJAX",
            params={"method": "getCheckouts", "source": "all"},
        )
        resp.raise_for_status()

        data = resp.json()
        checkouts = []

        # Response might have items directly or in an HTML field
        if isinstance(data, dict):
            # Check for direct items array
            items = data.get("checkouts", data.get("items", []))
            if items and isinstance(items, list):
                for item in items:
                    checkouts.append(
                        Checkout(
                            id=str(item.get("id", item.get("recordId", ""))),
                            title=item.get("title", "Unknown"),
                            author=item.get("author"),
                            due_date=parse_date(item.get("dueDate")),
                            format=item.get("format"),
                            can_renew=item.get("canRenew", True),
                            times_renewed=int(item.get("renewCount", 0)),
                            source=item.get("source", "ils"),
                            cover_url=item.get("coverUrl"),
                        )
                    )

            # Check for HTML content to parse
            html_content = data.get("html", data.get("body", ""))
            if html_content and not checkouts:
                checkouts = parse_checkouts_html(html_content)

        return checkouts

    async def get_holds(self) -> list[Hold]:
        """Get list of holds."""
        resp = await self.http_client.get(
            "/MyAccount/AJAX",
            params={"method": "getHolds", "source": "all"},
        )
        resp.raise_for_status()

        data = resp.json()
        holds = []

        if isinstance(data, dict):
            # Check for direct items array
            items = data.get("holds", data.get("items", []))
            if items and isinstance(items, list):
                for item in items:
                    status = "pending"
                    status_str = str(item.get("status", "")).lower()
                    if "available" in status_str or "ready" in status_str:
                        status = "available"
                    elif "transit" in status_str:
                        status = "in_transit"
                    elif "suspend" in status_str or "frozen" in status_str:
                        status = "suspended"

                    holds.append(
                        Hold(
                            id=str(item.get("id", item.get("holdId", ""))),
                            title=item.get("title", "Unknown"),
                            author=item.get("author"),
                            status=status,
                            position=item.get("position"),
                            pickup_location=item.get("pickupLocation"),
                            expiration_date=parse_date(item.get("expirationDate")),
                            is_frozen=item.get("frozen", False),
                            cover_url=item.get("coverUrl"),
                        )
                    )

            # Check for HTML content to parse
            html_content = data.get("html", data.get("body", ""))
            if html_content and not holds:
                holds = parse_holds_html(html_content)

        return holds

    async def search(self, query: str, index: str = "Keyword", limit: int = 20) -> list[SearchResult]:
        """Search the library catalog using browser (needed for Cloudflare bypass)."""
        context = await self._get_browser_context()

        # Apply cookies
        cookies = [
            {"name": k, "value": v, "domain": "catalog.hmcpl.org", "path": "/"}
            for k, v in self.cookies.items()
        ]
        await context.add_cookies(cookies)

        page = await context.new_page()

        try:
            url = f"{BASE_URL}/Search/Results?lookfor={query}&searchIndex={index}&view=list"
            await page.goto(url, wait_until="load")
            await page.wait_for_timeout(3000)

            # Get page content and parse
            content = await page.content()
            results = parse_search_results_html(content)

            return results[:limit]
        finally:
            await page.close()

    async def place_hold(self, record_id: str, pickup_location: str | None = None) -> HoldResult:
        """
        Place a hold on an item. Requires Playwright for form interaction.
        """
        context = await self._get_browser_context()

        # Apply current cookies to the browser context
        cookies = [
            {"name": k, "value": v, "domain": "catalog.hmcpl.org", "path": "/"}
            for k, v in self.cookies.items()
        ]
        await context.add_cookies(cookies)

        page = await context.new_page()

        try:
            # Navigate to hold page
            await page.goto(f"{BASE_URL}/Record/{record_id}/Hold", wait_until="load")

            # Select pickup location if specified
            if pickup_location:
                location_select = await page.query_selector("select#pickupBranch, select[name='pickupBranch']")
                if location_select:
                    # Find matching option
                    options = await location_select.query_selector_all("option")
                    for option in options:
                        text = await option.inner_text()
                        if pickup_location.lower() in text.lower():
                            value = await option.get_attribute("value")
                            await location_select.select_option(value)
                            break

            # Submit the hold form
            submit_btn = await page.query_selector(
                "input[type='submit'][value*='Hold'], button[type='submit'], .placeHold"
            )
            if submit_btn:
                await submit_btn.click()
                await page.wait_for_load_state("load")

            # Check for success/error message
            success_elem = await page.query_selector(".alert-success, .success, .holdConfirmation")
            error_elem = await page.query_selector(".alert-danger, .error, .holdError")

            if success_elem:
                msg = await success_elem.inner_text()
                return HoldResult(success=True, message=msg.strip())
            elif error_elem:
                msg = await error_elem.inner_text()
                return HoldResult(success=False, message=msg.strip())
            else:
                return HoldResult(success=False, message="Unknown result - please check your holds")

        finally:
            await page.close()

    async def renew_item(self, item_id: str) -> RenewResult:
        """Renew a specific checked out item."""
        # Try AJAX renewal first
        resp = await self.http_client.post(
            "/MyAccount/AJAX",
            data={
                "method": "renewItem",
                "itemId": item_id,
                "itemBarcode": item_id,
            },
        )

        if resp.status_code == 200:
            try:
                data = resp.json()
                success = data.get("success", False)
                message = data.get("message", "")
                new_due = parse_date(data.get("newDueDate"))
                return RenewResult(success=success, message=message, new_due_date=new_due)
            except Exception:
                pass

        # If AJAX didn't work, return failure
        return RenewResult(success=False, message="Renewal failed - please try through the website")

    async def renew_all(self) -> list[RenewResult]:
        """Renew all eligible items."""
        checkouts = await self.get_checkouts()
        results = []

        for checkout in checkouts:
            if checkout.can_renew:
                result = await self.renew_item(checkout.id)
                results.append(result)

        return results

    async def get_pickup_locations(self) -> list[str]:
        """Get list of available pickup locations."""
        # Try to get from a hold page
        context = await self._get_browser_context()

        # Apply cookies
        cookies = [
            {"name": k, "value": v, "domain": "catalog.hmcpl.org", "path": "/"}
            for k, v in self.cookies.items()
        ]
        await context.add_cookies(cookies)

        page = await context.new_page()

        try:
            # Navigate to search results to find a holdable item
            await page.goto(f"{BASE_URL}/Search/Results?lookfor=test", wait_until="load")
            await page.wait_for_timeout(3000)

            # Find first hold link
            hold_link = await page.query_selector("a[href*='/Hold']")
            if hold_link:
                href = await hold_link.get_attribute("href")
                await page.goto(f"{BASE_URL}{href}", wait_until="load")

                # Get locations from dropdown
                location_select = await page.query_selector("select#pickupBranch, select[name='pickupBranch']")
                if location_select:
                    options = await location_select.query_selector_all("option")
                    locations = []
                    for option in options:
                        text = await option.inner_text()
                        if text.strip() and text.strip() != "Select a location":
                            locations.append(text.strip())
                    return locations

        finally:
            await page.close()

        return []


async def create_client(
    barcode: str | None = None,
    pin: str | None = None,
    headless: bool = False,
) -> HMCPLClient:
    """Create and login a client, reading credentials from env if not provided."""
    import os
    from dotenv import load_dotenv

    load_dotenv()

    barcode = barcode or os.getenv("HMCPL_BARCODE")
    pin = pin or os.getenv("HMCPL_PIN")

    if not barcode or not pin:
        raise ValueError("HMCPL_BARCODE and HMCPL_PIN must be set")

    client = HMCPLClient(barcode, pin, headless=headless)
    if not await client.login():
        raise Exception("Failed to login to HMCPL")

    return client
