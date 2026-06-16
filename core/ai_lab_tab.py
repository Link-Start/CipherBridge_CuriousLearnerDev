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
    QDialog, QDialogButtonBox, QToolButton, QMenu,
)

from core.ai_config import load_ai_config, save_ai_config
from core.ai_lab_config_dialog import AILabConfigDialog
from core.ai_analyzer import AIAnalysisWorker, build_initial_messages
from core.ai_project_writer import (
    save_ai_project, guess_project_name, guess_match_rules, detect_body_format,
    PROFILES_DIR,
)
from core.browser_lab import BrowserLabWorker
from core.project_name import normalize_project_name
from core.theme import style_button, style_muted_label, setup_code_editor, style_sidebar_aux_button
from codegen import codegen_for_pipeline


class AILabTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._flows: list[dict] = []
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
        self._build_ui()
        self._load_config()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        hint = QLabel(
            "启动浏览器采集流量与 Hook →「生成解密/加密」自动分析并写出 plugin.py。"
            "首次使用请点击「AI 配置」填写 API Key。"
        )
        hint.setWordWrap(True)
        style_muted_label(hint)
        layout.addWidget(hint)

        # 常用操作 — 始终可见
        bar = QHBoxLayout()
        bar.setSpacing(6)
        bar.addWidget(QLabel("URL"))
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("https://example.com")
        bar.addWidget(self.url_edit, 1)
        self.hook_check = QCheckBox("Hook")
        self.hook_check.setChecked(True)
        self.hook_check.setToolTip("注入 crypto_hook.js 抓取密钥")
        bar.addWidget(self.hook_check)
        self.ai_cfg_btn = QPushButton("AI 配置")
        self.ai_cfg_btn.setToolTip("API Key、Base URL、模型、HTTP 代理")
        self.ai_cfg_btn.clicked.connect(lambda: self._open_config_dialog("ai"))
        style_sidebar_aux_button(self.ai_cfg_btn)
        bar.addWidget(self.ai_cfg_btn)
        self.adv_cfg_btn = QPushButton("高级")
        self.adv_cfg_btn.setToolTip("浏览器经解密端转发等高级选项")
        self.adv_cfg_btn.clicked.connect(lambda: self._open_config_dialog("advanced"))
        style_sidebar_aux_button(self.adv_cfg_btn)
        bar.addWidget(self.adv_cfg_btn)
        self.start_btn = QPushButton("启动")
        self.stop_btn = QPushButton("关闭")
        self.stop_btn.setEnabled(False)
        self.start_btn.clicked.connect(self._start_browser)
        self.stop_btn.clicked.connect(self._stop_browser)
        style_sidebar_aux_button(self.start_btn)
        style_sidebar_aux_button(self.stop_btn)
        self.start_btn.setFixedWidth(48)
        self.stop_btn.setFixedWidth(48)
        bar.addWidget(self.start_btn)
        bar.addWidget(self.stop_btn)
        layout.addLayout(bar)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.addWidget(QLabel("捕获的流量 (XHR / Fetch / API):"))
        self.flow_empty_hint = QLabel()
        self.flow_empty_hint.setWordWrap(True)
        style_muted_label(self.flow_empty_hint)
        ll.addWidget(self.flow_empty_hint)
        self.flow_list = QListWidget()
        self.flow_list.itemClicked.connect(self._on_flow_selected)
        ll.addWidget(self.flow_list)
        self.hook_stats = QLabel("Hook: 0 条 | JS: 0 个")
        style_muted_label(self.hook_stats)
        ll.addWidget(self.hook_stats)
        ll.addWidget(QLabel("Hook 日志 (CryptoJS/RSA/密钥):"))
        self.hook_view = QPlainTextEdit()
        self.hook_view.setReadOnly(True)
        self.hook_view.setMaximumBlockCount(3000)
        ll.addWidget(self.hook_view)
        splitter.addWidget(left)

        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(4, 0, 0, 0)
        rl.addWidget(QLabel("运行日志:"))
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(500)
        rl.addWidget(self.log_view, 1)

        self.result_tabs = QTabWidget()
        self.result_view = QPlainTextEdit()
        setup_code_editor(self.result_view)
        self.result_view.setReadOnly(True)
        self.plugin_view = QPlainTextEdit()
        setup_code_editor(self.plugin_view)
        self.plugin_view.setReadOnly(True)
        self.plugin_view.setPlaceholderText("点击「生成解密/加密」后，插件代码将显示在此")
        self.flow_detail_view = QPlainTextEdit()
        setup_code_editor(self.flow_detail_view)
        self.flow_detail_view.setReadOnly(True)
        self.flow_detail_view.setPlaceholderText("在左侧点击一条流量，查看请求与响应详情")
        self.result_tabs.addTab(self.result_view, "AI 分析结果")
        self.result_tabs.addTab(self.plugin_view, "代理脚本")
        self.result_tabs.addTab(self.flow_detail_view, "请求/响应")
        rl.addWidget(self.result_tabs, 2)

        chat_row = QHBoxLayout()
        chat_row.setSpacing(6)
        self.followup_edit = QLineEdit()
        self.followup_edit.setPlaceholderText("追问 AI，例如：密钥是 your-16-byte-key!")
        self.followup_edit.returnPressed.connect(self._continue_chat)
        self.continue_btn = QPushButton("发送")
        self.continue_btn.setEnabled(False)
        self.continue_btn.clicked.connect(self._continue_chat)
        style_sidebar_aux_button(self.continue_btn)
        chat_row.addWidget(self.followup_edit, 1)
        chat_row.addWidget(self.continue_btn)
        rl.addLayout(chat_row)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)
        self.analyze_btn = QPushButton("仅AI分析")
        self.analyze_btn.setToolTip("仅运行 AI 分析，不生成 plugin.py")
        self.analyze_btn.clicked.connect(self._run_analysis)
        style_button(self.analyze_btn, "accent")
        btn_row.addWidget(self.analyze_btn)
        self.gen_decrypt_btn = QPushButton("生成解密")
        self.gen_decrypt_btn.setToolTip("AI 分析并生成解密代理（浏览器密文 → Burp 明文）")
        self.gen_decrypt_btn.clicked.connect(lambda: self._run_analyze_and_generate("decrypt"))
        style_button(self.gen_decrypt_btn, "primary")
        self.gen_encrypt_btn = QPushButton("生成加密")
        self.gen_encrypt_btn.setToolTip("AI 分析并生成加密代理（Burp 明文 → 加密签名 → 服务器）")
        self.gen_encrypt_btn.clicked.connect(lambda: self._run_analyze_and_generate("encrypt"))
        style_button(self.gen_encrypt_btn, "primary")
        for btn in (self.analyze_btn, self.gen_decrypt_btn, self.gen_encrypt_btn):
            btn.setMinimumHeight(32)
        btn_row.addWidget(self.gen_decrypt_btn, 1)
        btn_row.addWidget(self.gen_encrypt_btn, 1)

        more_btn = QToolButton()
        more_btn.setText("⋯")
        more_btn.setToolTip("Hook 分析、加载步骤、清空采集等")
        more_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        more_menu = QMenu(self)
        self._act_hook_analyze = more_menu.addAction("分析 Hook+JS", self._run_hook_analysis)
        self._act_hook_analyze.setToolTip("优先 Hook 日志与页面 JS，不生成脚本")
        more_menu.addSeparator()
        more_menu.addAction("加载到构建器", self._load_to_builder)
        more_menu.addAction("加载到解析器", self._load_fields_to_parser)
        more_menu.addSeparator()
        more_menu.addAction("清空采集", self._clear_capture)
        more_btn.setMenu(more_menu)
        more_btn.setFixedWidth(36)
        btn_row.addWidget(more_btn)
        rl.addLayout(btn_row)
        splitter.addWidget(right)
        splitter.setSizes([480, 520])
        layout.addWidget(splitter, 1)
        self._update_flow_empty_hint()

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
        return True

    def _load_config(self):
        cfg = load_ai_config()
        browser = cfg.get("browser", {})
        self.hook_check.setChecked(bool(browser.get("hook_enabled", True)))

    def _browser_cfg(self) -> dict:
        return load_ai_config().get("browser", {})

    def _save_config(self):
        """从当前 Hook 勾选同步 browser.hook_enabled 到配置文件."""
        cfg = load_ai_config()
        browser = cfg.get("browser", {})
        if not isinstance(browser, dict):
            browser = {}
        browser["hook_enabled"] = self.hook_check.isChecked()
        cfg["browser"] = browser
        save_ai_config(cfg)

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
            return
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
        self._update_flow_empty_hint()

    def _stop_browser(self):
        if self._worker and self._worker.isRunning():
            self._worker.stop()

    def _on_browser_stopped(self):
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self._worker = None
        self._clear_session_capture()

    def _on_flow(self, flow: dict):
        clean = self._clean_flow(flow)
        self._flows.append(clean)
        pending = clean.get("status") == 0 and clean.get("response_body") == "(等待响应…)"
        prefix = "… " if pending else ""
        item = QListWidgetItem(f"{prefix}{clean.get('method')} {clean.get('url', '')[:78]}")
        item.setData(Qt.ItemDataRole.UserRole, len(self._flows) - 1)
        self.flow_list.addItem(item)
        self._refresh_capture_stats()
        self._update_flow_empty_hint()

    def _on_flow_updated(self, flow: dict):
        idx = flow.get("_index")
        if idx is None or idx < 0 or idx >= len(self._flows):
            return
        clean = self._clean_flow(flow)
        self._flows[idx] = clean
        item = self.flow_list.item(idx)
        if item:
            item.setText(f"[{clean.get('status')}] {clean.get('method')} {clean.get('url', '')[:75]}")
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

    def _refresh_capture_stats(self):
        self.hook_stats.setText(
            f"Hook: {len(self._hooks)} 条 | JS: {len(self._scripts)} 个 | 流量: {len(self._flows)} 条"
        )

    def _update_flow_empty_hint(self):
        if self._flows:
            self.flow_empty_hint.hide()
            return
        self.flow_empty_hint.show()
        if self.stop_btn.isEnabled():
            self.flow_empty_hint.setText("流量捕获较慢，请耐心等待…")
        else:
            self.flow_empty_hint.setText("启动浏览器后，XHR / Fetch / API 流量将显示在下方列表")

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

    def _clear_session_capture(self):
        """关闭浏览器时清空本次捕获数据（保留 AI 分析结果与已生成脚本）."""
        self._flows.clear()
        self._hooks.clear()
        self._scripts.clear()
        self.flow_list.clear()
        self.hook_view.clear()
        self.log_view.clear()
        self._hook_buf.clear()
        self._log_buf.clear()
        self._ui_flush_timer.stop()
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
        self.analyze_btn.setEnabled(enabled)
        self.gen_decrypt_btn.setEnabled(enabled)
        self.gen_encrypt_btn.setEnabled(enabled)
        self._act_hook_analyze.setEnabled(enabled)

    def _run_analyze_and_generate(self, role: str):
        """一键：按角色 AI 分析并生成 plugin.py."""
        if self._analysis_worker and self._analysis_worker.isRunning():
            self._log("分析进行中，请稍候…")
            return
        if not self._flows and not self._hooks and not self._scripts:
            QMessageBox.warning(self, "提示", "请先启动浏览器并操作页面，采集流量/Hook/JS")
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

        if not silent:
            type_label = "加密" if opts.get("code_role") == "encrypt" else "解密"
            QMessageBox.information(
                self,
                "生成成功",
                f"已生成{type_label}脚本: plugins/{name}/plugin.py\n"
                f"控制面板已切换到项目「{name}」。",
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
        title = "▶ Hook+JS 分析中…\n\n" if focus_hook else "▶ AI 分析中，实时输出如下…\n\n"
        self.result_view.clear()
        self.result_view.setPlainText(title)
        self._analysis_stream_pos = len(self.result_view.toPlainText())
        self._set_analysis_buttons_enabled(False)
        self.continue_btn.setEnabled(False)
        label = "解密" if role == "decrypt" else "加密"
        self._log(f"—— 开始{label}脚本分析 ——" if focus_hook else f"—— 开始 AI 分析 ({label}) ——")

        self._analysis_role = role
        self._chat_history = build_initial_messages(
            list(self._flows),
            list(self._hooks),
            role,
            scripts=dict(self._scripts),
            focus_hook=focus_hook,
        )

        self._analysis_worker = AIAnalysisWorker(
            list(self._flows),
            list(self._hooks),
            cfg,
            role=role,
            scripts=dict(self._scripts),
            focus_hook=focus_hook,
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
            QMessageBox.warning(self, "提示", "请先启动浏览器并操作页面，采集流量/Hook/JS")
            return
        cfg = self._get_ai_cfg()
        if not cfg:
            return
        if not self._hooks:
            self._log("提示: 无 Hook 日志，建议勾选 JS Hook 后重新登录再分析")
        self._start_analysis_worker(cfg, role="decrypt", focus_hook=False)

    def _run_hook_analysis(self):
        if self._analysis_worker and self._analysis_worker.isRunning():
            self._log("分析进行中，请稍候…")
            return
        cfg = self._get_ai_cfg()
        if not cfg:
            return
        self._start_analysis_worker(cfg, role="decrypt", focus_hook=True, require_hooks=False)

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
            QMessageBox.information(self, "提示", "请先启动浏览器并捕获至少一条 API 流量")
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
