import uuid

from django.core.files.storage import default_storage

ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "gif", "webp"}


def upload_image(file, folder="images"):
    """Upload an image file and return its URL.

    Uses Django's default_storage backend, making it trivial to swap
    between local FileSystemStorage, GCP, or AWS S3 by changing the
    STORAGES["default"] setting.
    """
    ext = file.name.rsplit(".", 1)[-1].lower()
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValueError(f"Unsupported image format: .{ext}")
    filename = f"{folder}/{uuid.uuid4().hex}.{ext}"
    saved_path = default_storage.save(filename, file)
    return default_storage.url(saved_path)
