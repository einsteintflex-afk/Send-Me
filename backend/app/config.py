from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    env: str = "development"  # development | production | test
    database_url: str = "sqlite:///./sendme.db"
    jwt_secret: str = "dev-only-change-me"
    access_token_minutes: int = 60
    refresh_token_days: int = 14
    frontend_url: str = "http://localhost:3000"
    cors_origins: str = "http://localhost:3000"
    upload_dir: str = "./uploads"
    max_upload_bytes: int = 2_000_000
    email_backend: str = "console"  # console | smtp (smtp not yet implemented)
    # Paystack. Leave empty until you have keys; payments then return 503.
    paystack_secret_key: str = ""
    paystack_base_url: str = "https://api.paystack.co"
    currency: str = "GHS"
    rate_limit_auth_per_minute: int = 20

    def validate_for_production(self) -> None:
        if self.env == "production" and self.jwt_secret == "dev-only-change-me":
            raise RuntimeError("JWT_SECRET must be set in production")


@lru_cache
def get_settings() -> Settings:
    return Settings()
