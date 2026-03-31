from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.db.base import Base
from app.db.session import engine
from app.routers import reports
import app.models.balance_cache  # noqa: F401


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(
    title="ContaREPO - Reportes Contables",
    version="1.0.0",
    description="Servicio de reportes para ContaPYME (Balance, EERR, Formulario 710)",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

PREFIX = "/api/v1"
app.include_router(reports.router, prefix=PREFIX)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "ContaREPO"}
