"""Pydantic models for HMCPL library data."""

from datetime import date as Date
from pydantic import BaseModel


class AccountSummary(BaseModel):
    """Summary of library account status."""

    num_checked_out: int = 0
    num_overdue: int = 0
    num_holds: int = 0
    num_available_holds: int = 0
    total_fines: float = 0.0
    expires: Date | None = None
    name: str | None = None


class Checkout(BaseModel):
    """A checked out library item."""

    id: str
    title: str
    author: str | None = None
    due_date: Date | None = None
    format: str | None = None
    can_renew: bool = True
    times_renewed: int = 0
    source: str = "ils"  # "ils", "overdrive", "hoopla", etc.
    cover_url: str | None = None


class Hold(BaseModel):
    """A hold on a library item."""

    id: str
    title: str
    author: str | None = None
    status: str = "pending"  # "pending", "available", "in_transit", "suspended"
    position: int | None = None
    pickup_location: str | None = None
    expiration_date: Date | None = None
    available_date: Date | None = None
    format: str | None = None
    cover_url: str | None = None
    freeze_until: Date | None = None
    is_frozen: bool = False


class SearchResult(BaseModel):
    """A search result from the catalog."""

    id: str
    title: str
    author: str | None = None
    format: str | None = None
    publication_year: int | None = None
    availability: str | None = None
    cover_url: str | None = None
    description: str | None = None


class Fine(BaseModel):
    """A fine or fee on the account."""

    id: str | None = None
    title: str | None = None
    amount: float
    date: Date | None = None
    reason: str | None = None


class HoldResult(BaseModel):
    """Result of placing a hold."""

    success: bool
    message: str
    hold_id: str | None = None


class RenewResult(BaseModel):
    """Result of renewing an item."""

    success: bool
    message: str
    new_due_date: Date | None = None
