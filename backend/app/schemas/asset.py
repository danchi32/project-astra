import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models import AcknowledgementStatus, AssetCategory, AssetStatus


def _date_or_none(v: str | None) -> str | None:
    """Dates are stored as YYYY-MM-DD text, so they are checked on the way in: one that does
    not parse would break every reader that compares or parses it (the Watchlist, warranty
    buckets). Day-first input is normalised. Only on create/update, never on read, so a bad
    value already in the database cannot make the asset list fail."""
    if v is None or not str(v).strip():
        return None
    from app.services.warranty import parse_date

    return parse_date(str(v))


class AssetBase(BaseModel):
    asset_tag: str | None = Field(default=None, max_length=60)
    name: str = Field(min_length=1, max_length=200)
    category: AssetCategory = AssetCategory.OTHER
    status: AssetStatus = AssetStatus.IN_USE
    assigned_to_user_id: uuid.UUID | None = None
    device_id: uuid.UUID | None = None
    manufacturer: str | None = Field(default=None, max_length=150)
    model: str | None = Field(default=None, max_length=150)
    serial_number: str | None = Field(default=None, max_length=150)
    location: str | None = Field(default=None, max_length=200)
    purchase_date: str | None = Field(default=None, max_length=10)
    warranty_expiry: str | None = Field(default=None, max_length=10)
    purchase_cost: float | None = Field(default=None, ge=0)
    notes: str | None = Field(default=None, max_length=2000)


class AssetCreate(AssetBase):
    _dates = field_validator("purchase_date", "warranty_expiry")(_date_or_none)


class AssetUpdate(BaseModel):
    """All fields optional — only the provided ones are changed."""

    asset_tag: str | None = Field(default=None, max_length=60)
    name: str | None = Field(default=None, min_length=1, max_length=200)
    category: AssetCategory | None = None
    status: AssetStatus | None = None
    assigned_to_user_id: uuid.UUID | None = None
    device_id: uuid.UUID | None = None
    manufacturer: str | None = Field(default=None, max_length=150)
    model: str | None = Field(default=None, max_length=150)
    serial_number: str | None = Field(default=None, max_length=150)
    location: str | None = Field(default=None, max_length=200)
    purchase_date: str | None = Field(default=None, max_length=10)
    warranty_expiry: str | None = Field(default=None, max_length=10)
    purchase_cost: float | None = Field(default=None, ge=0)
    notes: str | None = Field(default=None, max_length=2000)

    _dates = field_validator("purchase_date", "warranty_expiry")(_date_or_none)


class AssetRead(AssetBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    org_id: uuid.UUID
    acknowledgement_status: AcknowledgementStatus = AcknowledgementStatus.NOT_REQUIRED
    acknowledged_at: datetime | None = None
    archived_at: datetime | None = None
    # L5b warranty provenance (read-only: set by edits, imports and lookups, never posted).
    warranty_source: str | None = None
    warranty_checked_at: datetime | None = None
    warranty_found: str | None = None
    warranty_found_source: str | None = None
    # Enriched for display (not stored on the row).
    assigned_to_name: str | None = None
    device_hostname: str | None = None
    created_at: datetime
    updated_at: datetime


class AssetSummary(BaseModel):
    total: int
    by_status: dict[str, int]
    by_category: dict[str, int]
    total_value: float
    warranty_expiring_soon: int
