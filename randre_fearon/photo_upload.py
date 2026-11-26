"""F-02 helper: validate and store the vehicle photos uploaded on the Add Unit form.

Photos are saved in the UPLOAD_FOLDER set in shared/config.py ("uploads/", which .gitignore
already skips) and the vehicle stores their web addresses (/inventory/photos/<name>) as a
JSON list in vehicles.photo_urls, exactly as docs/API_AND_DB_CONTRACT.md says.

Note for deployment: Vercel's disk is temporary, so for production the files would need to
move to cloud storage (for example Vercel Blob or Amazon S3). Local development works as is.
"""

import os
import uuid

from flask import current_app

PHOTO_URL_PREFIX = "/inventory/photos/"
MAX_PHOTOS = 10
MAX_PHOTO_BYTES = 5 * 1024 * 1024  # 5 MB each
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}


def upload_dir() -> str:
    """Absolute path of the folder where photos are stored."""
    folder = current_app.config.get("UPLOAD_FOLDER", "uploads")
    if not os.path.isabs(folder):
        folder = os.path.join(current_app.root_path, folder)
    return folder


def _detect_extension(header: bytes):
    """Work out the real image type from the first bytes of the file.

    This is safer than trusting the file name: a harmful file renamed to cat.jpg is rejected.
    """
    if header.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if header[:6] in (b"GIF87a", b"GIF89a"):
        return ".gif"
    if header[:4] == b"RIFF" and header[8:12] == b"WEBP":
        return ".webp"
    return None


def _inspect(file):
    """Return (first 12 bytes, size in bytes) and leave the file ready to be read again."""
    stream = file.stream
    stream.seek(0)
    header = stream.read(12)
    stream.seek(0, os.SEEK_END)
    size = stream.tell()
    stream.seek(0)
    return header, size


def validate_photos(files) -> str | None:
    """Return an error message for the first problem found, or None if every photo is fine."""
    if len(files) > MAX_PHOTOS:
        return f"You can upload at most {MAX_PHOTOS} photos at a time"
    for file in files:
        name = os.path.basename(file.filename or "")[:60]
        header, size = _inspect(file)
        extension = os.path.splitext(name)[1].lower()
        if extension not in ALLOWED_EXTENSIONS or _detect_extension(header) is None:
            return f'"{name}" is not a valid image (use JPG, PNG, GIF or WEBP)'
        if size > MAX_PHOTO_BYTES:
            return f'"{name}" is larger than {MAX_PHOTO_BYTES // (1024 * 1024)} MB'
    return None


def save_photos(files) -> list:
    """Save already-validated photos. Returns their web addresses, in the order uploaded."""
    folder = upload_dir()
    os.makedirs(folder, exist_ok=True)
    urls = []
    for file in files:
        header, _size = _inspect(file)
        # A random name means two uploads can never overwrite each other, and the
        # customer's file name (which could contain ../ tricks) is never used on disk.
        filename = uuid.uuid4().hex + _detect_extension(header)
        file.save(os.path.join(folder, filename))
        urls.append(PHOTO_URL_PREFIX + filename)
    return urls


def delete_photos(urls) -> None:
    """Remove photos saved for a record that then failed to save (so no orphan files remain)."""
    folder = upload_dir()
    for url in urls:
        if url.startswith(PHOTO_URL_PREFIX):
            path = os.path.join(folder, os.path.basename(url))
            if os.path.exists(path):
                os.remove(path)
