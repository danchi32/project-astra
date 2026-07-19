import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models import AcknowledgementStatus, AssetCategory, AssetStatus


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
    pass


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


class AssetRead(AssetBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    org_id: uuid.UUID
    acknowledgement_status: AcknowledgementStatus = AcknowledgementStatus.NOT_REQUIRED
    acknowledged_at: datetime | None = None
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
