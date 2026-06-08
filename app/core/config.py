from __future__ import annotations

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    APP_ENV: str = "production"
    API_BASE_URL: str = "https://api.mymizan.shop"
    FRONTEND_ORIGIN: str = "https://mymizan.shop"

    DATABASE_URL: str = "postgresql+psycopg://mymizan:CHANGE_ME@localhost:5432/mymizan"

    ORDER_WEBHOOK_URL: str = ""
    ORDER_WEBHOOK_SECRET: str = ""

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


settings = Settings()
