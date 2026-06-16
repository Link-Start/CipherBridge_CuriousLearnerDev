"""AI 实验室 — 从分析步骤自动生成并保存 mitmdump 代理项目."""

from __future__ import annotations

import json
import os
import re
from urllib.parse import urlparse

import yaml

from codegen import generate_code_from_steps
from core.project_name import normalize_project_name

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROFILES_DIR = os.path.join(ROOT, "profiles")
PLUGINS_DIR = os.path.join(ROOT, "plugins")


def guess_project_name(url: str, flows: list[dict] | None = None) -> str:
    host = ""
    if flows:
        host = urlparse(flows[0].get("url", "")).hostname or ""
    if not host and url:
        u = url.strip()
        if not u.startswith("http"):
            u = "https://" + u
        host = urlparse(u).hostname or ""
    if not host:
        return "ai_project"
    return normalize_project_name(host.lower().replace(".", "_"), default="ai_project")


def detect_body_format(flows: list[dict]) -> str:
    for f in flows:
        body = (f.get("request_body") or "").strip()
        if not body:
            continue
        if body.startswith("{") or body.startswith("["):
            return "json"
        if "=" in body and "&" in body and not body.startswith("<"):
            return "form"
    return "json"


def guess_match_rules(flows: list[dict], fallback_url: str = "") -> dict:
    hosts: set[str] = set()
    paths: set[str] = set()
    methods: set[str] = set()

    for f in flows:
        u = urlparse(f.get("url", ""))
        if u.hostname:
            hosts.add(u.hostname)
        if u.path:
            parts = [p for p in u.path.strip("/").split("/") if p]
            if parts:
                paths.add(f"/{parts[0]}/*")
            else:
                paths.add("/*")
        m = (f.get("method") or "").upper()
        if m:
            methods.add(m)

    if not hosts and fallback_url:
        u = fallback_url.strip()
        if not u.startswith("http"):
            u = "https://" + u
        if urlparse(u).hostname:
            hosts.add(urlparse(u).hostname)

    return {
        "host": sorted(hosts) or ["*"],
        "path": sorted(paths) or ["/api/*"],
        "methods": sorted(methods) or ["POST"],
    }


def save_ai_project(
    profile_name: str,
    steps: list[dict],
    *,
    roles: list[str],
    code_role: str | None = None,
    match: dict | None = None,
    body_format: str = "json",
    description: str = "",
    flows: list[dict] | None = None,
    fallback_url: str = "",
    overwrite: bool = False,
) -> tuple[str, str]:
    """写入 plugins/ + profiles/ + state.json，返回 (项目名, 插件代码)."""
    name = normalize_project_name(profile_name)
    if not name:
        raise ValueError("项目名称不能为空")

    profile_path = os.path.join(PROFILES_DIR, f"{name}.yaml")
    plugin_dir = os.path.join(PLUGINS_DIR, name)
    if os.path.exists(profile_path) or os.path.isdir(plugin_dir):
        if not overwrite:
            raise FileExistsError(f"项目 '{name}' 已存在")

    if not steps:
        raise ValueError("没有可用的加解密步骤，请先运行 AI 分析")

    rules = match or guess_match_rules(flows or [], fallback_url)
    if code_role in ("encrypt", "decrypt"):
        gen_role = code_role
    elif isinstance(roles, list) and "encrypt" in roles and "decrypt" not in roles:
        gen_role = "encrypt"
    else:
        gen_role = "decrypt"
    code = generate_code_from_steps(
        steps, body_format, role=gen_role, profile_name=name, match_rules=rules,
    )

    os.makedirs(plugin_dir, exist_ok=True)
    with open(os.path.join(plugin_dir, "plugin.py"), "w", encoding="utf-8") as f:
        f.write(code)

    profile = {
        "name": name,
        "description": description or "AI 实验室自动生成",
        "plugin": name,
        "roles": roles or ["decrypt"],
        "match": {
            "host": rules.get("host", ["*"]),
            "path": rules.get("path", ["/api/*"]),
            "methods": rules.get("methods", ["POST"]),
        },
    }
    with open(profile_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(profile, f, allow_unicode=True, sort_keys=False)

    with open(os.path.join(plugin_dir, "state.json"), "w", encoding="utf-8") as f:
        json.dump(
            {
                "steps": steps,
                "parsed_fields": {},
                "parsed_query": {},
                "body_format": body_format,
                "raw_input": "",
                "ai_generated": True,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )

    return name, code
