"""HTTP 流量 ↔ 请求解析器报文格式转换."""

from __future__ import annotations

import re


def _header_lines(hdrs: dict | None) -> list[str]:
    if not hdrs or not isinstance(hdrs, dict):
        return []
    return [f"{k}: {v}" for k, v in hdrs.items()]


def flow_to_parser_raw(flow: dict) -> str:
    """将 AI 实验室捕获的单条流量格式化为请求解析器可解析的报文（含可选响应段）."""
    method = (flow.get("method") or "POST").upper()
    url = flow.get("url") or ""
    req_body = (flow.get("request_body") or "").strip()
    resp_body = (flow.get("response_body") or "").strip()
    status = int(flow.get("status") or 200)
    req_hdrs = flow.get("request_headers") or {}
    resp_hdrs = flow.get("response_headers") or {}

    if resp_body in ("(等待响应…)", "(等待响应...)", ""):
        resp_body = ""

    lines = [f"{method} {url} HTTP/1.1"]
    hdr_lines = _header_lines(req_hdrs)
    if hdr_lines:
        lines.extend(hdr_lines)
    else:
        lines.extend(["Content-Type: application/json", "Accept: application/json"])
    lines.extend(["", req_body])

    if resp_body:
        lines.append("")
        lines.append(f"HTTP/1.1 {status} OK")
        resp_hdr_lines = _header_lines(resp_hdrs)
        if resp_hdr_lines:
            lines.extend(resp_hdr_lines)
        else:
            lines.append("Content-Type: application/json")
        lines.extend(["", resp_body])
    return "\n".join(lines)


def split_request_response_body(body_section: str) -> tuple[str, str | None]:
    """从请求 Body 段中分离 Burp 风格的响应块（以 HTTP/1.x 状态行开头）."""
    if not body_section:
        return "", None
    m = re.search(r"(?:^|\n)\s*(HTTP/\d\.\d\s+\d+[^\n]*)\s*\n", body_section)
    if not m:
        return body_section.strip(), None
    req_body = body_section[: m.start()].strip()
    resp_block = body_section[m.start() :].strip()
    return req_body, resp_block if resp_block else None
