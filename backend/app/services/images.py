"""Report image upload, retrieval and deletion.

Uploads are identified by their bytes (never the client's filename or content type), fully decoded
by Pillow and re-encoded. Re-encoding drops EXIF data such as GPS location and any trailing payload.
Files are stored under UPLOAD_DIR/items with random names and are only served through the API.
"""

import os
import warnings
from io import BytesIO
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile
from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.rate_limit import allow_for_key
from app.db.models import Item, ReportImage, User
from app.schemas.items import ItemImageResponse
from app.services import audit
from app.services import items as item_service
from app.services.concurrency import lock_status
from app.services.errors import ServiceError

MAX_IMAGES_PER_ITEM = 5
MAX_PIXELS = 40_000_000
UNSUPPORTED = "Upload a JPEG, PNG or WebP image."

# Pillow format name -> (content type, file extension)
FORMATS = {"JPEG": ("image/jpeg", "jpg"), "PNG": ("image/png", "png"), "WEBP": ("image/webp", "webp")}


def _sniff_format(data: bytes) -> str | None:
    if data.startswith(b"\xff\xd8\xff"):
        return "JPEG"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "PNG"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "WEBP"
    return None


def _reencode(data: bytes) -> tuple[bytes, str]:
    fmt = _sniff_format(data)
    if fmt is None:
        raise ServiceError(415, UNSUPPORTED)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(data)) as probe:
                if probe.format != fmt or probe.width * probe.height > MAX_PIXELS:
                    raise ServiceError(415, UNSUPPORTED)
                probe.verify()
            with Image.open(BytesIO(data)) as img:
                img.load()
                img = ImageOps.exif_transpose(img)
    except ServiceError:
        raise
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError, Image.DecompressionBombError,
            Image.DecompressionBombWarning):
        raise ServiceError(415, UNSUPPORTED) from None

    out = BytesIO()
    if fmt == "JPEG":
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        img.save(out, "JPEG", quality=90, optimize=True)
    elif fmt == "PNG":
        img.save(out, "PNG", optimize=True)
    else:
        img.save(out, "WEBP", quality=90)
    return out.getvalue(), fmt


def _image_dir(settings: Settings) -> Path:
    path = Path(settings.upload_dir) / "items"
    path.mkdir(parents=True, exist_ok=True)
    return path


def add_image(db: Session, settings: Settings, user: User, item_id: int, upload: UploadFile) -> ReportImage:
    item = item_service.get_manageable(db, user, item_id)
    if item.status not in item_service.EDITABLE_STATUSES:
        raise ServiceError(409, "Images can no longer be changed for this report.")
    lock_status(db, Item, item.id, item_service.EDITABLE_STATUSES,
                "Images can no longer be changed for this report.")
    count = db.scalar(select(func.count(ReportImage.id)).where(ReportImage.item_id == item.id)) or 0
    if count >= MAX_IMAGES_PER_ITEM:
        raise ServiceError(409, f"A report can have at most {MAX_IMAGES_PER_ITEM} images.")
    if not allow_for_key("upload-image", str(user.id), 60, 3600):
        raise ServiceError(429, "You have uploaded many images recently. Try again later.", {"Retry-After": "3600"})

    raw = upload.file.read(settings.max_upload_bytes + 1)
    if not raw:
        raise ServiceError(422, "The uploaded file is empty.")
    too_large = ServiceError(413, f"Images must be {settings.max_upload_bytes // (1024 * 1024)} MB or smaller.")
    if len(raw) > settings.max_upload_bytes:
        raise too_large
    data, fmt = _reencode(raw)
    if len(data) > settings.max_upload_bytes:
        raise too_large

    content_type, ext = FORMATS[fmt]
    stored_filename = f"{uuid4().hex}.{ext}"
    path = _image_dir(settings) / stored_filename
    temp = path.with_suffix(".tmp")
    temp.write_bytes(data)
    os.replace(temp, path)

    try:
        image = ReportImage(item_id=item.id, stored_filename=stored_filename, content_type=content_type,
                            file_size=len(data))
        db.add(image)
        db.flush()
        audit.record(db, "item.image_added", "item", item.id, actor_id=user.id, details={"image_id": image.id})
        db.commit()
    except Exception:
        db.rollback()
        path.unlink(missing_ok=True)
        raise
    return image


def delete_image(db: Session, settings: Settings, user: User, item_id: int, image_id: int) -> None:
    item = item_service.get_manageable(db, user, item_id)
    if item.status not in item_service.EDITABLE_STATUSES:
        raise ServiceError(409, "Images can no longer be changed for this report.")
    lock_status(db, Item, item.id, item_service.EDITABLE_STATUSES,
                "Images can no longer be changed for this report.")
    image = db.get(ReportImage, image_id)
    if image is None or image.item_id != item.id:
        raise ServiceError(404, "Image not found.")
    filename = image.stored_filename
    db.delete(image)
    audit.record(db, "item.image_deleted", "item", item.id, actor_id=user.id, details={"image_id": image_id})
    db.commit()
    (_image_dir(settings) / filename).unlink(missing_ok=True)


def get_image_file(db: Session, settings: Settings, user: User, image_id: int) -> tuple[Path, str]:
    image = db.get(ReportImage, image_id)
    if image is None:
        raise ServiceError(404, "Image not found.")
    try:
        item_service.get_viewable(db, user, image.item_id)
    except ServiceError:
        raise ServiceError(404, "Image not found.") from None
    path = _image_dir(settings) / image.stored_filename
    if not path.is_file():
        raise ServiceError(404, "Image not found.")
    return path, image.content_type


def to_response(image: ReportImage) -> ItemImageResponse:
    return ItemImageResponse(id=image.id, url=f"/api/images/{image.id}", content_type=image.content_type,
                             file_size=image.file_size)
