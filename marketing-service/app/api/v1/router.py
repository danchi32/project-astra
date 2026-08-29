from fastapi import APIRouter

from app.api.v1 import content, leads, telegram

api_router = APIRouter()
api_router.include_router(leads.router)
api_router.include_router(content.router)
api_router.include_router(telegram.router)
