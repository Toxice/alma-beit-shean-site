from io import BytesIO

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from PIL import Image, ImageOps, UnidentifiedImageError

MAX_SIDE = 1600
MAX_BYTES = 15 * 1024 * 1024
UNSUPPORTED_MESSAGE = "הקובץ אינו תמונה נתמכת. יש להעלות תמונה בפורמט JPG או PNG."


def validate_upload(file):
    """Reject files over 15 MB or that Pillow cannot read (e.g. iPhone HEIC)."""
    if getattr(file, "_committed", False):
        return  # already-stored photo: only new uploads are checked (a lost file must not block saving the tab)
    if file.size > MAX_BYTES:
        raise ValidationError("התמונה גדולה מדי. הגודל המרבי הוא 15MB.")
    try:
        with Image.open(file) as img:
            img.verify()
    except (UnidentifiedImageError, OSError, SyntaxError):
        raise ValidationError(UNSUPPORTED_MESSAGE)
    finally:
        file.seek(0)


def to_web_jpeg(file):
    """Return (ContentFile, width, height): upright, RGB on white, longest side <= MAX_SIDE, JPEG q82."""
    file.seek(0)
    with Image.open(file) as original:
        img = ImageOps.exif_transpose(original)
        if img.mode in ("RGBA", "LA", "P"):
            rgba = img.convert("RGBA")
            img = Image.new("RGB", rgba.size, (255, 255, 255))
            img.paste(rgba, mask=rgba.getchannel("A"))
        else:
            img = img.convert("RGB")
        img.thumbnail((MAX_SIDE, MAX_SIDE), Image.LANCZOS)  # shrinks only, never upscales
        buf = BytesIO()
        img.save(buf, "JPEG", quality=82, optimize=True, progressive=True)
    return ContentFile(buf.getvalue()), img.width, img.height
