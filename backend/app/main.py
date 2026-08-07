"""JobPilot - AI-powered job application assistant."""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse

from app.api.routes import router
from app.core.config import settings
from app.core.rate_limit import RateLimitMiddleware
from app.core.llm import LLMError

logger = logging.getLogger("jobpilot")
logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - setup directories."""
    # Ensure data directories exist
    Path(settings.data_dir).mkdir(parents=True, exist_ok=True)
    Path(settings.cv_dir).mkdir(parents=True, exist_ok=True)
    Path(settings.jobs_dir).mkdir(parents=True, exist_ok=True)
    Path(settings.outputs_dir).mkdir(parents=True, exist_ok=True)

    logger.info("JobPilot started")
    logger.info(f"  LLM: {settings.llm_model} @ {settings.llm_base_url}")
    logger.info(f"  CVs dir: {Path(settings.cv_dir).resolve()}")
    logger.info(f"  Jobs dir: {Path(settings.jobs_dir).resolve()}")
    yield
    logger.info("JobPilot shutting down")


app = FastAPI(
    title="JobPilot",
    description="AI-powered job application assistant using local LLMs",
    version="0.1.0",
    lifespan=lifespan,
)

_allowed_origins = [o.strip() for o in settings.allowed_origins.split(",") if o.strip()]

app.add_middleware(RateLimitMiddleware, max_requests=120, window_seconds=60.0)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.exception_handler(LLMError)
async def llm_error_handler(request, exc: LLMError):
    logger.error("LLM error: %s", exc)
    return JSONResponse(status_code=502, content={"detail": "The local LLM is unavailable or returned an unexpected response."})

# Serve frontend static files if built
frontend_dist = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")
