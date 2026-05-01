from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy.exc import SQLAlchemyError
from starlette.concurrency import run_in_threadpool

from backend.app.api.auth import ensure_bootstrap_admin, router as auth_router
from backend.app.api.inventory import router as inventory_router
from backend.app.api.lifecycle import router as lifecycle_router
from backend.app.api.services import router as services_router
from backend.app.api.system import router as system_router
from backend.app.config import get_settings
from backend.app.db import Session, engine
from backend.app.core.docker_client import ping_docker
from backend.app.core.health_monitor import health_monitor
from backend.app.core.metrics import metrics_sampler
from backend.app.ws.logs import router as logs_ws_router
from backend.app.ws.metrics import router as metrics_ws_router

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    metrics_sampler.start()
    health_monitor.start()
    try:
        with Session(engine) as session:
            ensure_bootstrap_admin(session)
    except SQLAlchemyError:
        pass
    try:
        yield
    finally:
        health_monitor.stop()
        metrics_sampler.stop()


app = FastAPI(
    title=settings.app_name,
    debug=settings.app_debug,
    lifespan=lifespan,
)
app.include_router(auth_router)
app.include_router(inventory_router)
app.include_router(lifecycle_router)
app.include_router(services_router)
app.include_router(system_router)
app.include_router(logs_ws_router)
app.include_router(metrics_ws_router)


@app.get("/healthz", tags=["health"])
async def healthcheck() -> dict:
    return {
        "status": "ok",
        "environment": settings.app_env,
        "docker_available": await run_in_threadpool(ping_docker),
    }
