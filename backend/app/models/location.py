import uuid

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import GUID, Base, TimestampMixin


class Location(TimestampMixin, Base):
    """A managed site/location for an organization (HQ, Warehouse-2, …). Assets store the
    location NAME (denormalized) so reports group by it directly; renaming a location
    cascades to its assets."""

    __tablename__ = "locations"
    __table_args__ = (UniqueConstraint("org_id", "name", name="uq_locations_org_name"),)

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
