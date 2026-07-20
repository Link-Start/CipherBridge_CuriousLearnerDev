"""AI 实验室 Tab — 浏览器 + Hook + AI 分析 (参考 AI_JS_DEBUGGER)."""

from __future__ import annotations

import json
import os

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QTextCursor
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QPlainTextEdit, QSpinBox, QCheckBox, QSplitter,
    QListWidget, QListWidgetItem, QMessageBox, QFormLayout, QTabWidget,
    QDialog, QDialogButtonBox, QToolButton, QMenu, QSizePolicy,
)

from core.ai_config import load_ai_config, save_ai_config
from core.ai_lab_config_dialog import AILabConfigDialog
from core.ai_analyzer import AIAnalysisWorker, build_initial_messages
from core.ai_project_writer import (
    save_ai_project, guess_project_name, guess_match_rules, detect_body_format,
    PROFILES_DIR,
)
from core.browser_lab import BrowserLabWorker
from core.miniprogram_tab import MiniprogramPanel
from core.project_name import normalize_project_name
from core.icon_loader import set_btn_icon
from core.theme import (
    C, style_button, style_muted_label, setup_code_editor, style_sidebar_aux_button,
)
from codegen import codegen_for_pipeline


class _ReadyChip(QLabel):
    """采集就绪小标签：流量 / Hook / JS."""

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self._title = title
        self.setObjectName("aiReadyChip")
        self.set_count(0)

    def set_count(self, n: int) -> None:
        self.setText(f"{self._title}  {n}")
        ready = n > 0
        bg = C.get("surface2", "#3c3c3c")
        fg = C.get("primary", "#4fc1ff") if ready else C.get("text_dim", "#999")
        border = C.get("accent", "#569cd6") if ready else C.get("border", "#555")
        self.setStyleSheet(
            f"QLabel#aiReadyChip {{"
            f" background:{bg}; color:{fg}; border:1px solid {border};"
            f" border-radius:10px; padding:3px 10px; font-size:12px;"
            f"}}"
        )


class AILabTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._flows: list[dict] = []
        self._flow_keys: dict[str, int] = {}
        self._hooks: list[str] = []
        self._scripts: dict[str, str] = {}
        self._worker: BrowserLabWorker | None = None
        self._analysis_worker: AIAnalysisWorker | None = None
        self._last_result: dict | None = None
        self._last_plugin_code: str = ""
        self._auto_generate_after_analysis = False
        self._pending_generate_role: str | None = None
        self._chat_history: list[dict] = []
        self._analysis_stream_pos = 0
        self._analysis_role = "decrypt"
        self._hook_buf: list[str] = []
        self._log_buf: list[str] = []
        self._ui_flush_timer = QTimer(self)
        self._ui_flush_timer.setInterval(80)
        self._ui_flush_timer.timeout.connect(self._flush_ui_buffers)
        self._busy = False
        self._btn_labels = {
            "decrypt": "AI生成解密代理",
            "encrypt": "AI生成加密代理",
            "analyze": "AI分析",
        }
        self._build_ui()
        self._load_config()
        self._refresh_api_status()
        self._sync_action_buttons()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # —— 顶栏：流程说明 + 就绪状态 + 配置 ——
        top = QHBoxLayout()
        top.setSpacing(8)
        title = QLabel("AI 自动化分析")
        title.setObjectName("homeCardTitle")
        top.addWidget(title)
        flow_hint = QLabel("采集 → 识别 → 生成代理")
        style_muted_label(flow_hint)
        top.addWidget(flow_hint)
        top.addSpacing(8)
        self.chip_flow = _ReadyChip("流量")
        self.chip_hook = _ReadyChip("Hook")
        self.chip_js = _ReadyChip("JS")
        for chip in (self.chip_flow, self.chip_hook, self.chip_js):
            top.addWidget(chip)
        # 兼容旧代码引用
        self.hook_stats = QLabel("")
        self.hook_stats.hide()
        top.addStretch()
        self.api_status = QLabel()
        self.api_status.setObjectName("aiReadyChip")
        self.api_status.setCursor(Qt.CursorShape.PointingHandCursor)
        self.api_status.installEventFilter(self)
        top.addWidget(self.api_status)
        self.ai_cfg_btn = QPushButton("AI 配置")
        self.ai_cfg_btn.setToolTip("API Key、模型（首次使用必填）")
        self.ai_cfg_btn.clicked.connect(self._on_open_ai_config)
        style_button(self.ai_cfg_btn, "accent")
        set_btn_icon(self.ai_cfg_btn, "setting", size=14)
        top.addWidget(self.ai_cfg_btn)
        self.adv_cfg_btn = QPushButton("高级")
        self.adv_cfg_btn.setToolTip("浏览器经解密端转发等")
        self.adv_cfg_btn.clicked.connect(self._on_open_adv_config)
        style_sidebar_aux_button(self.adv_cfg_btn)
        top.addWidget(self.adv_cfg_btn)
        layout.addLayout(top)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)

        # —— 左：采集 ——
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.setSpacing(6)
        src_title = QLabel("① 采集素材")
        src_title.setObjectName("homeSectionTitle")
        ll.addWidget(src_title)
        self.source_tabs = QTabWidget()
        self.source_tabs.addTab(self._build_browser_source(), "网页")
        self.miniprogram_panel = MiniprogramPanel(compact=True)
        self.miniprogram_panel.scripts_ready.connect(self.load_miniprogram_scripts)
        self.miniprogram_panel.request_ai_analyze.connect(self._run_miniprogram_ai)
        self.miniprogram_panel.flow_captured.connect(self._on_miniprogram_flow)
        self.miniprogram_panel.flow_updated.connect(self._on_miniprogram_flow_updated)
        self.miniprogram_panel.flow_selected.connect(self._show_external_flow)
        self.miniprogram_panel.capture_log.connect(self._log)
        self.source_tabs.addTab(self.miniprogram_panel, "小程序")
        ll.addWidget(self.source_tabs, 1)
        splitter.addWidget(left)

        # —— 右：一键生成（核心） ——
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(10, 0, 0, 0)
        rl.setSpacing(8)

        out_title = QLabel("② 识别并生成")
        out_title.setObjectName("homeSectionTitle")
        rl.addWidget(out_title)

        self.next_hint = QLabel()
        self.next_hint.setObjectName("aiNextHint")
        self.next_hint.setWordWrap(True)
        rl.addWidget(self.next_hint)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        self.analyze_btn = QPushButton(self._btn_labels["analyze"])
        self.analyze_btn.setToolTip("只跑 AI，不写文件")
        self.analyze_btn.clicked.connect(self._run_analysis)
        style_button(self.analyze_btn, "danger_fill")
        set_btn_icon(self.analyze_btn, "search", size=16)
        self.gen_decrypt_btn = QPushButton(self._btn_labels["decrypt"])
        self.gen_decrypt_btn.setToolTip("AI 分析并写出解密端 plugin.py")
        self.gen_decrypt_btn.clicked.connect(lambda: self._run_analyze_and_generate("decrypt"))
        style_button(self.gen_decrypt_btn, "danger_fill")
        set_btn_icon(self.gen_decrypt_btn, "decrypt", size=16)
        self.gen_encrypt_btn = QPushButton(self._btn_labels["encrypt"])
        self.gen_encrypt_btn.setToolTip("AI 分析并写出加密端 plugin.py")
        self.gen_encrypt_btn.clicked.connect(lambda: self._run_analyze_and_generate("encrypt"))
        style_button(self.gen_encrypt_btn, "danger_fill")
        set_btn_icon(self.gen_encrypt_btn, "encrypt", size=16)
        for btn in (self.analyze_btn, self.gen_decrypt_btn, self.gen_encrypt_btn):
            btn.setFixedHeight(36)
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            btn_row.addWidget(btn, 1)
        rl.addLayout(btn_row)

        sec_row = QHBoxLayout()
        sec_row.setSpacing(8)
        clear_btn = QPushButton("清空采集")
        clear_btn.setToolTip("清空流量 / Hook / JS（保留分析结果）")
        clear_btn.clicked.connect(self._clear_capture)
        style_sidebar_aux_button(clear_btn)
        set_btn_icon(clear_btn, "clear", size=14)
        clear_btn.setMinimumHeight(30)
        sec_row.addWidget(clear_btn)

        more_btn = QToolButton()
        more_btn.setText("更多")
        more_btn.setToolTip("Hook 分析、加载到构建器等")
        more_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        more_menu = QMenu(self)
        self._act_hook_analyze = more_menu.addAction("分析 Hook + JS", self._run_hook_analysis)
        more_menu.addSeparator()
        more_menu.addAction("加载到构建器", self._load_to_builder)
        more_menu.addAction("加载到解析器", self._load_fields_to_parser)
        more_btn.setMenu(more_menu)
        more_btn.setMinimumHeight(30)
        sec_row.addWidget(more_btn)
        sec_row.addStretch()
        rl.addLayout(sec_row)

        self.result_tabs = QTabWidget()
        self.result_view = QPlainTextEdit()
        setup_code_editor(self.result_view)
        self.result_view.setReadOnly(True)
        self.result_view.setPlaceholderText("点上方「AI生成解密代理」后，识别结果会显示在这里")
        self.plugin_view = QPlainTextEdit()
        setup_code_editor(self.plugin_view)
        self.plugin_view.setReadOnly(True)
        self.plugin_view.setPlaceholderText("生成成功后的 plugin.py")
        self.flow_detail_view = QPlainTextEdit()
        setup_code_editor(self.flow_detail_view)
        self.flow_detail_view.setReadOnly(True)
        self.flow_detail_view.setPlaceholderText("在左侧点选一条流量查看请求/响应")
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(800)
        self.log_view.setPlaceholderText("运行日志")
        self.result_tabs.addTab(self.result_view, "分析结果")
        self.result_tabs.addTab(self.plugin_view, "代理脚本")
        self.result_tabs.addTab(self.flow_detail_view, "请求详情")
        self.result_tabs.addTab(self.log_view, "日志")
        rl.addWidget(self.result_tabs, 1)

        chat_row = QHBoxLayout()
        chat_row.setSpacing(6)
        self.followup_edit = QLineEdit()
        self.followup_edit.setPlaceholderText("追问补充，例如：密钥是 your-16-byte-key!")
        self.followup_edit.returnPressed.connect(self._continue_chat)
        self.continue_btn = QPushButton("发送")
        self.continue_btn.setEnabled(False)
        self.continue_btn.clicked.connect(self._continue_chat)
        style_sidebar_aux_button(self.continue_btn)
        chat_row.addWidget(self.followup_edit, 1)
        chat_row.addWidget(self.continue_btn)
        rl.addLayout(chat_row)

        splitter.addWidget(right)
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 5)
        splitter.setSizes([400, 600])
        layout.addWidget(splitter, 1)
        self._update_flow_empty_hint()
        self._update_next_hint()

    def _build_browser_source(self) -> QWidget:
        """网页采集：URL + 启动 + 流量/Hook."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(8)

        tip = QLabel("打开目标页，自动抓 XHR/Fetch；勾选 Hook 可抓密钥。")
        tip.setWordWrap(True)
        style_muted_label(tip)
        layout.addWidget(tip)

        bar = QHBoxLayout()
        bar.setSpacing(6)
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("https://example.com  （回车启动）")
        self.url_edit.setMinimumHeight(32)
        self.url_edit.returnPressed.connect(self._start_browser)
        bar.addWidget(self.url_edit, 1)
        self.hook_check = QCheckBox("Hook 密钥")
        self.hook_check.setChecked(True)
        self.hook_check.setToolTip("注入 crypto_hook.js，抓 CryptoJS / RSA 等密钥")
        bar.addWidget(self.hook_check)
        layout.addLayout(bar)

        ctrl = QHBoxLayout()
        ctrl.setSpacing(8)
        self.start_btn = QPushButton("启动采集")
        self.stop_btn = QPushButton("停止")
        self.stop_btn.setEnabled(False)
        self.start_btn.clicked.connect(self._start_browser)
        self.stop_btn.clicked.connect(self._stop_browser)
        style_button(self.start_btn, "primary")
        style_sidebar_aux_button(self.stop_btn)
        set_btn_icon(self.start_btn, "play", size=16)
        set_btn_icon(self.stop_btn, "stop", size=14)
        self.start_btn.setMinimumHeight(36)
        self.stop_btn.setMinimumHeight(36)
        self.stop_btn.setFixedWidth(72)
        ctrl.addWidget(self.start_btn, 1)
        ctrl.addWidget(self.stop_btn)
        layout.addLayout(ctrl)

        capture_tabs = QTabWidget()
        flow_page = QWidget()
        fl = QVBoxLayout(flow_page)
        fl.setContentsMargins(0, 4, 0, 0)
        fl.setSpacing(4)
        self.flow_empty_hint = QLabel()
        self.flow_empty_hint.setObjectName("homeEmptyHint")
        self.flow_empty_hint.setWordWrap(True)
        fl.addWidget(self.flow_empty_hint)
        self.flow_list = QListWidget()
        self.flow_list.itemClicked.connect(self._on_flow_selected)
        fl.addWidget(self.flow_list, 1)
        capture_tabs.addTab(flow_page, "流量")

        hook_page = QWidget()
        hl = QVBoxLayout(hook_page)
        hl.setContentsMargins(0, 4, 0, 0)
        self.hook_view = QPlainTextEdit()
        self.hook_view.setReadOnly(True)
        self.hook_view.setMaximumBlockCount(3000)
        self.hook_view.setPlaceholderText("启动后操作页面，密钥 / 算法会出现在这里")
        hl.addWidget(self.hook_view)
        capture_tabs.addTab(hook_page, "Hook")
        layout.addWidget(capture_tabs, 1)
        return page

    def _on_open_ai_config(self) -> None:
        self._open_config_dialog("ai")

    def _on_open_adv_config(self) -> None:
        self._open_config_dialog("advanced")

    def eventFilter(self, obj, event):
        from PyQt6.QtCore import QEvent
        if obj is getattr(self, "api_status", None) and event.type() == QEvent.Type.MouseButtonPress:
            self._open_config_dialog("ai")
            return True
        return super().eventFilter(obj, event)

    def _open_config_dialog(self, section: str = "ai") -> bool:
        """打开配置弹窗，保存成功返回 True."""
        dlg = AILabConfigDialog(self, initial_tab=section)
        dlg.load_from(load_ai_config())
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return False
        cfg = load_ai_config()
        updates = dlg.collect(hook_enabled=self.hook_check.isChecked())
        for key, val in updates.items():
            if key == "browser" and isinstance(cfg.get("browser"), dict):
                cfg["browser"] = {**cfg["browser"], **val}
            else:
                cfg[key] = val
        save_ai_config(cfg)
        self._load_config()
        self._log("配置已保存到 config/ai.yaml")
        self._refresh_api_status()
        return True

    def _load_config(self):
        cfg = load_ai_config()
        browser = cfg.get("browser", {})
        self.hook_check.setChecked(bool(browser.get("hook_enabled", True)))
        last_url = (browser.get("last_url") or "").strip()
        if last_url and not self.url_edit.text().strip():
            self.url_edit.setText(last_url)

    def _browser_cfg(self) -> dict:
        return load_ai_config().get("browser", {})

    def _save_config(self):
        """从当前 Hook 勾选同步 browser.hook_enabled / last_url 到配置文件."""
        cfg = load_ai_config()
        browser = cfg.get("browser", {})
        if not isinstance(browser, dict):
            browser = {}
        browser["hook_enabled"] = self.hook_check.isChecked()
        url = self.url_edit.text().strip()
        if url:
            browser["last_url"] = url
        cfg["browser"] = browser
        save_ai_config(cfg)

    def _refresh_api_status(self):
        if not hasattr(self, "api_status"):
            return
        cfg = load_ai_config()
        ok = bool(cfg.get("api_key"))
        model = (cfg.get("model") or "").strip() or "未选模型"
        if ok:
            self.api_status.setText(f"API 就绪 · {model}")
            fg = C.get("primary", "#6fbf7a")
            border = C.get("primary", "#6fbf7a")
        else:
            self.api_status.setText("未配置 API")
            fg = C.get("warn", "#c4a85a")
            border = C.get("warn", "#c4a85a")
        bg = C.get("surface2", "#30363f")
        self.api_status.setStyleSheet(
            f"QLabel#aiReadyChip {{ background:{bg}; color:{fg};"
            f" border:1px solid {border}; border-radius:10px;"
            f" padding:3px 10px; font-size:12px; }}"
        )
        self.api_status.setToolTip(
            "已配置，可直接生成代理" if ok else "点击「AI 配置」填写 API Key"
        )

    def _has_capture_data(self) -> bool:
        return bool(self._flows or self._hooks or self._scripts)

    def _sync_action_buttons(self):
        """无素材时禁用生成按钮，并给出明确提示."""
        if self._busy:
            return
        ready = self._has_capture_data()
        for btn in (self.gen_decrypt_btn, self.gen_encrypt_btn, self.analyze_btn):
            btn.setEnabled(ready)
        self._act_hook_analyze.setEnabled(ready)
        tip = (
            "已有采集数据，可生成代理"
            if ready
            else "请先在左侧「网页」采集或「小程序」解包/抓包"
        )
        self.gen_decrypt_btn.setToolTip(f"写出解密端 plugin.py — {tip}")
        self.gen_encrypt_btn.setToolTip(f"写出加密端 plugin.py — {tip}")
        self.analyze_btn.setToolTip(f"只分析不写文件 — {tip}")

    def _log(self, msg: str):
        self._log_buf.append(msg)
        if not self._ui_flush_timer.isActive():
            self._ui_flush_timer.start()

    def _flush_ui_buffers(self):
        if self._log_buf:
            self.log_view.appendPlainText("\n".join(self._log_buf))
            self._log_buf.clear()
        if self._hook_buf:
            self.hook_view.appendPlainText("\n".join(self._hook_buf))
            self._hook_buf.clear()
        if self._hook_buf or self._log_buf:
            return
        self._ui_flush_timer.stop()
        self._refresh_capture_stats()

    @staticmethod
    def _clean_flow(flow: dict) -> dict:
        return {k: v for k, v in flow.items() if not str(k).startswith("_")}

    def _start_browser(self):
        url = self.url_edit.text().strip()
        if not url:
            QMessageBox.warning(self, "提示", "请输入目标 URL")
            self.url_edit.setFocus()
            return
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
            self.url_edit.setText(url)
        if self._worker and self._worker.isRunning():
            QMessageBox.information(self, "提示", "浏览器已在运行")
            return
        browser = self._browser_cfg()
        self._save_config()
        self._worker = BrowserLabWorker(
            url=url,
            hook_enabled=self.hook_check.isChecked(),
            use_mitm_proxy=bool(browser.get("use_mitm_proxy", False)),
            mitm_port=int(browser.get("mitm_port", 8080)),
        )
        self._worker.log.connect(self._log)
        self._worker.flow_captured.connect(self._on_flow)
        self._worker.flow_updated.connect(self._on_flow_updated)
        self._worker.hook_line.connect(self._on_hook)
        self._worker.script_captured.connect(self._on_script)
        self._worker.stopped.connect(self._on_browser_stopped)
        self._worker.start()
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.start_btn.setText("采集中…")
        self._update_flow_empty_hint()
        self._set_hint(
            "浏览器已启动，请在页面操作以产生流量；采到数据后即可生成代理。",
            kind="info",
        )
        self.result_tabs.setCurrentWidget(self.log_view)

    def _stop_browser(self):
        if self._worker and self._worker.isRunning():
            self._worker.stop()

    def _on_browser_stopped(self):
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.start_btn.setText("启动采集")
        set_btn_icon(self.start_btn, "play", size=16)
        self._worker = None
        self._clear_session_capture()
        self._update_next_hint()

    def _on_flow(self, flow: dict):
        """浏览器采集 → 写入 _flows 并显示在「浏览器 → 流量」列表."""
        self._ingest_flow(flow, show_in_browser_list=True)

    def _on_miniprogram_flow(self, flow: dict):
        """小程序抓包 → 只写入 _flows 供 AI，不进浏览器流量列表."""
        self._ingest_flow(flow, show_in_browser_list=False)

    def _ingest_flow(self, flow: dict, *, show_in_browser_list: bool):
        clean = self._clean_flow(flow)
        idx = len(self._flows)
        self._flows.append(clean)
        key = flow.get("_key") or flow.get("key")
        if key is not None and str(key):
            self._flow_keys[str(key)] = idx
        if show_in_browser_list:
            pending = clean.get("status") == 0 and clean.get("response_body") == "(等待响应…)"
            prefix = "… " if pending else ""
            item = QListWidgetItem(f"{prefix}{clean.get('method')} {clean.get('url', '')[:78]}")
            item.setData(Qt.ItemDataRole.UserRole, idx)
            self.flow_list.addItem(item)
            self._update_flow_empty_hint()
        self._refresh_capture_stats()

    def _on_flow_updated(self, flow: dict):
        """浏览器流量更新（同步列表项）."""
        self._update_ingested_flow(flow, update_browser_list=True)

    def _on_miniprogram_flow_updated(self, flow: dict):
        """小程序流量更新（不碰浏览器列表）."""
        self._update_ingested_flow(flow, update_browser_list=False)

    def _update_ingested_flow(self, flow: dict, *, update_browser_list: bool):
        key = flow.get("_key") or flow.get("key")
        idx = None
        if key is not None and str(key) in self._flow_keys:
            idx = self._flow_keys[str(key)]
        else:
            idx = flow.get("_index")
        if idx is None or idx < 0 or idx >= len(self._flows):
            return
        clean = self._clean_flow(flow)
        self._flows[idx] = clean
        if update_browser_list:
            for i in range(self.flow_list.count()):
                item = self.flow_list.item(i)
                if item and item.data(Qt.ItemDataRole.UserRole) == idx:
                    item.setText(
                        f"[{clean.get('status')}] {clean.get('method')} "
                        f"{clean.get('url', '')[:75]}"
                    )
                    break
            cur = self.flow_list.currentItem()
            if cur is not None and cur.data(Qt.ItemDataRole.UserRole) == idx:
                self.flow_detail_view.setPlainText(self._format_flow_detail(clean))
        self._refresh_capture_stats()

    def _on_hook(self, line: str):
        self._hooks.append(line)
        self._hook_buf.append(line)
        if not self._ui_flush_timer.isActive():
            self._ui_flush_timer.start()

    def _on_script(self, item: dict):
        url = item.get("url", "")
        content = item.get("content", "")
        if url and content:
            self._scripts[url] = content
            self._refresh_capture_stats()

    def load_miniprogram_scripts(self, scripts: dict[str, str], meta: dict | None = None) -> None:
        """由「小程序」子页注入反编译 JS，供本页右侧 AI 分析."""
        if not scripts:
            return
        self._scripts.update(scripts)
        self._refresh_capture_stats()
        info = ""
        if meta:
            aid = meta.get("appid") or ""
            out = meta.get("out_dir") or ""
            info = f"（AppID={aid} 目录={out}）" if aid or out else ""
        self._log(f"已载入小程序反编译脚本 {len(scripts)} 个{info}")
        if hasattr(self, "hook_view"):
            self.hook_view.appendPlainText(
                f"[miniprogram] loaded {len(scripts)} scripts{info}"
            )
        self.result_tabs.setCurrentWidget(self.result_view)
        self._set_hint(
            f"已载入小程序脚本 {len(scripts)} 个。可点「AI生成解密代理」，或左侧「AI 识别」。",
            kind="ready",
        )
        self._sync_action_buttons()

    def _refresh_capture_stats(self):
        n_flow = len(self._flows)
        n_hook = len(self._hooks)
        n_js = len(self._scripts)
        if hasattr(self, "chip_flow"):
            self.chip_flow.set_count(n_flow)
            self.chip_hook.set_count(n_hook)
            self.chip_js.set_count(n_js)
        if hasattr(self, "hook_stats") and self.hook_stats.isVisible():
            self.hook_stats.setText(
                f"采集  流量 {n_flow}  ·  Hook {n_hook}  ·  JS {n_js}"
            )
        self._update_next_hint()

    def _set_hint(self, text: str, *, kind: str = "info"):
        """更新右侧引导条；kind: empty | info | ready | ok | busy | warn."""
        if not hasattr(self, "next_hint"):
            return
        self.next_hint.setText(text)
        accent = {
            "empty": C.get("warn", "#c4a85a"),
            "warn": C.get("warn", "#c4a85a"),
            "info": C.get("accent", "#6b9fd4"),
            "ready": C.get("accent", "#6b9fd4"),
            "ok": C.get("primary", "#6fbf7a"),
            "busy": C.get("teal", "#6eb8ae"),
        }.get(kind, C.get("accent", "#6b9fd4"))
        bg = C.get("surface", "#262b33")
        border = C.get("border", "#3d4450")
        dim = C.get("text_dim", "#8b929e")
        self.next_hint.setStyleSheet(
            f"QLabel#aiNextHint {{ background:{bg}; color:{dim};"
            f" border:1px solid {border}; border-left:3px solid {accent};"
            f" border-radius:8px; padding:10px 12px; }}"
        )

    def _update_next_hint(self):
        if not hasattr(self, "next_hint"):
            return
        if getattr(self, "_busy", False):
            return
        has_data = self._has_capture_data()
        api_ok = bool(load_ai_config().get("api_key"))
        if self._last_plugin_code:
            self._set_hint(
                "已生成代理脚本 → 打开「代理脚本」查看，或「更多 → 加载到构建器」微调。"
                " 左侧控制面板可直接启动解密/加密端。",
                kind="ok",
            )
        elif self._last_result:
            self._set_hint(
                "分析完成。可再点「AI生成解密/加密代理」写出 plugin.py，"
                "或在下方追问补充密钥与字段。",
                kind="ready",
            )
        elif has_data:
            parts = []
            if self._flows:
                parts.append(f"流量 {len(self._flows)}")
            if self._hooks:
                parts.append(f"Hook {len(self._hooks)}")
            if self._scripts:
                parts.append(f"JS {len(self._scripts)}")
            extra = "" if api_ok else "（请先点右上角配置 API）"
            self._set_hint(
                f"已采集 {' · '.join(parts)}。下一步：点「AI生成解密代理」或「AI生成加密代理」。{extra}",
                kind="ready" if api_ok else "warn",
            )
        else:
            self._set_hint(
                "① 左侧「网页」填 URL 启动采集，或「小程序」解包/抓包  "
                "② 右上角配置 API  ③ 点 AI生成解密/加密代理",
                kind="empty",
            )
        self._sync_action_buttons()

    def _update_flow_empty_hint(self):
        if self._flows:
            self.flow_empty_hint.hide()
            return
        self.flow_empty_hint.show()
        if self.stop_btn.isEnabled():
            self.flow_empty_hint.setText("等待流量…在页面里登录或点几下触发请求即可。")
        else:
            self.flow_empty_hint.setText(
                "1. 填入目标 URL（可回车启动）\n"
                "2. 勾选 Hook 密钥（推荐）\n"
                "3. 点「启动采集」后在页面操作"
            )

    @staticmethod
    def _format_headers_text(hdrs: dict | None) -> str:
        if not hdrs or not isinstance(hdrs, dict):
            return "(无)"
        lines = []
        for k, v in hdrs.items():
            try:
                lines.append(f"  {k}: {v}")
            except Exception:
                lines.append(f"  {k}: ?")
        return "\n".join(lines) if lines else "(无)"

    @staticmethod
    def _safe_flow_text(val) -> str:
        if val is None:
            return ""
        if isinstance(val, (dict, list)):
            try:
                return json.dumps(val, ensure_ascii=False, indent=2)
            except Exception:
                return str(val)
        return str(val)

    def _format_flow_detail(self, f: dict) -> str:
        req_body = self._safe_flow_text(f.get("request_body", ""))[:8000]
        resp_body = self._safe_flow_text(f.get("response_body", ""))[:8000]
        return (
            f"{f.get('method')} {f.get('url')}\n\n"
            f"--- Request Headers ---\n"
            f"{self._format_headers_text(f.get('request_headers'))}\n\n"
            f"--- Request Body ---\n{req_body}\n\n"
            f"--- Response Headers ---\n"
            f"{self._format_headers_text(f.get('response_headers'))}\n\n"
            f"--- Response ({f.get('status')}) ---\n{resp_body}"
        )

    def _on_flow_selected(self, item: QListWidgetItem):
        if item is None:
            return
        try:
            idx = item.data(Qt.ItemDataRole.UserRole)
            if idx is None:
                idx = self.flow_list.row(item)
            if not isinstance(idx, int) or idx < 0 or idx >= len(self._flows):
                return
            f = self._flows[idx]
            self.flow_detail_view.setPlainText(self._format_flow_detail(f))
            self.result_tabs.setCurrentWidget(self.flow_detail_view)
        except Exception as e:
            self._log(f"显示流量详情失败: {e}")

    def _show_external_flow(self, flow: dict):
        """小程序页流量列表点选 → 右侧详情."""
        clean = self._clean_flow(flow)
        self.flow_detail_view.setPlainText(self._format_flow_detail(clean))
        self.result_tabs.setCurrentWidget(self.flow_detail_view)

    def _clear_session_capture(self):
        """关闭浏览器时清空本次捕获数据（保留 AI 分析结果与已生成脚本）."""
        self._flows.clear()
        self._flow_keys.clear()
        self._hooks.clear()
        self._scripts.clear()
        self.flow_list.clear()
        self.hook_view.clear()
        self.log_view.clear()
        self._hook_buf.clear()
        self._log_buf.clear()
        self._ui_flush_timer.stop()
        panel = getattr(self, "miniprogram_panel", None)
        if panel is not None and hasattr(panel, "clear_local_flows"):
            panel.clear_local_flows()
        self._refresh_capture_stats()
        self._update_flow_empty_hint()
        self.flow_detail_view.clear()
        if not self._last_result:
            self.result_view.clear()

    def _reset_chat(self):
        self._chat_history.clear()
        self.continue_btn.setEnabled(False)
        self.followup_edit.clear()

    def _clear_capture(self):
        self._clear_session_capture()
        self._last_result = None
        self._last_plugin_code = ""
        self.result_view.clear()
        self.plugin_view.clear()
        self.flow_detail_view.clear()
        self._reset_chat()
        if self._analysis_worker and self._analysis_worker.isRunning():
            self._analysis_worker.requestInterruption()

    def _set_analysis_buttons_enabled(self, enabled: bool):
        self._busy = not enabled
        if not enabled:
            self.gen_decrypt_btn.setText("分析中…")
            self.gen_encrypt_btn.setText("分析中…")
            self.analyze_btn.setText("分析中…")
            self.gen_decrypt_btn.setEnabled(False)
            self.gen_encrypt_btn.setEnabled(False)
            self.analyze_btn.setEnabled(False)
            self._act_hook_analyze.setEnabled(False)
            self._set_hint(
                "AI 正在分析，请稍候…结果会实时出现在「分析结果」。",
                kind="busy",
            )
            self.result_tabs.setCurrentWidget(self.result_view)
        else:
            self.gen_decrypt_btn.setText(self._btn_labels["decrypt"])
            self.gen_encrypt_btn.setText(self._btn_labels["encrypt"])
            self.analyze_btn.setText(self._btn_labels["analyze"])
            set_btn_icon(self.gen_decrypt_btn, "decrypt", size=16)
            set_btn_icon(self.gen_encrypt_btn, "encrypt", size=16)
            set_btn_icon(self.analyze_btn, "search", size=16)
            self._sync_action_buttons()
            self._update_next_hint()

    def _run_analyze_and_generate(self, role: str):
        """一键：按角色 AI 分析并生成 plugin.py."""
        if self._analysis_worker and self._analysis_worker.isRunning():
            self._log("分析进行中，请稍候…")
            return
        if not self._has_capture_data():
            self.source_tabs.setCurrentIndex(0)
            QMessageBox.warning(
                self, "提示",
                "请先在左侧采集：网页启动采集，或小程序解包 / 抓包。",
            )
            return
        cfg = self._get_ai_cfg()
        if not cfg:
            return
        self._pending_generate_role = role
        self._auto_generate_after_analysis = True
        self._start_analysis_worker(cfg, role=role, focus_hook=True)

    def _ask_project_options(self, code_role: str = "decrypt") -> dict | None:
        default_name = guess_project_name(self.url_edit.text().strip(), self._flows)
        match = guess_match_rules(self._flows, self.url_edit.text().strip())
        type_label = "解密脚本" if code_role == "decrypt" else "加密脚本"

        dlg = QDialog(self)
        dlg.setWindowTitle(f"生成{type_label}")
        dlg.setMinimumWidth(420)
        form = QFormLayout(dlg)
        name_edit = QLineEdit(default_name)
        name_edit.setPlaceholderText("小写字母/数字/下划线（会自动修正）")
        form.addRow("项目名称:", name_edit)
        form.addRow("脚本类型:", QLabel(type_label))
        match_label = QLabel(
            f"Host: {', '.join(match['host'])}\n"
            f"Path: {', '.join(match['path'])}\n"
            f"Methods: {', '.join(match['methods'])}"
        )
        match_label.setWordWrap(True)
        style_muted_label(match_label)
        form.addRow("匹配规则:", match_label)
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        form.addRow(btns)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return None

        return {
            "name": normalize_project_name(name_edit.text().strip()),
            "roles": [code_role],
            "match": match,
            "code_role": code_role,
        }

    def _generate_plugin(self, *, silent: bool = False, code_role: str | None = None) -> bool:
        if not self._last_result or not self._last_result.get("steps"):
            if not silent:
                QMessageBox.information(self, "提示", "请先运行 AI 分析并得到有效步骤")
            return False

        role = code_role or self._pending_generate_role or self._analysis_role or "decrypt"
        opts = self._ask_project_options(role)
        if not opts:
            return False

        steps = self._last_result["steps"]
        body_format = detect_body_format(self._flows)
        summary = self._last_result.get("summary", "")
        confidence = self._last_result.get("confidence", "")

        if confidence == "low" and not silent:
            reply = QMessageBox.question(
                self,
                "置信度较低",
                f"AI 分析置信度为 low：\n{summary}\n\n仍要生成代理脚本吗？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return False

        profile_path = os.path.join(PROFILES_DIR, f"{opts['name']}.yaml")
        overwrite = False
        if os.path.exists(profile_path):
            reply = QMessageBox.question(
                self,
                "项目已存在",
                f"项目 '{opts['name']}' 已存在，是否覆盖？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return False
            overwrite = True

        try:
            name, code = save_ai_project(
                opts["name"],
                steps,
                roles=opts["roles"],
                code_role=opts.get("code_role"),
                match=opts["match"],
                body_format=body_format,
                description=summary,
                flows=self._flows,
                fallback_url=self.url_edit.text().strip(),
                overwrite=overwrite,
            )
        except Exception as e:
            if not silent:
                QMessageBox.critical(self, "生成失败", str(e))
            self._log(f"生成失败: {e}")
            return False

        self._last_plugin_code = code
        self.plugin_view.setPlainText(code)
        self.result_tabs.setCurrentWidget(self.plugin_view)
        self._log(f"已生成项目: {name} → plugins/{name}/plugin.py")
        self._sync_to_main_window(name, steps, code, body_format)
        type_label = "加密" if opts.get("code_role") == "encrypt" else "解密"
        self._set_hint(
            f"已生成{type_label}脚本 plugins/{name}/plugin.py，"
            f"控制面板已切到「{name}」，可直接启动代理。",
            kind="ok",
        )
        return True

    def _sync_to_main_window(self, name: str, steps: list, code: str, body_format: str):
        import gui as gui_mod
        main = self.window()
        gui_mod.shared_pipeline.steps = [dict(s) for s in steps]
        gui_mod.shared_pipeline.body_format = body_format
        gui_mod.shared_pipeline._plugin_code = code
        gui_mod.shared_pipeline._notify()

        if hasattr(main, "control"):
            main.control._refresh_profiles()
            main.control.profile_combo.setCurrentText(name)

        if hasattr(main, "visual_builder_tab"):
            vb = main.visual_builder_tab
            vb._clear_all()
            for step in steps:
                vb._add_step(step["type"])
            for i, step in enumerate(steps):
                if i < len(gui_mod.shared_pipeline.steps):
                    gui_mod.shared_pipeline.steps[i]["params"].update(step.get("params", {}))
            vb._rebuild_steps()
            vb.code_preview.setPlainText(code)

        if hasattr(main, "parser_tab"):
            main.parser_tab.code_preview.setPlainText(code)

        if hasattr(gui_mod, "log_signal"):
            gui_mod.log_signal.append_log.emit("INFO", f"AI 实验室已生成项目: {name}")

    def _get_ai_cfg(self) -> dict | None:
        cfg = load_ai_config()
        if not cfg.get("api_key"):
            QMessageBox.warning(self, "提示", "请先点击「AI 配置」填写 API Key")
            self._open_config_dialog("ai")
            cfg = load_ai_config()
            if not cfg.get("api_key"):
                return None
        return cfg

    def _start_analysis_worker(
        self,
        cfg: dict,
        *,
        role: str = "decrypt",
        focus_hook: bool = False,
        focus_miniprogram: bool = False,
        require_hooks: bool = False,
    ):
        if require_hooks and not self._hooks and not self._scripts:
            QMessageBox.warning(
                self, "无 Hook/JS 数据",
                "Hook 日志与 JS 均为空。\n\n"
                "1. 勾选「JS Hook」\n"
                "2. 启动浏览器后在页面执行登录（触发加密）\n"
                "3. 确认左侧 Hook 日志出现 [debug] Key …",
            )
            return

        self._reset_chat()
        if focus_miniprogram:
            title = "▶ 小程序静态分析中…\n\n"
            log_title = "—— 开始小程序加解密识别 ——"
        elif focus_hook:
            title = "▶ Hook+JS 分析中…\n\n"
            log_title = f"—— 开始{'解密' if role == 'decrypt' else '加密'}脚本分析 ——"
        else:
            title = "▶ AI 分析中，实时输出如下…\n\n"
            log_title = f"—— 开始 AI 分析 ({'解密' if role == 'decrypt' else '加密'}) ——"
        self.result_view.clear()
        self.result_view.setPlainText(title)
        self._analysis_stream_pos = len(self.result_view.toPlainText())
        self._set_analysis_buttons_enabled(False)
        self.continue_btn.setEnabled(False)
        self._log(log_title)
        self._log(
            f"送入: 流量 {len(self._flows)} · Hook {len(self._hooks)} · JS {len(self._scripts)}"
        )

        self._analysis_role = role
        self._chat_history = build_initial_messages(
            list(self._flows),
            list(self._hooks),
            role,
            scripts=dict(self._scripts),
            focus_hook=focus_hook,
            focus_miniprogram=focus_miniprogram,
        )

        self._analysis_worker = AIAnalysisWorker(
            list(self._flows),
            list(self._hooks),
            cfg,
            role=role,
            scripts=dict(self._scripts),
            focus_hook=focus_hook,
            focus_miniprogram=focus_miniprogram,
        )
        self._analysis_worker.log.connect(self._log)
        self._analysis_worker.chunk.connect(self._on_analysis_chunk)
        self._analysis_worker.finished_ok.connect(self._on_analysis_done)
        self._analysis_worker.failed.connect(self._on_analysis_failed)
        self._analysis_worker.start()

    def _run_analysis(self):
        if self._analysis_worker and self._analysis_worker.isRunning():
            self._log("分析进行中，请稍候…")
            return
        if not self._flows and not self._hooks and not self._scripts:
            QMessageBox.warning(
                self, "提示",
                "请先在左侧「网页」或「小程序」采集流量 / Hook / JS。",
            )
            return
        cfg = self._get_ai_cfg()
        if not cfg:
            return
        # 若主要是小程序脚本，走小程序静态分析提示
        mini_n = sum(1 for k in self._scripts if str(k).startswith("miniprogram://"))
        focus_mp = mini_n > 0 and not self._flows and not self._hooks
        if not self._hooks and not self._scripts:
            self._log("提示: 无 Hook / JS，分析结果可能不准确")
        self._start_analysis_worker(
            cfg, role="decrypt",
            focus_hook=False,
            focus_miniprogram=focus_mp,
        )

    def _run_hook_analysis(self):
        if self._analysis_worker and self._analysis_worker.isRunning():
            self._log("分析进行中，请稍候…")
            return
        cfg = self._get_ai_cfg()
        if not cfg:
            return
        self._start_analysis_worker(cfg, role="decrypt", focus_hook=True, require_hooks=False)

    def _run_miniprogram_ai(self):
        """小程序页「AI 识别」：反编译 JS +（可选）代理抓包流量."""
        if self._analysis_worker and self._analysis_worker.isRunning():
            self._log("分析进行中，请稍候…")
            return
        panel = getattr(self, "miniprogram_panel", None)
        if panel is not None and hasattr(panel, "_emit_scripts") and panel._last_result:
            panel._emit_scripts(silent=True)
        mini_n = sum(1 for k in self._scripts if str(k).startswith("miniprogram://"))
        if mini_n <= 0 and not self._flows:
            QMessageBox.warning(
                self, "提示",
                "请先「解包」载入脚本，或「启动抓包」采集流量后再识别。",
            )
            return
        cfg = self._get_ai_cfg()
        if not cfg:
            return
        self._log(
            f"小程序分析：脚本 {mini_n} · 流量 {len(self._flows)}，开始识别…"
        )
        self.result_tabs.setCurrentWidget(self.result_view)
        self._start_analysis_worker(
            cfg, role="decrypt",
            focus_hook=False,
            focus_miniprogram=True,
            require_hooks=False,
        )

    def _continue_chat(self):
        if self._analysis_worker and self._analysis_worker.isRunning():
            self._log("AI 回复中，请稍候…")
            return
        text = self.followup_edit.text().strip()
        if not text:
            QMessageBox.information(self, "提示", "请输入追问内容")
            return
        if not self._chat_history:
            QMessageBox.information(self, "提示", "请先运行一次「AI 分析」")
            return

        cfg = load_ai_config()
        if not cfg.get("api_key"):
            QMessageBox.warning(self, "提示", "请先点击「AI 配置」填写 API Key")
            self._open_config_dialog("ai")
            cfg = load_ai_config()
            if not cfg.get("api_key"):
                return

        self._chat_history.append({"role": "user", "content": text})
        self.followup_edit.clear()

        sep = "\n\n—— 追问 ——\n你: " + text + "\n\nAI: "
        self.result_view.appendPlainText(sep)
        self._analysis_stream_pos = len(self.result_view.toPlainText())
        self.result_tabs.setCurrentWidget(self.result_view)

        self._set_analysis_buttons_enabled(False)
        self.continue_btn.setEnabled(False)
        self._log(f"—— 继续对话: {text[:60]}…")

        self._analysis_worker = AIAnalysisWorker(
            messages=list(self._chat_history),
            cfg=cfg,
        )
        self._analysis_worker.log.connect(self._log)
        self._analysis_worker.chunk.connect(self._on_analysis_chunk)
        self._analysis_worker.finished_ok.connect(self._on_analysis_done)
        self._analysis_worker.failed.connect(self._on_analysis_failed)
        self._analysis_worker.start()

    def _on_analysis_chunk(self, text: str):
        cursor = self.result_view.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.insertText(text)
        self.result_view.setTextCursor(cursor)
        self.result_view.ensureCursorVisible()

    def _on_analysis_done(self, result: dict, raw_text: str):
        self._last_result = result
        role = self._analysis_role
        self._set_analysis_buttons_enabled(True)
        self.continue_btn.setEnabled(True)
        self._analysis_worker = None
        self._update_next_hint()

        if self._chat_history and self._chat_history[-1].get("role") == "user":
            self._chat_history.append({"role": "assistant", "content": raw_text})

        try:
            formatted = json.dumps(result, ensure_ascii=False, indent=2)
            if len(self._chat_history) <= 2:
                self.result_view.setPlainText(formatted)
            else:
                cursor = self.result_view.textCursor()
                cursor.setPosition(self._analysis_stream_pos)
                cursor.movePosition(cursor.MoveOperation.End, cursor.MoveMode.KeepAnchor)
                cursor.removeSelectedText()
                self.result_view.appendPlainText(formatted)
            self.result_tabs.setCurrentWidget(self.result_view)
        except Exception:
            pass

        if self._auto_generate_after_analysis:
            self._auto_generate_after_analysis = False
            gen_role = self._pending_generate_role or role
            self._pending_generate_role = None
            if result.get("steps"):
                self._log("分析完成，正在生成脚本…")
                self._generate_plugin(silent=False, code_role=gen_role)
            else:
                self._log("分析完成但无有效步骤，已跳过生成")
            return

        if not result.get("steps"):
            self._log(
                f"未生成有效步骤（{'加密' if role == 'encrypt' else '解密'}端密钥未确认）。"
                "请 Hook 抓密钥后重试「分析 Hook+JS」"
            )
        elif result.get("confidence") == "low":
            self._log("置信度较低，建议核对 Hook 日志中的 Key 后再生成脚本")

    def _on_analysis_failed(self, err: str):
        self._set_analysis_buttons_enabled(True)
        self.continue_btn.setEnabled(bool(self._chat_history))
        self._analysis_worker = None
        self._auto_generate_after_analysis = False
        self._pending_generate_role = None
        if len(self._chat_history) > 2 and self._chat_history[-1].get("role") == "user":
            self._chat_history.pop()
        self._log(f"分析失败: {err}")
        QMessageBox.critical(self, "AI 分析失败", err)

    def _load_to_builder(self):
        if not self._last_result or not self._last_result.get("steps"):
            QMessageBox.information(self, "提示", "请先运行 AI 分析并得到有效步骤")
            return
        import gui as gui_mod
        steps = self._last_result["steps"]
        reply = QMessageBox.question(
            self, "确认",
            f"将加载 {len(steps)} 个步骤到可视化构建器（会覆盖当前步骤）？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        main = self.window()
        if not hasattr(main, "visual_builder_tab"):
            return
        vb = main.visual_builder_tab
        vb._clear_all()
        for step in steps:
            vb._add_step(step["type"])
        for i, step in enumerate(steps):
            if i < len(gui_mod.shared_pipeline.steps):
                gui_mod.shared_pipeline.steps[i]["params"].update(step.get("params", {}))
        vb._rebuild_steps()
        vb._preview_code()
        if hasattr(main, "parser_tab"):
            profile = ""
            if hasattr(main, "control"):
                profile = main.control.profile_combo.currentText()
            code = codegen_for_pipeline(
                gui_mod.shared_pipeline.steps, gui_mod.shared_pipeline.body_format, profile
            )
            main.parser_tab.code_preview.setPlainText(code)
        main.tabs.setCurrentWidget(vb)
        self._log("已加载到可视化构建器")

    def _selected_flow(self) -> dict | None:
        item = self.flow_list.currentItem()
        if item:
            idx = item.data(Qt.ItemDataRole.UserRole)
            if idx is not None and 0 <= idx < len(self._flows):
                return self._flows[idx]
        for f in reversed(self._flows):
            body = (f.get("response_body") or "").strip()
            if body and body not in ("(等待响应…)", "(等待响应...)"):
                return f
        return self._flows[-1] if self._flows else None

    def _load_fields_to_parser(self):
        flow = self._selected_flow()
        if not flow:
            QMessageBox.information(self, "提示", "请先采集并点选一条流量")
            return
        resp = (flow.get("response_body") or "").strip()
        if not resp or resp in ("(等待响应…)", "(等待响应...)"):
            QMessageBox.warning(
                self, "提示",
                "当前流量尚无完整响应。\n请等待左侧列表出现 [200] 后再加载，或选中已完成的那条。",
            )
            return
        main = self.window()
        if not hasattr(main, "parser_tab"):
            QMessageBox.warning(self, "提示", "未找到请求解析器 Tab")
            return
        if not main.parser_tab.load_captured_flow(flow, keep_steps=True):
            QMessageBox.warning(self, "提示", "加载失败：流量数据不完整")
            return
        main.tabs.setCurrentWidget(main.parser_tab)
        self._log(f"已加载到请求解析器: {flow.get('method')} {flow.get('url', '')[:60]}")
