from apscheduler.schedulers.asyncio import AsyncIOScheduler
from backend.core.config import settings
import logging

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler(timezone=settings.TIMEZONE)

def init_scheduler():
    if not scheduler.running:
        scheduler.start()
        logger.info("✅ APScheduler started successfully.")
