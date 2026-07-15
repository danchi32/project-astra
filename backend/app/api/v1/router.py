from fastapi import APIRouter

from app.api.v1 import (
    agent,
    assets,
    audit,
    auth,
    billing,
    conversations,
    devices,
    downloads,
    knowledge,
    notifications,
    platform,
    remediation,
    reports,
    settings,
    telemetry,
    users,
)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(devices.router)
api_router.include_router(assets.router)
api_router.include_router(agent.router)
api_router.include_router(telemetry.router)
api_router.include_router(conversations.router)
api_router.include_router(remediation.router)
api_router.include_router(knowledge.router)
api_router.include_router(audit.router)
api_router.include_router(reports.router)
api_router.include_router(notifications.router)
api_router.include_router(settings.router)
api_router.include_router(downloads.router)
api_router.include_router(platform.router)
api_router.include_router(billing.router)
