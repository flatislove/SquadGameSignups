from supabase import create_client, Client
from backend.core.config import settings
import logging

logger = logging.getLogger(__name__)

class SupabaseManager:
    client: Client = None

db_manager = SupabaseManager()

def init_db():
    try:
        db_manager.client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)
        logger.info("✅ Supabase client initialized successfully.")
    except Exception as e:
        logger.error(f"❌ Failed to initialize Supabase client: {e}")
        raise

def get_db() -> Client:
    if not db_manager.client:
        init_db()
    return db_manager.client
