from __future__ import annotations

import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import inspect, text
from starlette.middleware.base import BaseHTTPMiddleware

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


class CatchUnhandledErrorsMiddleware(BaseHTTPMiddleware):
    """Turn unhandled exceptions into a JSON 500 *below* CORSMiddleware.

    An `@app.exception_handler(Exception)` is installed into ServerErrorMiddleware,
    which sits outside CORSMiddleware, so its response carries no
    `access-control-allow-origin` header. The browser then discards the response
    and `fetch()` rejects with a generic network error, hiding the real server
    error from the storefront. Catching here keeps the response inside CORS.
    """

    async def dispatch(self, request: Request, call_next):
        try:
            return await call_next(request)
        except Exception as exc:
            logger.exception("Unhandled exception on %s %s: %s", request.method, request.url.path, exc)
            return JSONResponse(
                status_code=500,
                content={"detail": "Internal server error", "error": "server_error"},
            )


# Added first so it ends up inside CORSMiddleware: error responses get CORS headers.
app.add_middleware(CatchUnhandledErrorsMiddleware)
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


@app.get("/health/live")
async def health_live():
    return {"ok": True}


@app.get("/health/schema")
async def health_schema():
    """Report the schema drift that silently breaks order creation."""
    try:
        inspector = inspect(engine)
        tables = set(inspector.get_table_names())
        product_columns = (
            {column["name"] for column in inspector.get_columns("products")}
            if "products" in tables
            else set()
        )
        missing_tables = sorted({"products", "orders", "order_items", "customers", "analytics_events"} - tables)
        missing_product_columns = sorted({"slug", "sku", "price_1", "price_2", "price_3", "active"} - product_columns)

        return {
            "ok": not missing_tables and not missing_product_columns,
            "missing_tables": missing_tables,
            "missing_product_columns": missing_product_columns,
        }
    except Exception as exc:
        logger.warning("Schema health probe failed: %s", exc)
        return JSONResponse(status_code=503, content={"ok": False, "detail": str(exc)})


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
