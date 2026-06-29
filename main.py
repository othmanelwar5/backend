from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text

from app.api.routes import orders
from app.core.config import settings
from app.db.session import engine
from app.schemas.order import HealthOut

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.basicConfig(level=logging.INFO)
    logger.info("Starting Mizan API (env=%s)", settings.APP_ENV)
    yield
    logger.info("Shutting down Mizan API")


app = FastAPI(title="Mizan API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_ORIGIN, "http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(orders.router)


@app.get("/health/live")
async def health_live():
    return {"ok": True}


@app.get("/health", response_model=HealthOut)
async def health():
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
        tables = sorted(inspect(engine).get_table_names())

    return HealthOut(ok=True, database="connected", tables=tables)
