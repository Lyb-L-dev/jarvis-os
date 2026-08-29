from __future__ import annotations

import asyncio
import hmac
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from app.api.router import api_router
from app.core.config import get_settings
from app.db.session import create_schema, dispose_engine
from app.services.intelligence import intelligence_background_worker
from app.services.knowledge_archive import knowledge_archive_background_worker
from app.services.monitoring import monitoring_background_worker
from app.services.proactive import proactive_background_worker

settings = get_settings()


class DesktopSessionMiddleware(BaseHTTPMiddleware):
    """Require the launch-scoped desktop token when bundled mode enables it."""

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        configured = settings.desktop_session_token
        if configured is None or request.method == "OPTIONS":
            return await call_next(request)
        if request.url.path in {f"{settings.api_prefix}/health/live", "/"}:
            return await call_next(request)
        expected = configured.get_secret_value()
        provided = request.headers.get("X-Jarvis-Desktop-Session", "")
        if not provided or not hmac.compare_digest(provided, expected):
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Desktop session is missing or expired."},
            )
        return await call_next(request)


def selector_loop_factory() -> asyncio.AbstractEventLoop:
    """Windows loop factory for uvicorn (defaults to Proactor, which breaks psycopg)."""
    return asyncio.SelectorEventLoop()


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    if settings.auto_create_schema:
        await create_schema()
    stop_event = asyncio.Event()
    worker = None
    knowledge_worker = None
    monitoring_worker = None
    proactive_worker = None
    if (
        settings.intelligence_auto_brief_enabled
        and settings.app_env != "test"
    ):
        worker = asyncio.create_task(
            intelligence_background_worker(stop_event),
            name="jarvis-intelligence-worker",
        )
    if settings.monitoring_auto_enabled and settings.app_env != "test":
        monitoring_worker = asyncio.create_task(
            monitoring_background_worker(stop_event),
            name="jarvis-monitoring-worker",
        )
    if settings.proactive_enabled and settings.app_env != "test":
        proactive_worker = asyncio.create_task(
            proactive_background_worker(
                stop_event,
                interval_seconds=settings.proactive_poll_seconds,
            ),
            name="jarvis-proactive-worker",
        )
    if settings.knowledge_auto_archive_enabled and settings.app_env != "test":
        knowledge_worker = asyncio.create_task(
            knowledge_archive_background_worker(
                stop_event,
                interval_seconds=settings.knowledge_auto_archive_interval_seconds,
            ),
            name="jarvis-knowledge-archive-worker",
        )
    yield
    stop_event.set()
    if worker is not None:
        worker.cancel()
        with suppress(asyncio.CancelledError):
            await worker
    if knowledge_worker is not None:
        knowledge_worker.cancel()
        with suppress(asyncio.CancelledError):
            await knowledge_worker
    if monitoring_worker is not None:
        monitoring_worker.cancel()
        with suppress(asyncio.CancelledError):
            await monitoring_worker
    if proactive_worker is not None:
        proactive_worker.cancel()
        with suppress(asyncio.CancelledError):
            await proactive_worker
    await dispose_engine()


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Personal AI Operating System API",
    debug=settings.debug,
    lifespan=lifespan,
)

app.add_middleware(DesktopSessionMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.web_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.api_prefix)


@app.exception_handler(ConnectionError)
async def connection_error_handler(
    _: Request,
    __: ConnectionError,
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "detail": "A required local service is unavailable. Check Jarvis system status."
        },
    )


@app.get("/", include_in_schema=False)
async def root() -> dict[str, str]:
    return {
        "name": settings.app_name,
        "status": "running",
        "docs": "/docs",
    }
