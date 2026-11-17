import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import GUID, Base, TimestampMixin


class DeviceBitLockerKey(TimestampMixin, Base):
    """A BitLocker recovery password escrowed from a device, so an admin can unlock the drive
    when a PC asks for its key (the same job Intune does for managed devices).

    The password is a credential: it is stored encrypted with the platform key
    (`app.core.crypto`), never returned by a list, and decrypted only by an explicit admin
    reveal, which is audited. `protector_id` is the key's ID, shown on the BitLocker recovery
    screen, so the admin can match the right key to the right PC."""

    __tablename__ = "device_bitlocker_keys"
    __table_args__ = (
        UniqueConstraint("device_id", "drive", "protector_id", name="uq_device_bitlocker_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    device_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True
    )
    org_id: Mapped[uuid.UUID] = mapped_column(GUID, nullable=False, index=True)
    drive: Mapped[str] = mapped_column(String(2), nullable=False)          # "C:"
    protector_id: Mapped[str] = mapped_column(String(60), nullable=False)  # the key's GUID
    recovery_password_enc: Mapped[str] = mapped_column(Text, nullable=False)
    escrowed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
