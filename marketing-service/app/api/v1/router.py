from fastapi import APIRouter

from app.api.v1 import content, leads

api_router = APIRouter()
api_router.include_router(leads.router)
api_router.include_router(content.router)
