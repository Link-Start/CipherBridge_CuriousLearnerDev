"""浏览器实验室 — Playwright + JS Hook + 流量采集 (独立分析，默认不走 CryptoProxy)."""

from __future__ import annotations

import json
import os
import queue
from urllib.parse import urlparse

from PyQt6.QtCore import QThread, pyqtSignal

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOK_SCRIPT = os.path.join(ROOT, "hooks", "crypto_hook.js")
NETWORK_CAPTURE_SCRIPT = os.path.join(ROOT, "hooks", "network_capture.js")

_STATIC_SUFFIXES = (
    ".js", ".css", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".woff", ".woff2",
    ".ttf", ".map", ".webp", ".mp4", ".mp3",
)

_SCRIPT_URL_KEYWORDS = ("encrypt", "crypto", "cipher", "login", "auth", "sign", "password")


def _norm_headers(raw: dict | None, max_items: int = 40, max_val: int = 500) -> dict:
    if not raw or not isinstance(raw, dict):
        return {}
    out: dict[str, str] = {}
    for k, v in list(raw.items())[:max_items]:
        out[str(k)] = str(v)[:max_val]
    return out


class BrowserLabWorker(QThread):
    """后台线程运行 Playwright，避免阻塞 GUI."""

    log = pyqtSignal(str)
    flow_captured = pyqtSignal(dict)
    flow_updated = pyqtSignal(dict)
    hook_line = pyqtSignal(str)
    script_captured = pyqtSignal(dict)
    stopped = pyqtSignal()

    def __init__(
        self,
        url: str,
        hook_enabled: bool = True,
        headless: bool = False,
        use_mitm_proxy: bool = False,
        mitm_port: int = 8080,
        parent=None,
    ):
        super().__init__(parent)
        self.url = url.strip()
        self.hook_enabled = hook_enabled
        self.headless = headless
        self.use_mitm_proxy = use_mitm_proxy
        self.mitm_port = mitm_port
        self._stop_flag = False
        self._seen_flows: set[str] = set()
        self._pending_flow_idx: dict[str, int] = {}
        self._seen_scripts: set[str] = set()
        self._capture_count = 0
        self._script_count = 0
        self._js_capture_enabled = False
        # Playwright 回调在 Chromium 线程执行，禁止直接 emit Qt 信号（Windows 会 0xC0000409 崩溃）
        self._evt_queue: queue.SimpleQueue = queue.SimpleQueue()

    def stop(self):
        self._stop_flag = True

    def _enqueue(self, item: tuple) -> None:
        try:
            self._evt_queue.put_nowait(item)
        except Exception:
            pass

    def _flow_key(self, flow: dict) -> str:
        return f"{flow.get('method', '')}|{flow.get('url', '')}|{flow.get('request_body', '')[:200]}"

    def _ingest_flow(self, flow: dict) -> None:
        key = self._flow_key(flow)
        phase = flow.get("phase", "response")
        flow = {k: v for k, v in flow.items() if k != "phase"}

        if phase == "request":
            if key in self._seen_flows:
                return
            self._seen_flows.add(key)
            self._capture_count += 1
            pending = dict(flow)
            pending["response_body"] = pending.get("response_body") or "(等待响应…)"
            pending["status"] = 0
            pending.setdefault("request_headers", {})
            pending.setdefault("response_headers", {})
            pending["_key"] = key
            self._pending_flow_idx[key] = self._capture_count - 1
            self.flow_captured.emit(pending)
            short_url = (flow.get("url") or "")[:70]
            self.log.emit(f"→ #{self._capture_count} {flow.get('method')} {short_url}")
            return

        if key in self._pending_flow_idx:
            flow["_key"] = key
            flow["_index"] = self._pending_flow_idx.pop(key)
            self.flow_updated.emit(flow)
            short_url = (flow.get("url") or "")[:70]
            self.log.emit(
                f"✓ #{flow['_index'] + 1} [{flow.get('status')}] {short_url} "
                f"({flow.get('source', 'js-hook')})"
            )
            return

        if key in self._seen_flows:
            return
        self._seen_flows.add(key)
        self._capture_count += 1
        flow["_key"] = key
        self.flow_captured.emit(flow)
        short_url = (flow.get("url") or "")[:70]
        self.log.emit(
            f"捕获 #{self._capture_count} [{flow.get('method')}] {short_url} "
            f"({flow.get('source', 'js-hook')})"
        )

    def _flow_from_capture_data(self, data: dict) -> dict:
        return {
            "method": data.get("method", "GET"),
            "url": data.get("url", ""),
            "request_body": (data.get("request_body") or "")[:6000],
            "response_body": (data.get("response_body") or "")[:6000],
            "request_headers": _norm_headers(data.get("request_headers")),
            "response_headers": _norm_headers(data.get("response_headers")),
            "status": data.get("status", 0),
            "source": data.get("source", "js-hook"),
            "phase": data.get("phase", "response"),
        }

    def _process_capture_payload(self, payload) -> None:
        if self._stop_flag:
            return
        try:
            if isinstance(payload, str):
                data = json.loads(payload)
            elif isinstance(payload, dict):
                data = payload
            else:
                return
            self._ingest_flow(self._flow_from_capture_data(data))
        except (json.JSONDecodeError, TypeError, KeyError):
            pass

    def _handle_js_capture(self, _source, payload) -> None:
        self._enqueue(("capture", payload))

    def _drain_events(self) -> None:
        while True:
            try:
                kind, data = self._evt_queue.get_nowait()
            except queue.Empty:
                break
            if kind == "capture":
                self._process_capture_payload(data)
            elif kind == "hook":
                self.hook_line.emit(str(data))
            elif kind == "script":
                url, content = data
                self._emit_script(url, content)
            elif kind == "flow":
                self._ingest_flow(data)
            elif kind == "log":
                self.log.emit(str(data))

    @staticmethod
    def _looks_static(url: str) -> bool:
        path = urlparse(url).path.lower()
        return any(path.endswith(s) for s in _STATIC_SUFFIXES)

    @staticmethod
    def _is_api_like(request, response_headers: dict | None = None) -> bool:
        rt = request.resource_type
        if rt in ("xhr", "fetch"):
            return True
        if rt in ("image", "stylesheet", "script", "font", "media", "websocket", "manifest"):
            return False
        headers = request.headers
        accept = (headers.get("accept") or "").lower()
        ctype = (headers.get("content-type") or "").lower()
        if response_headers:
            ctype = ctype or (response_headers.get("content-type") or "").lower()
        if "json" in accept or "json" in ctype:
            return True
        if request.method in ("POST", "PUT", "PATCH", "DELETE"):
            return rt in ("xhr", "fetch", "other", "")
        return False

    def _read_response_body(self, response, max_bytes: int = 120_000) -> str:
        try:
            cl = response.headers.get("content-length") or response.headers.get("Content-Length")
            if cl:
                try:
                    if int(cl) > max_bytes:
                        return ""
                except ValueError:
                    pass
            raw = response.body()
            if not raw:
                return ""
            if len(raw) > max_bytes:
                raw = raw[:max_bytes]
            return raw.decode("utf-8", errors="replace")
        except Exception:
            return ""

    def _script_url_interesting(self, url: str) -> bool:
        low = (url or "").lower()
        return any(k in low for k in _SCRIPT_URL_KEYWORDS)

    def _on_console(self, msg) -> None:
        text = msg.text or ""
        if text.startswith("[capture] "):
            if self._js_capture_enabled:
                return
            self._enqueue(("capture", text[10:]))
            return
        if "[debug]" in text:
            self._enqueue(("hook", text))

    def _emit_script(self, url: str, content: str) -> None:
        if not url or not content or url in self._seen_scripts:
            return
        self._seen_scripts.add(url)
        self._script_count += 1
        self.script_captured.emit({
            "url": url,
            "content": content[:50000],
            "size": len(content),
        })
        short = url.split("/")[-1][:50]
        self.log.emit(f"JS #{self._script_count}: {short} ({len(content)} bytes)")

    def _should_capture_script(self, url: str, content: str) -> bool:
        if not content or len(content) < 80:
            return False
        if not self._script_url_interesting(url):
            keywords = ("encrypt", "decrypt", "cryptojs", "aes", "password", "cipher")
            head = content[:4000].lower()
            if not any(k in head for k in keywords):
                return False
        return True

    def _on_response(self, response) -> None:
        """Playwright 回退通道：仅入队，在 worker 主循环里处理."""
        if self._stop_flag:
            return
        if self._js_capture_enabled:
            try:
                req = response.request
                url = req.url or ""
                if req.resource_type != "script" and not self._script_url_interesting(url):
                    return
                content = self._read_response_body(response, max_bytes=120_000)
                if content and self._should_capture_script(url, content):
                    self._enqueue(("script", (url, content)))
            except Exception:
                pass
            return

        try:
            req = response.request
            url = req.url or ""
            if self._looks_static(url):
                return
            resp_hdrs = dict(response.headers)
            if not self._is_api_like(req, resp_hdrs):
                return
            req_body = req.post_data or ""
            resp_body = self._read_response_body(response)
            if not req_body.strip() and not resp_body.strip():
                return
            self._enqueue(("flow", {
                "method": req.method,
                "url": url,
                "request_body": req_body[:6000],
                "response_body": resp_body[:6000],
                "request_headers": _norm_headers(dict(req.headers)),
                "response_headers": _norm_headers(resp_hdrs),
                "status": response.status,
                "source": req.resource_type or "playwright",
                "phase": "response",
            }))
        except Exception as e:
            if url:
                self._enqueue(("log", f"捕获跳过 {url[:60]}: {type(e).__name__}"))

    def run(self):
        import sys
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            py = sys.executable
            self.log.emit(
                f"未安装 Playwright（当前 Python:\n  {py}）\n\n"
                f"请在该解释器下执行:\n"
                f'  "{py}" -m pip install playwright\n'
                f'  "{py}" -m playwright install chromium\n\n'
                "完成后重启 GUI。"
            )
            self.stopped.emit()
            return

        if self.use_mitm_proxy:
            self.log.emit(f"启动浏览器（经 CryptoProxy 127.0.0.1:{self.mitm_port}）…")
        else:
            self.log.emit("启动浏览器（页面内 Hook 实时回传）…")
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=self.headless,
                    args=["--ignore-certificate-errors", "--disable-web-security"],
                )
                ctx_opts: dict = {"ignore_https_errors": True}
                if self.use_mitm_proxy:
                    ctx_opts["proxy"] = {"server": f"http://127.0.0.1:{self.mitm_port}"}
                context = browser.new_context(**ctx_opts)

                if os.path.isfile(NETWORK_CAPTURE_SCRIPT):
                    context.expose_binding("cpCapture", self._handle_js_capture)
                    with open(NETWORK_CAPTURE_SCRIPT, encoding="utf-8") as f:
                        context.add_init_script(f.read())
                    self._js_capture_enabled = True
                    self.log.emit("已注入 network_capture.js（含请求/响应头）")

                if self.hook_enabled and os.path.isfile(HOOK_SCRIPT):
                    with open(HOOK_SCRIPT, encoding="utf-8") as f:
                        context.add_init_script(f.read())
                    self.log.emit("已注入 crypto_hook.js — 触发加密后显示密钥")

                context.on("response", self._on_response)
                context.on("console", self._on_console)

                page = context.new_page()
                target = self.url if self.url.startswith("http") else f"https://{self.url}"
                self.log.emit(f"打开: {target}")
                page.goto(target, wait_until="domcontentloaded", timeout=60000)
                self.log.emit("页面已打开；API 请求会立即出现在左侧列表")

                while not self._stop_flag:
                    self._drain_events()
                    page.wait_for_timeout(100)

                self._drain_events()
                context.close()
                browser.close()
        except Exception as e:
            self.log.emit(f"浏览器错误: {e}")
        self.log.emit(
            f"浏览器已关闭（流量 {self._capture_count} 条，JS {self._script_count} 个）"
        )
        self.stopped.emit()
