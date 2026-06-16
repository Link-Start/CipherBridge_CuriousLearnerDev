"""项目名称规范化."""

from __future__ import annotations

import re

_NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")


def normalize_project_name(raw: str, default: str = "project") -> str:
    """转为合法项目名：小写字母/数字/下划线，以字母开头."""
    name = (raw or "").strip().lower().replace(" ", "_")
    name = re.sub(r"[^a-z0-9_]", "_", name)
    name = re.sub(r"_+", "_", name).strip("_")
    if not name:
        return default
    if name[0].isdigit():
        name = f"p_{name}"
    return name


def is_valid_project_name(name: str) -> bool:
    return bool(name and _NAME_RE.match(name))
