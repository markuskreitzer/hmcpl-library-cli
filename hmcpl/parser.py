"""HTML parsing utilities for HMCPL AJAX responses."""

import re
from datetime import date, datetime
from bs4 import BeautifulSoup

from hmcpl.models import Checkout, Hold, SearchResult


def parse_date(date_str: str | None) -> date | None:
    """Parse various date formats from HMCPL."""
    if not date_str:
        return None

    date_str = date_str.strip()

    # Try common formats
    formats = [
        "%m/%d/%Y",  # 02/15/2026
        "%m-%d-%Y",  # 02-15-2026
        "%Y-%m-%d",  # 2026-02-15
        "%B %d, %Y",  # February 15, 2026
        "%b %d, %Y",  # Feb 15, 2026
        "%b. %d, %Y",  # Feb. 15, 2026
    ]

    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue

    return None


def parse_checkouts_html(html: str) -> list[Checkout]:
    """Parse checkouts from the AJAX response HTML."""
    soup = BeautifulSoup(html, "lxml")
    checkouts = []

    # Look for checkout rows - they're typically in a table or list structure
    rows = soup.select(".checkoutEntry, .ilsCheckoutEntry, tr.checkout-row, .result")

    for row in rows:
        try:
            # Extract item ID from data attributes or hidden inputs
            item_id = None
            id_elem = row.select_one("[data-id], [data-recordid], input[name*='id']")
            if id_elem:
                item_id = id_elem.get("data-id") or id_elem.get("data-recordid") or id_elem.get("value")

            # Try alternate ID sources
            if not item_id:
                checkbox = row.select_one("input[type='checkbox'][name*='selected']")
                if checkbox:
                    item_id = checkbox.get("value") or checkbox.get("id")

            if not item_id:
                # Generate ID from row position
                item_id = f"checkout-{len(checkouts)}"

            # Extract title
            title_elem = row.select_one(".title, .result-title, a.title, h3, h4")
            title = title_elem.get_text(strip=True) if title_elem else "Unknown Title"

            # Extract author
            author_elem = row.select_one(".author, .result-author, .by")
            author = author_elem.get_text(strip=True) if author_elem else None
            if author and author.lower().startswith("by "):
                author = author[3:]

            # Extract due date
            due_date = None
            due_elem = row.select_one(".dueDate, .due-date, .status, [data-due]")
            if due_elem:
                due_text = due_elem.get("data-due") or due_elem.get_text(strip=True)
                # Extract date from text like "Due: 02/15/2026" or "Due 02/15/2026"
                date_match = re.search(r"(\d{1,2}[/-]\d{1,2}[/-]\d{4})", due_text)
                if date_match:
                    due_date = parse_date(date_match.group(1))

            # Extract format
            format_elem = row.select_one(".format, .itemType, .material-type")
            item_format = format_elem.get_text(strip=True) if format_elem else None

            # Check if renewable
            can_renew = True
            renew_elem = row.select_one(".renewOption, button.renew, input.renew")
            if renew_elem:
                if renew_elem.get("disabled") or "disabled" in renew_elem.get("class", []):
                    can_renew = False
            no_renew_msg = row.select_one(".noRenew, .cannot-renew")
            if no_renew_msg:
                can_renew = False

            # Extract cover image
            cover_elem = row.select_one("img.cover, img.bookcover, img[src*='cover']")
            cover_url = cover_elem.get("src") if cover_elem else None

            checkouts.append(
                Checkout(
                    id=item_id,
                    title=title,
                    author=author,
                    due_date=due_date,
                    format=item_format,
                    can_renew=can_renew,
                    cover_url=cover_url,
                )
            )
        except Exception:
            continue

    return checkouts


