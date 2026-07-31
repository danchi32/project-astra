"""One page shape, and one way to produce it.

Every list endpoint used to return its whole table. That is fine at demo scale and wrong at
fleet scale: an org with 2,000 devices has tens of thousands of audit rows, and the portal was
asking for all of them on every visit, holding them all in memory, and rendering them all.

The shape matches DevicePage, which already existed — deliberately, so the portal has one
contract to code against rather than one per endpoint.
"""
import math
from typing import Generic, Sequence, TypeVar

from pydantic import BaseModel
from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

T = TypeVar("T")

# An upper bound on page_size. Present so a caller that genuinely wants everything (an export,
# a lookup) can say so explicitly and still be bounded — "no limit" is how a single request
# ends up trying to serialise a million rows.
MAX_PAGE_SIZE = 10_000
DEFAULT_PAGE_SIZE = 50


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
    pages: int


def clamp(page: int, page_size: int) -> tuple[int, int]:
    """Page numbers arrive from a URL, so they arrive wrong sometimes. Clamped rather than
    rejected: a 422 on `?page=0` would break the page for a user who did nothing but edit
    the address bar."""
    return max(1, page), min(max(1, page_size), MAX_PAGE_SIZE)


def build(items: Sequence[T], total: int, page: int, page_size: int) -> Page[T]:
    return Page[T](
        items=list(items),
        total=total,
        page=page,
        page_size=page_size,
        # Always at least 1 so "Page 1 of 0" never appears on an empty list.
        pages=max(1, math.ceil(total / page_size)) if total else 1,
    )


async def paginate(
    session: AsyncSession,
    stmt: Select,
    *,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> tuple[list, int, int, int]:
    """Run `stmt` for one page and count the whole match. Returns (rows, total, page, size).

    The count is derived from the same statement with its ordering dropped — ORDER BY in a
    subquery is both pointless and, on some backends, an error.
    """
    page, page_size = clamp(page, page_size)
    total = await session.scalar(
        select(func.count()).select_from(stmt.order_by(None).subquery())
    )
    total = int(total or 0)
    result = await session.execute(stmt.offset((page - 1) * page_size).limit(page_size))
    return list(result.scalars().all()), total, page, page_size
