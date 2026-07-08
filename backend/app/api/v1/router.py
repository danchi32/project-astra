from fastapi import APIRouter

from app.api.v1 import agent, auth, conversations, devices, telemetry, users

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(devices.router)
api_router.include_router(agent.router)
api_router.include_router(telemetry.router)
api_router.include_router(conversations.router)