def parse_holds_html(html: str) -> list[Hold]:
    """Parse holds from the AJAX response HTML."""
    soup = BeautifulSoup(html, "lxml")
    holds = []

    rows = soup.select(".holdEntry, .ilsHoldEntry, tr.hold-row, .result")

    for row in rows:
        try:
            # Extract hold ID
            hold_id = None
            id_elem = row.select_one("[data-id], [data-holdid], input[name*='id']")
            if id_elem:
                hold_id = id_elem.get("data-id") or id_elem.get("data-holdid") or id_elem.get("value")

            if not hold_id:
                checkbox = row.select_one("input[type='checkbox'][name*='selected']")
                if checkbox:
                    hold_id = checkbox.get("value") or checkbox.get("id")

            if not hold_id:
                hold_id = f"hold-{len(holds)}"

            # Extract title
            title_elem = row.select_one(".title, .result-title, a.title, h3, h4")
            title = title_elem.get_text(strip=True) if title_elem else "Unknown Title"

            # Extract author
            author_elem = row.select_one(".author, .result-author, .by")
            author = author_elem.get_text(strip=True) if author_elem else None
            if author and author.lower().startswith("by "):
                author = author[3:]

            # Extract status
            status = "pending"
            status_elem = row.select_one(".status, .holdStatus, .hold-status")
            if status_elem:
                status_text = status_elem.get_text(strip=True).lower()
                if "available" in status_text or "ready" in status_text:
                    status = "available"
                elif "transit" in status_text:
                    status = "in_transit"
                elif "suspend" in status_text or "frozen" in status_text:
                    status = "suspended"

            # Extract position
            position = None
            pos_elem = row.select_one(".holdPosition, .position, .queue")
            if pos_elem:
                pos_text = pos_elem.get_text(strip=True)
                pos_match = re.search(r"(\d+)", pos_text)
                if pos_match:
                    position = int(pos_match.group(1))

            # Extract pickup location
            pickup_elem = row.select_one(".pickupLocation, .pickup, .location")
            pickup_location = pickup_elem.get_text(strip=True) if pickup_elem else None

            # Extract expiration
            exp_date = None
            exp_elem = row.select_one(".expirationDate, .expires, .expiration")
            if exp_elem:
                exp_text = exp_elem.get_text(strip=True)
                date_match = re.search(r"(\d{1,2}[/-]\d{1,2}[/-]\d{4})", exp_text)
                if date_match:
                    exp_date = parse_date(date_match.group(1))

            # Check if frozen
            is_frozen = "suspend" in status or "frozen" in status
            frozen_elem = row.select_one(".frozen, .suspended, input[name*='freeze']:checked")
            if frozen_elem:
                is_frozen = True

            # Extract cover image
            cover_elem = row.select_one("img.cover, img.bookcover, img[src*='cover']")
            cover_url = cover_elem.get("src") if cover_elem else None

            holds.append(
                Hold(
                    id=hold_id,
                    title=title,
                    author=author,
                    status=status,
                    position=position,
                    pickup_location=pickup_location,
                    expiration_date=exp_date,
                    is_frozen=is_frozen,
                    cover_url=cover_url,
                )
            )
        except Exception:
            continue

    return holds


