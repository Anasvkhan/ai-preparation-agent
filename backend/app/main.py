from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import artifacts, auth, evidence, health, projects, sessions, users
from app.core.config import get_settings
from app.db.mongo import close_async_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await close_async_client()


settings = get_settings()
app = FastAPI(title="FYP Viva Preparation Agent API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for router in (health.router, auth.router, users.router, projects.router, artifacts.router,
               evidence.router, sessions.router):
    app.include_router(router, prefix="/api")
