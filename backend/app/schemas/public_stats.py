from datetime import datetime

from pydantic import BaseModel, Field


class PublicStats(BaseModel):
    """Aggregate counts for the marketing site's homepage.

    Counts only. No organisation names, no device names, no per-organisation breakdown —
    nothing here can identify a customer, which is what makes it safe to serve to anyone
    who asks. It replaces four invented figures that had been sitting in the hero since
    before there was anything real to put there.
    """

    organizations: int = Field(description="Customer organisations, excluding our own.")
    devices: int = Field(description="Managed devices across every customer organisation.")
    devices_online: int = Field(
        description="Devices that have reported in recently. A liveness figure, not a "
                    "reliability claim — do not present it as uptime."
    )
    remediations: int = Field(
        description="Remediation tasks that have completed successfully, all time."
    )
    #: So the site can say how fresh the numbers are, and so a stale cache is visible
    #: rather than silently wrong.
    generated_at: datetime
