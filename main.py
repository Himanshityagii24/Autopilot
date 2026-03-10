import os
from fastapi import FastAPI
from contextlib import asynccontextmanager
from core.database import init_db
from core.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
   
    print("Starting Autopilot")
    os.makedirs(settings.artifacts_dir, exist_ok=True)
    await init_db()
    print(f" LLM Model   : {settings.llm_model}")
    print(f" Max steps   : {settings.max_steps}")
    print(f" Cache       : {settings.cache_enabled}")
    print(" Ready\n")
    yield
    print(" Shutting down")


app = FastAPI(
    title="Task Autopilot",
    description="AI agentic task runner",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health", tags=["Health"])
async def health():
    return {
        "status": "ok",
        "llm_model": settings.llm_model,
        "max_steps": settings.max_steps,
        "cache_enabled": settings.cache_enabled,
    }