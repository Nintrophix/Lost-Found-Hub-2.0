"""FastAPI application entry point. Run with: uvicorn app.main:app --reload"""

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import CSRF_HEADER
from app.api.routes import admin, auth, claims, dashboard, images, items, matches, notifications, reference, staff
from app.core.config import get_settings
from app.core.middleware import BodySizeLimitMiddleware, SecurityHeadersMiddleware
from app.db.session import get_db
from app.services.errors import ServiceError

settings = get_settings()
is_production = settings.environment == "production"

app = FastAPI(
    title=settings.app_name,
    docs_url=None if is_production else "/api/docs",
    redoc_url=None,
    openapi_url=None if is_production else "/api/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Content-Type", CSRF_HEADER],
)
# Uploads are the largest legitimate bodies; allow multipart overhead on top of the image limit.
app.add_middleware(BodySizeLimitMiddleware, max_bytes=settings.max_upload_bytes + 1024 * 1024)
# Added last so it is outermost and also covers CORS preflights and 413 responses.
app.add_middleware(SecurityHeadersMiddleware, hsts=is_production)


@app.exception_handler(ServiceError)
def handle_service_error(_request: Request, exc: ServiceError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail}, headers=exc.headers)


app.include_router(auth.router, prefix="/api")
app.include_router(admin.router, prefix="/api")
app.include_router(reference.router, prefix="/api")
app.include_router(items.router, prefix="/api")
app.include_router(images.router, prefix="/api")
app.include_router(matches.router, prefix="/api")
app.include_router(notifications.router, prefix="/api")
app.include_router(claims.router, prefix="/api")
app.include_router(staff.router, prefix="/api")
app.include_router(dashboard.router, prefix="/api")


@app.get("/api/health", tags=["system"])
def health(db: Session = Depends(get_db)) -> dict[str, str]:
    db.execute(text("SELECT 1"))
    foreign_keys = db.execute(text("PRAGMA foreign_keys")).scalar_one()
    return {"status": "ok", "database": "ok", "foreign_keys": "on" if foreign_keys == 1 else "off"}