def parse_search_results_html(html: str) -> list[SearchResult]:
    """Parse search results from Aspen Discovery HTML."""
    soup = BeautifulSoup(html, "lxml")
    results = []

    # Aspen Discovery uses .resultsList class for each result
    # Avoid .result as it may match other elements
    rows = soup.select(".resultsList")

    for row in rows:
        try:
            # Extract record ID from grouped record ID or link
            record_id = None

            # Try id attribute like groupedRecord05c295dd-...
            row_id = row.get("id", "")
            if row_id.startswith("groupedRecord"):
                record_id = row_id.replace("groupedRecord", "")

            # Try to get from title link
            if not record_id:
                link = row.select_one("a.result-title, a[href*='/GroupedWork/'], a[href*='/Record/'], a[href*='/Hoopla/'], a[href*='/OverDrive/']")
                if link:
                    href = link.get("href", "")
                    # Match patterns like /Hoopla/16744279 or /GroupedWork/abc123
                    id_match = re.search(r"/(GroupedWork|Record|Hoopla|OverDrive)/([^/?]+)", href)
                    if id_match:
                        record_id = id_match.group(2)

            if not record_id:
                record_id = f"result-{len(results)}"

            # Extract title from .result-title
            title_elem = row.select_one(".result-title, a.result-title")
            title = title_elem.get_text(strip=True) if title_elem else "Unknown Title"

            # Extract author - look for result-value after "Author" label
            author = None
            labels = row.select(".result-label")
            for label in labels:
                label_text = label.get_text(strip=True).lower()
                if "author" in label_text:
                    # Get the next sibling result-value
                    value = label.find_next_sibling(class_="result-value")
                    if value:
                        author = value.get_text(strip=True)
                        break

            # Try alternate author location
            if not author:
                author_elem = row.select_one(".result-author, .author a")
                if author_elem:
                    author = author_elem.get_text(strip=True)

            # Extract format from manifestation section
            format_elem = row.select_one(".manifestation-format, .formatCategory, .format-category")
            item_format = None
            if format_elem:
                item_format = format_elem.get_text(strip=True)
                # Clean up format text
                item_format = re.sub(r"Show Edition.*", "", item_format).strip()
                if not item_format:
                    item_format = None

            # Extract publication year from result values
            pub_year = None
            for label in labels:
                label_text = label.get_text(strip=True).lower()
                if "pub" in label_text or "year" in label_text:
                    value = label.find_next_sibling(class_="result-value")
                    if value:
                        year_match = re.search(r"(\d{4})", value.get_text())
                        if year_match:
                            pub_year = int(year_match.group(1))
                            break

            # Extract availability from status labels
            avail_elem = row.select_one(".related-manifestation-shelf-status, .status-available, .availability")
            availability = avail_elem.get_text(strip=True) if avail_elem else None

            # Extract cover image - look for img with bookcover in src
            cover_elem = row.select_one("img[src*='bookcover'], img.use-original-covers")
            cover_url = cover_elem.get("src") if cover_elem else None

            results.append(
                SearchResult(
                    id=record_id,
                    title=title,
                    author=author,
                    format=item_format,
                    publication_year=pub_year,
                    availability=availability,
                    cover_url=cover_url,
                )
            )
        except Exception:
            continue

    return results


def parse_account_summary_page(html: str) -> dict:
    """Parse account summary from rendered MyAccount/Home page."""
    soup = BeautifulSoup(html, "lxml")
    result = {}

    # Extract name from header area
    name_elem = soup.select_one("span.menu-bar-label, .displayNameLink, #displayNameLink")
    if name_elem:
        name = name_elem.get_text(strip=True)
        if name:
            result["name"] = name

    # Extract summary counts from the account summary section
    # Look for dashboard widgets with specific IDs or classes
    body_text = soup.get_text()

    # Parse "CHECKED OUT TITLES" count
    for pattern, key in [
        (r"CHECKED OUT TITLES\s*(\d+)", "numCheckedOut"),
        (r"OVERDUE\s*(\d+)", "numOverdue"),
        (r"TITLES ON HOLD\s*(\d+)", "numHolds"),
        (r"READY FOR PICKUP\s*(\d+)", "numAvailableHolds"),
    ]:
        match = re.search(pattern, body_text, re.IGNORECASE)
        if match:
            result[key] = int(match.group(1))

    # Extract fines from sidebar: "Fees $0.00"
    fines_match = re.search(r"Fees?\s*\$?([\d,.]+)", body_text)
    if fines_match:
        try:
            result["totalFines"] = float(fines_match.group(1).replace(",", ""))
        except ValueError:
            pass

    # Extract expiration date if shown
    exp_match = re.search(r"(?:expires?|expiration)\s*[:.]?\s*(\w+ \d{1,2},?\s*\d{4})", body_text, re.IGNORECASE)
    if exp_match:
        result["expires"] = exp_match.group(1)

    return result


