import os
from fastapi import FastAPI
from contextlib import asynccontextmanager
from core.database import init_db
from core.config import settings
from api.routes.tasks import router as tasks_router
from api.routes.stream import router as stream_router
from api.routes.dag import router as dag_router
from fastapi.middleware.cors import CORSMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Starting Task Autopilot...")
    os.makedirs(settings.artifacts_dir, exist_ok=True)
    await init_db()
    print(f"LLM Model   : {settings.llm_model}")
    print(f"Max steps   : {settings.max_steps}")
    print(f"Cache       : {settings.cache_enabled}")
    print("Ready\n")
    yield
    print("Shutting down...")


app = FastAPI(
    title="Task Autopilot",
    description="AI agentic task runner — uTrade Backend Assignment",
    version="1.0.0",
    lifespan=lifespan,
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(tasks_router)
app.include_router(stream_router)
app.include_router(dag_router)


@app.get("/health", tags=["Health"])
async def health():
    return {
        "status": "ok",
        "llm_model": settings.llm_model,
        "max_steps": settings.max_steps,
        "cache_enabled": settings.cache_enabled,
    }