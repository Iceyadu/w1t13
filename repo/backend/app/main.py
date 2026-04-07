import logging
import uuid
from contextlib import asynccontextmanager

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("harborview")

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import Base, get_async_session_factory, get_engine
from app.routers import (
    auth,
    users,
    residents,
    properties,
    billing,
    payments,
    credits,
    orders,
    listings,
    media,
    content,
    reports,
    backup,
    health,
    audit,
    rollout,
)
from app.services.seed_service import seed_default_admin
from app.middleware.idempotency import IdempotencyMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: validate critical config
    if not settings.SECRET_KEY:
        raise RuntimeError(
            "SECRET_KEY is not set. Provide a strong secret via the SECRET_KEY "
            "environment variable or .env file before starting the application."
        )
    if settings.BACKUP_PASSPHRASE in ("", "backup-default-passphrase", "change-me-backup-passphrase"):
        logger.warning(
            "BACKUP_PASSPHRASE is not set or uses a default value. "
            "Set a strong passphrase via the BACKUP_PASSPHRASE environment variable."
        )
    # Startup: create tables and seed default admin
    logger.info("HarborView backend starting up")
    engine = get_engine()
    async_session_factory = get_async_session_factory()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with async_session_factory() as session:
        await seed_default_admin(session)
        await session.commit()
    logger.info("Database tables created, default admin seeded")
    yield
    # Shutdown
    await engine.dispose()


app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost",
        "http://localhost:80",
        "http://localhost:3000",
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(IdempotencyMiddleware)


# Request ID middleware
@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    request.state.request_id = request_id
    response: Response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


# Register routers
prefix = settings.API_V1_PREFIX

app.include_router(health.router, prefix=prefix, tags=["Health"])
app.include_router(auth.router, prefix=prefix, tags=["Auth"])
app.include_router(users.router, prefix=prefix, tags=["Users"])
app.include_router(residents.router, prefix=prefix, tags=["Residents"])
app.include_router(properties.router, prefix=prefix, tags=["Properties"])
app.include_router(billing.router, prefix=prefix, tags=["Billing"])
app.include_router(payments.router, prefix=prefix, tags=["Payments"])
app.include_router(credits.router, prefix=prefix, tags=["Credits"])
app.include_router(orders.router, prefix=prefix, tags=["Orders"])
app.include_router(listings.router, prefix=prefix, tags=["Listings"])
app.include_router(media.router, prefix=prefix, tags=["Media"])
app.include_router(content.router, prefix=prefix, tags=["Content"])
app.include_router(reports.router, prefix=prefix, tags=["Reports"])
app.include_router(backup.router, prefix=prefix, tags=["Backup"])
app.include_router(audit.router, prefix=prefix, tags=["Audit"])
app.include_router(rollout.router, prefix=prefix, tags=["Rollout"])
