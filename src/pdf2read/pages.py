from __future__ import annotations

from pathlib import Path


def render_page_image(page, dest: Path, page_number: int, *, dpi: int = 132) -> str:
    import pymupdf

    dest.mkdir(parents=True, exist_ok=True)
    zoom = max(1.0, dpi / 72)
    pixmap = page.get_pixmap(
        matrix=pymupdf.Matrix(zoom, zoom),
        alpha=False,
        annots=True,
    )
    webp = dest / f"p{page_number:05d}.webp"
    try:
        image = pixmap.pil_image()
        image.save(webp, format="WEBP", quality=82, method=4)
        return webp.name
    except (ImportError, OSError, ValueError):
        png = dest / f"p{page_number:05d}.png"
        pixmap.save(png)
        return png.name
