import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.config import settings
from app.database import init_db
from app.exceptions import AppError
from app.routes import certificates, jobs
from app.utils.constants import API_V1_PREFIX

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s [%(name)s] %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    settings.certificates_dir.mkdir(parents=True, exist_ok=True)
    init_db()
    yield


app = FastAPI(
    title="Bulk Certificate Generator API",
    description=(
        "Submit one request with many recipients and get one PDF certificate each. "
        "Generation runs in the background; poll the job endpoint for progress."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(jobs.router, prefix=API_V1_PREFIX)
app.include_router(certificates.router, prefix=API_V1_PREFIX)


@app.exception_handler(AppError)
async def handle_app_error(_request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})


@app.exception_handler(SQLAlchemyError)
async def handle_database_error(request: Request, exc: SQLAlchemyError) -> JSONResponse:
    logger.error("Database error on %s %s: %s", request.method, request.url.path, exc)
    return JSONResponse(status_code=500, content={"detail": "A database error occurred"})


@app.exception_handler(Exception)
async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@app.get("/", tags=["Health"], summary="Health check")
def health_check() -> dict[str, str]:
    return {"status": "ok", "message": "Bulk Certificate Generator API is running"}
