from fastapi import APIRouter, Depends
from backend.core.auth import get_current_user

router = APIRouter(prefix="/api/me", tags=["me"])

@router.get("/context")
async def get_my_context(user: dict = Depends(get_current_user)):
    """Returns user info and context for Two-Entry Web App."""
    return {
        "id": user.get("id"),
        "first_name": user.get("first_name"),
        "username": user.get("username")
    }

def register_all_routers(app):
    app.include_router(router)
    from backend.modules.groups.api import router as groups_router
    from backend.modules.announcements.api import router as announcements_router
    from backend.modules.signups.api import router as signups_router
    from backend.modules.payments.api import router as payments_router
    from backend.modules.venues.api import router as venues_router

    app.include_router(groups_router)
    app.include_router(announcements_router)
    app.include_router(signups_router)
    app.include_router(payments_router)
    app.include_router(venues_router)

