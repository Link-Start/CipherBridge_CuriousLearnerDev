"""Playwright 浏览器 — 绿色版内置 Chromium 路径."""

from __future__ import annotations

import os

from core.paths import get_app_root


def bundled_browsers_dir() -> str:
    return os.path.join(get_app_root(), "ms-playwright")


def setup_playwright_browsers_path() -> bool:
    """若存在内置 ms-playwright，设置 PLAYWRIGHT_BROWSERS_PATH."""
    path = bundled_browsers_dir()
    if os.path.isdir(path):
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = path
        return True
    return False


def has_bundled_chromium() -> bool:
    """是否已打包 Chromium（存在 chromium-* 目录）."""
    root = bundled_browsers_dir()
    if not os.path.isdir(root):
        return False
    try:
        for name in os.listdir(root):
            if name.startswith("chromium-"):
                return True
    except OSError:
        pass
    return False
