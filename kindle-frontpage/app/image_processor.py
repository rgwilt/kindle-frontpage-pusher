"""
Processes a raw front-page image into something that looks good on a
Kindle Paperwhite (2024): 7", 1264x1680 px, 300 ppi, E Ink Carta 1300,
16-level grayscale panel.

The pipeline: decode -> grayscale -> auto-contrast -> sharpen ->
resize/pad to the exact panel resolution -> save as PNG.

We deliberately do NOT dither here. FBInk (used on the Kindle side) does a
good job of dithering 8-bit grayscale down to the panel's native depth at
draw time, and pre-dithering a PNG tends to look worse once FBInk dithers
it a second time.
"""
from __future__ import annotations

import io
import logging

from PIL import Image, ImageEnhance, ImageFilter, ImageOps

log = logging.getLogger("frontpage.image")


def process_front_page(
    image_bytes: bytes,
    width: int = 1264,
    height: int = 1680,
    fit: str = "contain",
    background: str = "white",
    contrast: float = 1.15,
    sharpen: bool = True,
) -> bytes:
    """Return PNG bytes sized exactly (width, height), ready for the Kindle."""
    with Image.open(io.BytesIO(image_bytes)) as im:
        im = ImageOps.exif_transpose(im)  # respect orientation metadata
        gray = im.convert("L")

    # Stretch the histogram a touch so scanned newsprint isn't muddy grey,
    # but keep a small cutoff so we don't blow out highlights/shadows.
    gray = ImageOps.autocontrast(gray, cutoff=1)

    if contrast and contrast != 1.0:
        gray = ImageEnhance.Contrast(gray).enhance(contrast)

    if sharpen:
        gray = gray.filter(ImageFilter.UnsharpMask(radius=1.5, percent=110, threshold=2))

    bg_value = 255 if background == "white" else 0
    canvas = Image.new("L", (width, height), color=bg_value)

    src_w, src_h = gray.size
    if fit == "cover":
        scale = max(width / src_w, height / src_h)
    else:  # "contain" (default) -- never crop, may letterbox
        scale = min(width / src_w, height / src_h)

    new_w, new_h = max(1, round(src_w * scale)), max(1, round(src_h * scale))
    resized = gray.resize((new_w, new_h), Image.LANCZOS)

    if fit == "cover" and (new_w > width or new_h > height):
        left = (new_w - width) // 2
        top = (new_h - height) // 2
        resized = resized.crop((left, top, left + width, top + height))
        new_w, new_h = resized.size

    paste_x = (width - new_w) // 2
    paste_y = (height - new_h) // 2
    canvas.paste(resized, (paste_x, paste_y))

    out = io.BytesIO()
    canvas.save(out, format="PNG", optimize=True)
    log.info(
        "Processed image: source=%dx%d -> canvas=%dx%d (fit=%s)",
        src_w, src_h, width, height, fit,
    )
    return out.getvalue()
