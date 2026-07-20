import uuid

from pydantic import BaseModel, Field


class LocationRead(BaseModel):
    id: uuid.UUID
    name: str
    asset_count: int = 0


class LocationCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class LocationUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
