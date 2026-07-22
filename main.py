from __future__ import annotations

import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import inspect, text

from app.api.routes import admin, events, orders
from app.core.config import settings
from app.db.bootstrap import bootstrap_database
from app.db.session import engine
from app.schemas.order import HealthOut

logger = logging.getLogger(__name__)


def _bootstrap_in_background() -> None:
    try:
        bootstrap_database()
    except Exception:
        logger.exception("Background database bootstrap failed")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.basicConfig(level=logging.INFO)
    logger.info("Starting Mizan API (env=%s)", settings.APP_ENV)
    threading.Thread(target=_bootstrap_in_background, name="db-bootstrap", daemon=True).start()
    yield
    logger.info("Shutting down Mizan API")


app = FastAPI(title="Mizan API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(orders.router)
app.include_router(events.router)
app.include_router(admin.router)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Catch-all handler so that unhandled Python exceptions (DB crashes, etc.)
    still return a JSON response that passes through CORSMiddleware.
    Without this, ServerErrorMiddleware returns a bare 500 with no CORS headers,
    which makes the browser treat it as a network/CORS error instead of a server error.
    """
    logger.exception("Unhandled exception on %s %s: %s", request.method, request.url.path, exc)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "error": "server_error"},
    )


@app.get("/health/live")
async def health_live():
    return {"ok": True}


@app.get("/health")
async def health():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            tables = sorted(inspect(engine).get_table_names())

        return HealthOut(ok=True, database="connected", tables=tables)
    except Exception as exc:
        logger.warning("Health check database probe failed: %s", exc)
        return JSONResponse(
            status_code=503,
            content={"ok": False, "database": "disconnected", "detail": str(exc)},
        )
