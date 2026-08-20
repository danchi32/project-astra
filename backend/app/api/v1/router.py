from fastapi import APIRouter

from app.api.v1 import (
    agent,
    assets,
    audit,
    auth,
    billing,
    compliance,
    conversations,
    devices,
    downloads,
    fleet,
    help_centre,
    knowledge,
    locations,
    notifications,
    platform,
    public,
    remediation,
    reports,
    settings,
    support,
    telemetry,
    users,
)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(devices.router)
api_router.include_router(assets.router)
api_router.include_router(compliance.router)
api_router.include_router(fleet.router)
api_router.include_router(agent.router)
api_router.include_router(telemetry.router)
api_router.include_router(conversations.router)
api_router.include_router(remediation.router)
api_router.include_router(knowledge.router)
api_router.include_router(help_centre.router)
api_router.include_router(public.router)
api_router.include_router(support.router)
api_router.include_router(locations.router)
api_router.include_router(audit.router)
api_router.include_router(reports.router)
api_router.include_router(notifications.router)
api_router.include_router(settings.router)
api_router.include_router(downloads.router)
api_router.include_router(platform.router)
api_router.include_router(billing.router)