def parse_checkouts_page(html: str) -> list[Checkout]:
    """Parse checkouts from rendered MyAccount/CheckedOut full page."""
    soup = BeautifulSoup(html, "lxml")
    checkouts = []

    # Aspen Discovery uses specific classes for checkout entries
    rows = soup.select(".result, .listEntry, .ilsCheckoutEntry, .checkoutEntry")

    for row in rows:
        try:
            # Extract item ID
            item_id = None
            # Look for data attributes
            item_id = row.get("data-id") or row.get("id", "")
            if not item_id or item_id.startswith("listEntry"):
                id_elem = row.select_one("input[name*='selected'], input[type='checkbox']")
                if id_elem:
                    item_id = id_elem.get("value") or id_elem.get("name", "").split("|")[-1]
            if not item_id:
                item_id = f"checkout-{len(checkouts)}"

            # Extract title
            title_elem = row.select_one(".result-title, a.result-title, .title a, .title")
            title = title_elem.get_text(strip=True) if title_elem else "Unknown Title"

            # Extract author
            author = None
            labels = row.select(".result-label")
            for label in labels:
                if "author" in label.get_text(strip=True).lower():
                    value = label.find_next_sibling(class_="result-value")
                    if value:
                        author = value.get_text(strip=True)
                        break
            if not author:
                author_elem = row.select_one(".result-author, .author")
                if author_elem:
                    author = author_elem.get_text(strip=True)
            if author and author.lower().startswith("by "):
                author = author[3:]

            # Extract due date
            due_date = None
            for label in labels:
                label_text = label.get_text(strip=True).lower()
                if "due" in label_text:
                    value = label.find_next_sibling(class_="result-value")
                    if value:
                        date_match = re.search(r"(\d{1,2}[/-]\d{1,2}[/-]\d{4})", value.get_text())
                        if date_match:
                            due_date = parse_date(date_match.group(1))
                        else:
                            # Try "Month Day, Year" format
                            due_date = parse_date(value.get_text(strip=True))
                        break
            if not due_date:
                due_elem = row.select_one(".dueDate, .due-date")
                if due_elem:
                    date_match = re.search(r"(\d{1,2}[/-]\d{1,2}[/-]\d{4})", due_elem.get_text())
                    if date_match:
                        due_date = parse_date(date_match.group(1))

            # Extract format
            format_elem = row.select_one(".format, .itemType, .material-type, .manifestation-format")
            item_format = format_elem.get_text(strip=True) if format_elem else None

            # Check if renewable
            can_renew = True
            renew_btn = row.select_one("button.renewButton, .renewOption, a.renewButton")
            if renew_btn and renew_btn.get("disabled"):
                can_renew = False
            no_renew = row.select_one(".noRenew, .cannot-renew")
            if no_renew:
                can_renew = False

            # Cover image
            cover_elem = row.select_one("img[src*='bookcover'], img.use-original-covers")
            cover_url = cover_elem.get("src") if cover_elem else None

            checkouts.append(
                Checkout(
                    id=item_id,
                    title=title,
                    author=author,
                    due_date=due_date,
                    format=item_format,
                    can_renew=can_renew,
                    cover_url=cover_url,
                )
            )
        except Exception:
            continue

    return checkouts


