"""Validated menu photographs, stored with the local database."""

import base64
import io
import warnings

from fastapi import Depends, File, UploadFile
from fastapi.responses import Response
from PIL import Image, ImageOps, UnidentifiedImageError

from app.features import app, db, fail, get, manager, staff, write


@app.post("/menu/items/{ident}/image")
async def upload_menu_image(
    ident: int, file: UploadFile = File(), user=Depends(manager)
):
    raw = await file.read(5 * 1024 * 1024 + 1)
    if len(raw) > 5 * 1024 * 1024:
        fail("Image exceeds 5 MiB", 413)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(raw)) as source:
                if source.format not in {"JPEG", "PNG", "WEBP"}:
                    fail("Only JPEG, PNG and WebP photographs are accepted", 415)
                if source.width * source.height > 20_000_000:
                    fail("Image exceeds 20 megapixels", 413)
                source.load()
                photo = ImageOps.exif_transpose(source).convert("RGB")
                photo.thumbnail((1600, 1600))
                output = io.BytesIO()
                photo.save(output, format="JPEG", quality=88)
    except (
        UnidentifiedImageError,
        OSError,
        ValueError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ):
        fail("Invalid or unsafe image", 415)
    with db() as c:
        item = get(c, "item", ident)
        # A separate immutable image record allows existing clients to cache safely.
        image = write(
            c,
            "menu_image",
            {
                "item_id": ident,
                "content": base64.b64encode(output.getvalue()).decode(),
                "media_type": "image/jpeg",
                "width": photo.width,
                "height": photo.height,
            },
            user,
        )
        item["image_url"] = f"/menu/images/{image['id']}"
        write(c, "item", item, user, ident)
        return {
            "image_url": item["image_url"],
            "width": photo.width,
            "height": photo.height,
        }


@app.get("/menu/images/{ident}")
def menu_image(ident: int, user=Depends(staff)):
    with db() as c:
        image = get(c, "menu_image", ident)
        return Response(
            base64.b64decode(image["content"]),
            media_type=image["media_type"],
            headers={
                "X-Content-Type-Options": "nosniff",
                "Cache-Control": "private, max-age=86400",
            },
        )


@app.delete("/menu/items/{ident}/image")
def remove_menu_image(ident: int, user=Depends(manager)):
    with db() as c:
        item = get(c, "item", ident)
        item["image_url"] = None
        write(c, "item", item, user, ident)
        return {"image_url": None}
