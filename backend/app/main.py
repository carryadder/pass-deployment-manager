from fastapi import FastAPI

from backend.app.api.inventory import router as inventory_router
from backend.app.api.lifecycle import router as lifecycle_router
from backend.app.api.system import router as system_router
from backend.app.config import get_settings
from backend.app.core.docker_client import ping_docker

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    debug=settings.app_debug,
)
app.include_router(inventory_router)
app.include_router(lifecycle_router)
app.include_router(system_router)


@app.get("/healthz", tags=["health"])
def healthcheck() -> dict:
    return {
        "status": "ok",
        "environment": settings.app_env,
        "docker_available": ping_docker(),
    }