def parse_holds_page(html: str) -> list[Hold]:
    """Parse holds from rendered MyAccount/Holds full page."""
    soup = BeautifulSoup(html, "lxml")
    holds = []

    rows = soup.select(".result, .listEntry, .ilsHoldEntry, .holdEntry")

    for row in rows:
        try:
            hold_id = None
            hold_id = row.get("data-id") or row.get("id", "")
            if not hold_id or hold_id.startswith("listEntry"):
                id_elem = row.select_one("input[name*='selected'], input[type='checkbox']")
                if id_elem:
                    hold_id = id_elem.get("value") or id_elem.get("name", "").split("|")[-1]
            if not hold_id:
                hold_id = f"hold-{len(holds)}"

            title_elem = row.select_one(".result-title, a.result-title, .title a, .title")
            title = title_elem.get_text(strip=True) if title_elem else "Unknown Title"

            author = None
            labels = row.select(".result-label")
            for label in labels:
                label_text = label.get_text(strip=True).lower()
                if "author" in label_text:
                    value = label.find_next_sibling(class_="result-value")
                    if value:
                        author = value.get_text(strip=True)
                        break
            if not author:
                author_elem = row.select_one(".result-author, .author")
                if author_elem:
                    author = author_elem.get_text(strip=True)
            if author and author.lower().startswith("by "):
                author = author[3:]

            status = "pending"
            for label in labels:
                label_text = label.get_text(strip=True).lower()
                if "status" in label_text:
                    value = label.find_next_sibling(class_="result-value")
                    if value:
                        status_text = value.get_text(strip=True).lower()
                        if "available" in status_text or "ready" in status_text:
                            status = "available"
                        elif "transit" in status_text:
                            status = "in_transit"
                        elif "suspend" in status_text or "frozen" in status_text:
                            status = "suspended"
                        elif "expired" in status_text:
                            status = "expired"
                    break

            position = None
            for label in labels:
                label_text = label.get_text(strip=True).lower()
                if "position" in label_text or "queue" in label_text:
                    value = label.find_next_sibling(class_="result-value")
                    if value:
                        pos_match = re.search(r"(\d+)", value.get_text())
                        if pos_match:
                            position = int(pos_match.group(1))
                    break

            pickup_location = None
            pickup_elem = row.select_one(".pickupLocation, .pickup, .location")
            if pickup_elem:
                pickup_location = pickup_elem.get_text(strip=True)
            if not pickup_location:
                for label in labels:
                    label_text = label.get_text(strip=True).lower()
                    if "pickup" in label_text or "location" in label_text:
                        value = label.find_next_sibling(class_="result-value")
                        if value:
                            pickup_location = value.get_text(strip=True)
                            break

            exp_date = None
            exp_elem = row.select_one(".expirationDate, .expires, .expiration")
            if exp_elem:
                exp_text = exp_elem.get_text(strip=True)
                date_match = re.search(r"(\d{1,2}[/-]\d{1,2}[/-]\d{4})", exp_text)
                if date_match:
                    exp_date = parse_date(date_match.group(1))
            if not exp_date:
                for label in labels:
                    label_text = label.get_text(strip=True).lower()
                    if "expire" in label_text or "expiration" in label_text:
                        value = label.find_next_sibling(class_="result-value")
                        if value:
                            date_match = re.search(r"(\d{1,2}[/-]\d{1,2}[/-]\d{4})", value.get_text())
                            if date_match:
                                exp_date = parse_date(date_match.group(1))
                            else:
                                exp_date = parse_date(value.get_text(strip=True))
                            break

            is_frozen = "suspend" in status or "frozen" in status
            frozen_elem = row.select_one(".frozen, .suspended, input[name*='freeze']:checked")
            if frozen_elem:
                is_frozen = True

            cover_elem = row.select_one("img[src*='bookcover'], img.use-original-covers")
            cover_url = cover_elem.get("src") if cover_elem else None

            holds.append(
                Hold(
                    id=hold_id,
                    title=title,
                    author=author,
                    status=status,
                    position=position,
                    pickup_location=pickup_location,
                    expiration_date=exp_date,
                    is_frozen=is_frozen,
                    cover_url=cover_url,
                )
            )
        except Exception:
            continue

    return holds


def extract_csrf_token(html: str) -> str | None:
    """Extract CSRF token from page HTML."""
    soup = BeautifulSoup(html, "lxml")

    # Try various common CSRF token locations
    token_elem = soup.select_one(
        "input[name='csrf'], input[name='_token'], "
        "input[name='CSRFToken'], meta[name='csrf-token']"
    )

    if token_elem:
        return token_elem.get("value") or token_elem.get("content")

    return None
