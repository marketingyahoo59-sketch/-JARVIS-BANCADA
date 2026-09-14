"""Visão: marcação de pontas na foto + zoom da área de medição."""

from __future__ import annotations

import io
from typing import Any

from PIL import Image, ImageDraw, ImageFont


def annotate_board(
    image_bytes: bytes,
    coordinates: list[dict[str, Any]] | None,
    *,
    thick: bool = True,
) -> Image.Image:
    """Desenha cruzes/círculos nas coordenadas (x,y em 0–100)."""
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    draw = ImageDraw.Draw(img)
    w, h = img.size
    try:
        font = ImageFont.load_default()
    except Exception:
        font = None

    for item in coordinates or []:
        label = str(item.get("label") or "ponto")
        x = float(item.get("x", 50)) / 100.0 * w
        y = float(item.get("y", 50)) / 100.0 * h
        key = label.lower()
        if "vermelha" in key or "red" in key:
            color = (220, 40, 40)
        elif "preta" in key or "black" in key:
            color = (20, 20, 20)
        else:
            color = (20, 120, 220)
        r = max(10, min(w, h) // 35)
        width = max(3, r // 3) if thick else max(2, r // 4)
        # halo branco para contraste
        draw.ellipse((x - r - 2, y - r - 2, x + r + 2, y + r + 2), outline=(255, 255, 255), width=width + 2)
        draw.ellipse((x - r, y - r, x + r, y + r), outline=color, width=width)
        draw.line((x - r * 1.8, y, x + r * 1.8, y), fill=color, width=width)
        draw.line((x, y - r * 1.8, x, y + r * 1.8), fill=color, width=width)
        # tag
        tag = label[:28]
        tx, ty = x + r + 6, max(2, y - r - 2)
        if font:
            bbox = draw.textbbox((tx, ty), tag, font=font)
            draw.rectangle(bbox, fill=(0, 0, 0, 180))
            draw.text((tx, ty), tag, fill=(255, 255, 255), font=font)
        else:
            draw.text((tx, ty), tag, fill=color)
    return img


def zoom_around_probes(
    image_bytes: bytes,
    coordinates: list[dict[str, Any]] | None,
    *,
    pad_ratio: float = 0.28,
    min_size: int = 220,
) -> Image.Image | None:
    """Recorta/aumenta a região ao redor das pontas marcadas."""
    coords = coordinates or []
    if not coords:
        return None
    base = annotate_board(image_bytes, coords)
    w, h = base.size
    xs = [float(c.get("x", 50)) / 100.0 * w for c in coords]
    ys = [float(c.get("y", 50)) / 100.0 * h for c in coords]
    cx = sum(xs) / len(xs)
    cy = sum(ys) / len(ys)
    span = max(max(xs) - min(xs), max(ys) - min(ys), min(w, h) * 0.15)
    half = max(span * (0.5 + pad_ratio), min_size / 2)
    left = int(max(0, cx - half))
    top = int(max(0, cy - half))
    right = int(min(w, cx + half))
    bottom = int(min(h, cy + half))
    if right - left < 40 or bottom - top < 40:
        return None
    crop = base.crop((left, top, right, bottom))
    # upscale leve para leitura no celular
    scale = max(1.0, 480 / max(crop.size))
    if scale > 1.05:
        crop = crop.resize((int(crop.size[0] * scale), int(crop.size[1] * scale)), Image.Resampling.LANCZOS)
    return crop


def image_to_png_bytes(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

