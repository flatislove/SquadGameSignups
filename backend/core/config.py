import os
from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    BOT_TOKEN: str
    BOT_USERNAME: str
    SUPABASE_URL: str
    SUPABASE_SERVICE_KEY: str
    ALLOWED_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"
    TIMEZONE: str = "Asia/Tashkent"

    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",") if origin.strip()]

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
