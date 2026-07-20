"""GUI 图标加载 — 从 img/icons/ 加载 PNG/SVG，程序图标 img/main.jpg."""

from __future__ import annotations

import os
import re
from PyQt6.QtCore import Qt, QSize, QSize
from PyQt6.QtGui import QIcon, QPixmap, QPainter

try:
    from PyQt6.QtSvg import QSvgRenderer
    _HAS_SVG = True
except ImportError:
    _HAS_SVG = False

from core.theme import C
from core.paths import get_app_root

ROOT = get_app_root()
IMG_DIR = os.path.join(ROOT, "img")
ICON_DIR = os.path.join(IMG_DIR, "icons")
MAIN_ICON = os.path.join(IMG_DIR, "main.jpg")
TOPOLOGY_IMAGE = os.path.join(IMG_DIR, "e2f83ef5-edda-4dbf-a8f0-cf24bbc920aa.png")

_VARIANT_TINT = {
    "primary": C["text"],
    "accent": C["text"],
    "danger": C["danger"],
    "warn": C["text"],
    "ghost": C["text_dim"],
}

_cache: dict[tuple[str, int, str], QIcon] = {}


def clear_icon_cache() -> None:
    _cache.clear()


def _tint_svg_data(svg_data: str, color: str) -> bytes:
    """给无 fill 的 SVG 路径着色，适配深色主题."""
    svg_data = re.sub(
        r'(<svg\b[^>]*?)fill="[^"]*"',
        rf'\1fill="{color}"',
        svg_data,
        count=1,
    )
    if 'fill="' not in svg_data.split(">", 1)[0]:
        svg_data = re.sub(
            r"(<svg\b)",
            rf'\1 fill="{color}"',
            svg_data,
            count=1,
        )
    svg_data = re.sub(r'fill="#333"', f'fill="{color}"', svg_data)
    svg_data = re.sub(r"fill='#333'", f"fill='{color}'", svg_data)
    svg_data = re.sub(r'stroke="#333"', f'stroke="{color}"', svg_data)
    return svg_data.encode("utf-8")


def _render_svg(svg_path: str, size: int, tint: str | None = None) -> QIcon:
    color = tint or C["text"]
    with open(svg_path, encoding="utf-8") as f:
        svg_data = _tint_svg_data(f.read(), color)
    renderer = QSvgRenderer(svg_data)
    pixmap = QPixmap(QSize(size, size))
    pixmap.fill(Qt.GlobalColor.transparent)
    if renderer.isValid():
        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.end()
    return QIcon(pixmap)


def _resolve_tint(tint: str | None = None, light: bool = False, variant: str = "") -> str:
    if tint:
        return tint
    if variant in _VARIANT_TINT:
        return _VARIANT_TINT[variant]
    if light:
        return C["text"]
    return C["text"]


def icon(name: str, size: int = 20, light: bool = False, tint: str | None = None) -> QIcon:
    """按名称获取图标，优先 PNG，其次 SVG."""
    color = _resolve_tint(tint, light=light)
    key = (name, size, color)
    if key in _cache:
        return _cache[key]

    png = os.path.join(ICON_DIR, f"{name}.png")
    svg = os.path.join(ICON_DIR, f"{name}.svg")

    if os.path.isfile(png):
        ic = QIcon(png)
    elif os.path.isfile(svg) and _HAS_SVG:
        ic = _render_svg(svg, size, tint=color)
    else:
        ic = QIcon()

    _cache[key] = ic
    return ic


def app_icon() -> QIcon:
    """程序窗口图标 — img/main.jpg."""
    if os.path.isfile(MAIN_ICON):
        return QIcon(MAIN_ICON)
    return QIcon()


def set_btn_icon(btn, name: str, size: int = 16, light: bool = False, tint: str | None = None):
    """为按钮设置图标（主要操作按钮）."""
    if tint is None:
        variant = btn.property("variant") or ""
        if variant == "primary":
            tint = C.get("primary_fg", C["text"])
        elif variant == "accent":
            tint = C.get("accent_fg", C["text"])
        else:
            tint = C["text"]
    ic = icon(name, size, light=light, tint=tint)
    if ic.isNull():
        btn.setIcon(QIcon())
        return
    btn.setIcon(ic)
    btn.setIconSize(QSize(size, size))


def apply_app_icon(window) -> None:
    """设置主窗口及任务栏图标."""
    ic = app_icon()
    if not ic.isNull():
        window.setWindowIcon(ic)
