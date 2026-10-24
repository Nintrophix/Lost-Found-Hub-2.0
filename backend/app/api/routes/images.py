"""Authorised image download under /api/images. Images are never served as public static files."""

from fastapi import APIRouter
from fastapi.responses import FileResponse

from app.api.deps import AppSettings, CurrentUser, DbSession
from app.services import images as image_service

router = APIRouter(prefix="/images", tags=["images"])


@router.get("/{image_id}", response_class=FileResponse)
def get_image(image_id: int, user: CurrentUser, db: DbSession, settings: AppSettings) -> FileResponse:
    path, content_type = image_service.get_image_file(db, settings, user, image_id)
    return FileResponse(
        path,
        media_type=content_type,
        headers={
            "Cache-Control": "private, max-age=3600",
            "X-Content-Type-Options": "nosniff",
            "Content-Disposition": "inline",
            "Content-Security-Policy": "default-src 'none'; sandbox",
        },
    )
