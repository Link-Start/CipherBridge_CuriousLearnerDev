"""AI / 浏览器实验室配置."""

from __future__ import annotations

import os
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AI_CONFIG_PATH = os.path.join(ROOT, "config", "ai.yaml")

DEFAULT = {
    "provider": "deepseek",
    "api_key": "",
    "base_url": "https://api.deepseek.com/v1",
    "model": "deepseek-chat",
    "http_proxy": "127.0.0.1:7897",
    "use_http_proxy": False,
    "browser": {
        "hook_enabled": True,
        "headless": False,
        "use_mitm_proxy": False,
        "mitm_port": 8080,
    },
}


def load_ai_config() -> dict:
    if not os.path.isfile(AI_CONFIG_PATH):
        return dict(DEFAULT)
    with open(AI_CONFIG_PATH, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    cfg = dict(DEFAULT)
    cfg.update({k: v for k, v in data.items() if k != "browser"})
    cfg["browser"] = {**DEFAULT["browser"], **(data.get("browser") or {})}
    return cfg


def save_ai_config(cfg: dict) -> None:
    os.makedirs(os.path.dirname(AI_CONFIG_PATH), exist_ok=True)
    with open(AI_CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.safe_dump(cfg, f, allow_unicode=True, default_flow_style=False)
