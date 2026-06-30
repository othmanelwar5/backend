from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings
from sqlalchemy.engine import make_url

EASYPANEL_POSTGRES_HOST = "mymizan_database"


class Settings(BaseSettings):
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    APP_ENV: str = "production"
    API_BASE_URL: str = "https://api.mymizan.shop"
    FRONTEND_ORIGIN: str = "https://mymizan.shop"

    DATABASE_URL: str = "postgresql+psycopg://mymizan:CHANGE_ME@localhost:5432/mymizan"
    RUN_MIGRATIONS_ON_STARTUP: bool = False

    ORDER_WEBHOOK_URL: str = ""

    # MaxMind GeoIP2 Precision Insights
    MAXMIND_ACCOUNT_ID: str = ""
    MAXMIND_LICENSE_KEY: str = ""
    MAXMIND_ENABLED: bool = True

    # Geo-fraud settings
    GEO_ALLOWED_COUNTRIES: list[str] = Field(default=["SA"])
    GEO_BLOCK_VPN: bool = True
    GEO_BLOCK_HIGH_RISK: bool = True
    GEO_RISK_SCORE_THRESHOLD: float = 50.0

    # Whitelisted phone numbers that bypass geo/fraud checks (for testing in prod)
    WHITELISTED_PHONES: list[str] = Field(default=["055000000"])

    # Meta CAPI
    META_PIXEL_ID: str = ""
    META_ACCESS_TOKEN: str = ""
    META_TEST_EVENT_CODE: str = ""

    # TikTok CAPI
    TIKTOK_PIXEL_ID: str = ""
    TIKTOK_ACCESS_TOKEN: str = ""
    TIKTOK_TEST_EVENT_CODE: str = ""

    # Snap CAPI
    SNAP_PIXEL_ID: str = ""
    SNAP_ACCESS_TOKEN: str = ""

    CAPI_ENABLED: bool = True
    CAPI_TEST_MODE: bool = False


def normalize_database_url(raw_url: str) -> str:
    url = raw_url.strip()

    if url.startswith("postgres://"):
        url = "postgresql+psycopg://" + url[len("postgres://") :]
    elif url.startswith("postgresql://") and not url.startswith("postgresql+"):
        url = "postgresql+psycopg://" + url[len("postgresql://") :]

    parsed = make_url(url)
    if parsed.host == "HOST":
        parsed = parsed.set(host=EASYPANEL_POSTGRES_HOST)

    if parsed.username == "USER" or parsed.password == "PASSWORD" or parsed.database == "DBNAME":
        raise ValueError(
            "DATABASE_URL still contains placeholder credentials or database name. "
            "Set the real PostgreSQL username, password, and database name in EasyPanel."
        )

    return parsed.render_as_string(hide_password=False)


settings = Settings()
settings.DATABASE_URL = normalize_database_url(settings.DATABASE_URL)
