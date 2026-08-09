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
    QDialog, QDialogButtonBox, QToolButton, QMenu, QSizePolicy, QComboBox,
)

from core.ai_config import load_ai_config, save_ai_config
from core.ai_lab_config_dialog import AILabConfigDialog
from core.ai_analyzer import AIAnalysisWorker, build_initial_messages, _extract_json, _clean_steps
from core.agent_runner import (
    AgentWorker,
    GENERATE_DECRYPT_GOAL,
    GENERATE_ENCRYPT_GOAL,
    RECOGNIZE_GOAL,
    ANTI_DEBUG_GOAL,
)
from core.agent_tools import SessionData
from core.ai_project_writer import (
    save_ai_project, guess_project_name, guess_match_rules, detect_body_format,
    PROFILES_DIR,
)
from core.browser_lab import BrowserLabWorker
from core.miniprogram_tab import MiniprogramPanel
from core.app_tab import AppReversePanel
from core.project_name import normalize_project_name
from core.icon_loader import set_btn_icon
from core.theme import (
    C, style_button, style_muted_label, setup_code_editor, style_sidebar_aux_button,
)
from core.field_target_dialog import (
    ask_field_targets,
    format_field_targets_hint,
    summarize_field_targets,
)
from codegen import codegen_for_pipeline


class _ReadyChip(QLabel):
    """采集计数（兼容旧引用；界面已改用单行状态）."""

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self._title = title
        self.setObjectName("aiReadyChip")
        self.hide()

    def set_count(self, n: int) -> None:
        self.setText(f"{self._title}  {n}")


class AILabTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._flows: list[dict] = []
        self._flow_keys: dict[str, int] = {}
        self._hooks: list[str] = []
        self._scripts: dict[str, str] = {}
        self._worker: BrowserLabWorker | None = None
        self._analysis_worker: AIAnalysisWorker | None = None
        self._agent_worker: AgentWorker | None = None
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
            "decrypt": "生成解密",
            "encrypt": "生成加密",
            "recognize": "识别加解密",
            "anti_debug": "分析debugger",
        }
        self._agent_mode = "chat"
        # AI 加解密目标字段：decrypt / encrypt / resp_decrypt / unrestricted
        self._field_targets: dict | None = None
        self._build_ui()
        self._load_config()
        self._refresh_api_status()
        self._sync_action_buttons()
        self._refresh_field_targets_label()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 8)
        layout.setSpacing(4)

        # 兼容旧代码引用（不加入布局，零占位）
        self.chip_flow = _ReadyChip("流量", self)
        self.chip_hook = _ReadyChip("Hook", self)
        self.chip_js = _ReadyChip("JS", self)
        self.hook_stats = QLabel("", self)
        self.chip_flow.hide()
        self.chip_hook.hide()
        self.chip_js.hide()
        self.hook_stats.hide()

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)

        # —— 左：采集 ——
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.setSpacing(4)
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
        self.app_panel = AppReversePanel(compact=True)
        self.app_panel.scripts_ready.connect(self.load_app_scripts)
        self.app_panel.request_ai_analyze.connect(self._run_recognize)
        self.app_panel.capture_log.connect(self._log)
        self.source_tabs.addTab(self.app_panel, "App")
        ll.addWidget(self.source_tabs, 1)
        splitter.addWidget(left)

        # —— 右：识别并生成 ——
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(8, 0, 0, 0)
        rl.setSpacing(6)

        self.next_hint = QLabel()
        self.next_hint.setObjectName("aiNextHint")
        self.next_hint.setWordWrap(True)
        style_muted_label(self.next_hint)
        rl.addWidget(self.next_hint)

        sec_row = QHBoxLayout()
        sec_row.setSpacing(6)
        clear_btn = QPushButton("清空")
        clear_btn.setToolTip("清空流量 / Hook / JS（保留分析结果）")
        clear_btn.clicked.connect(self._clear_capture)
        style_sidebar_aux_button(clear_btn)
        set_btn_icon(clear_btn, "clear", size=12)
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
        sec_row.addWidget(more_btn)
        sec_row.addStretch()
        self.api_status = QLabel()
        self.api_status.setObjectName("aiReadyChip")
        self.api_status.setCursor(Qt.CursorShape.PointingHandCursor)
        self.api_status.installEventFilter(self)
        sec_row.addWidget(self.api_status)
        self.ai_cfg_btn = QPushButton("配置")
        self.ai_cfg_btn.setToolTip("API Key、模型（首次使用必填）")
        self.ai_cfg_btn.clicked.connect(self._on_open_ai_config)
        style_sidebar_aux_button(self.ai_cfg_btn)
        set_btn_icon(self.ai_cfg_btn, "setting", size=12)
        sec_row.addWidget(self.ai_cfg_btn)
        self.adv_cfg_btn = QPushButton("高级")
        self.adv_cfg_btn.setToolTip("浏览器经解密端转发等")
        self.adv_cfg_btn.clicked.connect(self._on_open_adv_config)
        style_sidebar_aux_button(self.adv_cfg_btn)
        sec_row.addWidget(self.adv_cfg_btn)
        rl.addLayout(sec_row)

        self.result_tabs = QTabWidget()
        self.result_view = QPlainTextEdit()
        setup_code_editor(self.result_view)
        self.result_view.setReadOnly(True)
        self.result_view.setPlaceholderText("识别 / 生成后的 JSON 结果")
        self.plugin_view = QPlainTextEdit()
        setup_code_editor(self.plugin_view)
        self.plugin_view.setReadOnly(True)
        self.plugin_view.setPlaceholderText("生成的 plugin.py")
        self.flow_detail_view = QPlainTextEdit()
        setup_code_editor(self.flow_detail_view)
        self.flow_detail_view.setReadOnly(True)
        self.flow_detail_view.setPlaceholderText("点左侧流量查看详情")
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(800)
        self.log_view.setPlaceholderText("运行日志")
        self.result_tabs.addTab(self._build_agent_page(), "Agent")
        self.result_tabs.addTab(self.result_view, "结果")
        self.result_tabs.addTab(self.plugin_view, "插件")
        self.result_tabs.addTab(self._build_userscript_page(), "Hook")
        self.result_tabs.addTab(self.flow_detail_view, "详情")
        self.result_tabs.addTab(self.log_view, "日志")
        # 兼容：旧代码可能引用工具栏上的 anti_debug_ai_btn
        self.anti_debug_ai_btn = self.anti_debug_agent_btn
        rl.addWidget(self.result_tabs, 1)
        QTimer.singleShot(0, self._refresh_userscript_preview)

        # 旧版追问框：Agent 页已有输入，默认隐藏减少干扰
        chat_row = QHBoxLayout()
        chat_row.setSpacing(6)
        self.followup_edit = QLineEdit()
        self.followup_edit.setPlaceholderText("追问补充…")
        self.followup_edit.returnPressed.connect(self._continue_chat)
        self.continue_btn = QPushButton("发送")
        self.continue_btn.setEnabled(False)
        self.continue_btn.clicked.connect(self._continue_chat)
        style_sidebar_aux_button(self.continue_btn)
        chat_row.addWidget(self.followup_edit, 1)
        chat_row.addWidget(self.continue_btn)
        self._followup_wrap = QWidget()
        self._followup_wrap.setLayout(chat_row)
        self._followup_wrap.hide()
        rl.addWidget(self._followup_wrap)
        self.result_tabs.currentChanged.connect(self._on_result_tab_changed)

        splitter.addWidget(right)
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 5)
        splitter.setSizes([400, 600])
        layout.addWidget(splitter, 1)
        self._update_flow_empty_hint()
        self._update_next_hint()

    def _on_result_tab_changed(self, index: int) -> None:
        """仅在「结果」页显示旧版追问栏。"""
        wrap = getattr(self, "_followup_wrap", None)
        if wrap is None:
            return
        name = self.result_tabs.tabText(index)
        wrap.setVisible(name == "结果")

    def _build_agent_page(self) -> QWidget:
        """Agent：动作区 + 目标字段条 + 对话."""
        from PyQt6.QtWidgets import QFrame

        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(8)

        # 主操作：识别 / 生成
        act = QHBoxLayout()
        act.setSpacing(6)
        self.recognize_btn = QPushButton(self._btn_labels["recognize"])
        self.recognize_btn.setToolTip("识别加解密（不写文件）")
        self.recognize_btn.clicked.connect(self._run_recognize)
        style_button(self.recognize_btn, "accent")
        set_btn_icon(self.recognize_btn, "code", size=14)
        self.gen_decrypt_btn = QPushButton(self._btn_labels["decrypt"])
        self.gen_decrypt_btn.setToolTip("分析并写出解密端 plugin.py")
        self.gen_decrypt_btn.clicked.connect(lambda: self._run_analyze_and_generate("decrypt"))
        style_button(self.gen_decrypt_btn, "primary")
        set_btn_icon(self.gen_decrypt_btn, "decrypt", size=14)
        self.gen_encrypt_btn = QPushButton(self._btn_labels["encrypt"])
        self.gen_encrypt_btn.setToolTip("分析并写出加密端 plugin.py")
        self.gen_encrypt_btn.clicked.connect(lambda: self._run_analyze_and_generate("encrypt"))
        style_button(self.gen_encrypt_btn, "primary")
        set_btn_icon(self.gen_encrypt_btn, "encrypt", size=14)
        self.anti_debug_agent_btn = QPushButton(self._btn_labels["anti_debug"])
        self.anti_debug_agent_btn.setToolTip("分析无限 debugger，推荐注入勾选")
        self.anti_debug_agent_btn.clicked.connect(self._run_anti_debug_analyze)
        style_button(self.anti_debug_agent_btn, "accent")
        set_btn_icon(self.anti_debug_agent_btn, "search", size=14)
        for btn in (
            self.recognize_btn,
            self.gen_decrypt_btn,
            self.gen_encrypt_btn,
            self.anti_debug_agent_btn,
        ):
            btn.setFixedHeight(32)
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            act.addWidget(btn, 1)
        layout.addLayout(act)

        # 目标字段面板
        target = QFrame()
        target.setObjectName("aiTargetPanel")
        tl = QHBoxLayout(target)
        tl.setContentsMargins(10, 8, 10, 8)
        tl.setSpacing(8)
        title = QLabel("目标字段")
        title.setObjectName("aiTargetPanelTitle")
        tl.addWidget(title)
        self.field_targets_label = QLabel()
        self.field_targets_label.setObjectName("aiTargetStatus")
        self.field_targets_label.setWordWrap(True)
        tl.addWidget(self.field_targets_label, 1)
        self.field_targets_btn = QPushButton("选择字段")
        self.field_targets_btn.setToolTip(
            "选请求 → 请求/响应 → 点字段，缩小 AI 猜测范围"
        )
        self.field_targets_btn.setFixedHeight(28)
        style_button(self.field_targets_btn, "primary")
        set_btn_icon(self.field_targets_btn, "search", size=12)
        self.field_targets_btn.clicked.connect(self._edit_field_targets)
        tl.addWidget(self.field_targets_btn)
        layout.addWidget(target)

        self.agent_view = QPlainTextEdit()
        setup_code_editor(self.agent_view)
        self.agent_view.setReadOnly(True)
        self.agent_view.setPlaceholderText("Agent 过程与结论会显示在这里")
        layout.addWidget(self.agent_view, 1)

        row = QHBoxLayout()
        row.setSpacing(6)
        self.agent_mode_combo = QComboBox()
        self.agent_mode_combo.addItem("加解密", "chat")
        self.agent_mode_combo.addItem("反调试", "anti_debug")
        self.agent_mode_combo.setToolTip("对话模式：加解密 / 反调试")
        self.agent_mode_combo.setFixedWidth(88)
        row.addWidget(self.agent_mode_combo)
        self.agent_edit = QLineEdit()
        self.agent_edit.setPlaceholderText("输入任务，回车发送…")
        self.agent_edit.setMinimumHeight(30)
        self.agent_edit.returnPressed.connect(self._run_agent)
        self.agent_send_btn = QPushButton("发送")
        self.agent_send_btn.setFixedHeight(30)
        self.agent_send_btn.clicked.connect(self._run_agent)
        style_button(self.agent_send_btn, "primary")
        self.agent_stop_btn = QPushButton("停止")
        self.agent_stop_btn.setFixedHeight(30)
        self.agent_stop_btn.setEnabled(False)
        self.agent_stop_btn.clicked.connect(self._stop_agent)
        style_sidebar_aux_button(self.agent_stop_btn)
        row.addWidget(self.agent_edit, 1)
        row.addWidget(self.agent_send_btn)
        row.addWidget(self.agent_stop_btn)
        layout.addLayout(row)
        return page

    def _build_userscript_page(self) -> QWidget:
        """Hook 脚本：勾选启用 + 代码预览。"""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(6)

        bar = QHBoxLayout()
        bar.setSpacing(6)
        self.userscript_enable_check = QCheckBox("启用")
        self.userscript_enable_check.setChecked(True)
        self.userscript_enable_check.setToolTip("启动浏览器时注入下方 Hook 脚本")
        self.userscript_enable_check.toggled.connect(self._on_userscript_enable_toggled)
        bar.addWidget(self.userscript_enable_check)

        gen_btn = QPushButton("生成")
        gen_btn.setToolTip("按「注入」菜单当前勾选生成 Hook")
        style_button(gen_btn, "primary")
        gen_btn.clicked.connect(self._export_hooks_to_tampermonkey)
        bar.addWidget(gen_btn)

        save_btn = QPushButton("保存")
        save_btn.setToolTip("保存编辑内容")
        style_sidebar_aux_button(save_btn)
        save_btn.clicked.connect(self._save_userscript_edits)
        bar.addWidget(save_btn)
        bar.addStretch()
        layout.addLayout(bar)

        # 兼容内部逻辑：隐藏列表，不占版面
        self.userscript_list = QListWidget()
        self.userscript_list.hide()
        self.userscript_list.itemChanged.connect(self._on_userscript_list_changed)
        layout.addWidget(self.userscript_list)

        self.userscript_path_label = QLabel("")
        self.userscript_path_label.hide()

        self.userscript_view = QPlainTextEdit()
        setup_code_editor(self.userscript_view)
        self.userscript_view.setPlaceholderText("点「生成」后在此查看 / 编辑 Hook 脚本")
        layout.addWidget(self.userscript_view, 1)
        return page

    def _focus_userscript_tab(self) -> None:
        for i in range(self.result_tabs.count()):
            if self.result_tabs.tabText(i) in ("Hook", "Hook脚本"):
                self.result_tabs.setCurrentIndex(i)
                break

    def _is_generated_hook_enabled(self) -> bool:
        """Hook脚本页 / 注入菜单：是否启用已生成脚本。"""
        if hasattr(self, "userscript_enable_check"):
            return self.userscript_enable_check.isChecked()
        if hasattr(self, "userscript_list") and self.userscript_list.count():
            for i in range(self.userscript_list.count()):
                it = self.userscript_list.item(i)
                if it and it.checkState() == Qt.CheckState.Checked:
                    return True
            return False
        return bool(getattr(self, "_act_cb_hook", None) and self._act_cb_hook.isChecked())

    def _on_inject_cb_hook_toggled(self, checked: bool) -> None:
        """注入菜单勾选 ↔ Hook脚本页勾选同步。"""
        if hasattr(self, "userscript_enable_check"):
            self.userscript_enable_check.blockSignals(True)
            self.userscript_enable_check.setChecked(checked)
            self.userscript_enable_check.blockSignals(False)
        if hasattr(self, "userscript_list"):
            self.userscript_list.blockSignals(True)
            for i in range(self.userscript_list.count()):
                item = self.userscript_list.item(i)
                if item:
                    item.setCheckState(
                        Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
                    )
            self.userscript_list.blockSignals(False)
        self._save_config()

    def _on_userscript_enable_toggled(self, checked: bool) -> None:
        if hasattr(self, "_act_cb_hook"):
            self._act_cb_hook.blockSignals(True)
            self._act_cb_hook.setChecked(checked)
            self._act_cb_hook.blockSignals(False)
        # 列表项与总开关同步
        if hasattr(self, "userscript_list"):
            self.userscript_list.blockSignals(True)
            for i in range(self.userscript_list.count()):
                item = self.userscript_list.item(i)
                if item:
                    item.setCheckState(
                        Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
                    )
            self.userscript_list.blockSignals(False)
        self._save_config()

    def _on_userscript_list_changed(self, item: QListWidgetItem) -> None:
        if item is None:
            return
        checked = item.checkState() == Qt.CheckState.Checked
        # 任一脚本勾选 → 启用总开关；全不选 → 关闭
        any_checked = False
        for i in range(self.userscript_list.count()):
            it = self.userscript_list.item(i)
            if it and it.checkState() == Qt.CheckState.Checked:
                any_checked = True
                break
        if hasattr(self, "userscript_enable_check"):
            self.userscript_enable_check.blockSignals(True)
            self.userscript_enable_check.setChecked(any_checked)
            self.userscript_enable_check.blockSignals(False)
        if hasattr(self, "_act_cb_hook"):
            self._act_cb_hook.setChecked(any_checked)
        self._save_config()
        if checked:
            self.userscript_list.setCurrentItem(item)
            self._load_selected_userscript_into_editor()

    def _refresh_userscript_preview(self) -> None:
        """从磁盘刷新 Hook 脚本列表与预览。"""
        if not hasattr(self, "userscript_list"):
            return
        from core.browser_ext_manager import USERSCRIPT_PATH, status_summary

        st = status_summary()
        enabled = True
        if hasattr(self, "_act_cb_hook"):
            enabled = self._act_cb_hook.isChecked()
        elif hasattr(self, "userscript_enable_check"):
            enabled = self.userscript_enable_check.isChecked()

        self.userscript_list.blockSignals(True)
        self.userscript_list.clear()
        if st.get("userscript") and os.path.isfile(USERSCRIPT_PATH):
            item = self._make_check_item(
                "cipherbridge_hooks.user.js（密桥 Hook）",
                USERSCRIPT_PATH,
                checked=enabled,
            )
            self.userscript_list.addItem(item)
            self.userscript_list.setCurrentItem(item)
            self.userscript_path_label.setText(USERSCRIPT_PATH)
        else:
            self.userscript_path_label.setText("尚未生成脚本")
            if hasattr(self, "userscript_view"):
                self.userscript_view.clear()
        self.userscript_list.blockSignals(False)

        if hasattr(self, "userscript_enable_check"):
            self.userscript_enable_check.blockSignals(True)
            self.userscript_enable_check.setChecked(enabled and self.userscript_list.count() > 0)
            self.userscript_enable_check.blockSignals(False)

        self._load_selected_userscript_into_editor()

    def _load_selected_userscript_into_editor(self) -> None:
        if not hasattr(self, "userscript_view"):
            return
        item = self.userscript_list.currentItem() if hasattr(self, "userscript_list") else None
        path = item.data(Qt.ItemDataRole.UserRole) if item else None
        if not path or not os.path.isfile(str(path)):
            return
        try:
            with open(str(path), encoding="utf-8") as f:
                text = f.read()
            self.userscript_view.setPlainText(text)
            self.userscript_path_label.setText(str(path))
        except OSError as e:
            self._log(f"读取 Hook 脚本失败: {e}")

    def _save_userscript_edits(self) -> None:
        """把编辑器内容写回 userscript + cb_hook inject.js。"""
        if not hasattr(self, "userscript_view"):
            return
        text = self.userscript_view.toPlainText()
        if not text.strip():
            QMessageBox.information(self, "提示", "编辑区为空，请先生成或粘贴脚本")
            return
        try:
            from core.browser_ext_manager import (
                CB_HOOK_DIR,
                USERSCRIPT_PATH,
                ensure_cb_hook_extension,
                ensure_dirs,
                write_cb_hook_options,
            )

            ensure_dirs()
            ensure_cb_hook_extension()
            with open(USERSCRIPT_PATH, "w", encoding="utf-8") as f:
                f.write(text)
            # 扩展侧不要 GM 头
            body = text
            if "// ==/UserScript==" in body:
                body = body.split("// ==/UserScript==", 1)[-1].lstrip("\n")
            inject = os.path.join(CB_HOOK_DIR, "inject.js")
            with open(inject, "w", encoding="utf-8") as f:
                f.write(body)
            # 同步 GUI「注入」勾选到扩展弹窗默认值
            try:
                write_cb_hook_options(self._inject_opts_from_ui())
            except Exception:
                pass
            if hasattr(self, "userscript_enable_check"):
                self.userscript_enable_check.setChecked(True)
            self._refresh_userscript_preview()
            self._log(f"已保存 Hook 脚本: {USERSCRIPT_PATH}")
            self._prompt_reopen_browser("Hook 脚本已保存到磁盘与密桥 Hook 扩展。")
        except Exception as e:
            QMessageBox.warning(self, "保存失败", str(e))

    def _focus_agent_tab(self) -> None:
        for i in range(self.result_tabs.count()):
            if self.result_tabs.tabText(i) == "Agent":
                self.result_tabs.setCurrentIndex(i)
                break

    def _focus_result_tab(self) -> None:
        self.result_tabs.setCurrentWidget(self.result_view)

    def _agent_session(self) -> SessionData:
        """Agent 只读素材：与列表勾选一致（未勾选的流量/JS 不送）。"""
        return SessionData(
            flows_provider=self._agent_flows,
            hooks_provider=lambda: self._hooks,
            scripts_provider=self._agent_scripts,
        )

    def _agent_flows(self) -> list[dict]:
        flows, _, _, _ = self._analysis_payload()
        return flows

    def _agent_scripts(self) -> dict[str, str]:
        _, scripts, _, _ = self._analysis_payload()
        return scripts

    def _set_agent_dialog_mode(self, mode: str) -> None:
        """同步下方「对话模式」下拉（chat / anti_debug）。"""
        combo = getattr(self, "agent_mode_combo", None)
        if combo is None:
            return
        for i in range(combo.count()):
            if combo.itemData(i) == mode:
                combo.setCurrentIndex(i)
                return

    def _run_agent(self):
        goal = self.agent_edit.text().strip()
        if not goal:
            QMessageBox.information(self, "提示", "请输入 Agent 任务")
            return
        self.agent_edit.clear()
        mode = "chat"
        combo = getattr(self, "agent_mode_combo", None)
        if combo is not None:
            mode = str(combo.currentData() or "chat")
        if mode == "anti_debug":
            # 追问也锁在反调试，避免又跑成加解密识别
            low = goal.casefold()
            if "debugger" not in low and "反调试" not in goal and "注入" not in goal:
                goal = (
                    "【反调试模式】只分析无限 debugger / 反调试与 inject_opts，"
                    f"禁止输出加解密 steps。用户说：{goal}"
                )
            self._start_agent_task(goal, mode="anti_debug")
        else:
            # 若已指定字段，一并约束自由对话
            self._start_agent_task(self._goal_with_field_targets(goal), mode="chat")

    def _pause_capture_for_ai(self) -> None:
        """AI 请求前停掉小程序抓包，避免系统代理劫持导致 API 发不出去。"""
        panel = getattr(self, "miniprogram_panel", None)
        if panel is None:
            return
        capture = getattr(panel, "_capture", None)
        was_running = bool(capture and getattr(capture, "running", False))
        if hasattr(panel, "stop_capture_if_running"):
            panel.stop_capture_if_running()
        if was_running:
            self._log("已自动停止抓包并恢复系统代理，以便 AI API 正常出网")

    def _refresh_field_targets_label(self) -> None:
        lab = getattr(self, "field_targets_label", None)
        if lab is None:
            return
        text = summarize_field_targets(self._field_targets)
        lab.setText(text)
        ready = bool(
            self._field_targets
            and not self._field_targets.get("unrestricted")
            and (
                self._field_targets.get("decrypt")
                or self._field_targets.get("encrypt")
                or self._field_targets.get("resp_decrypt")
            )
        )
        lab.setProperty("ready", "true" if ready else "false")
        lab.style().unpolish(lab)
        lab.style().polish(lab)

    def _edit_field_targets(self) -> None:
        """仅编辑目标字段，不启动分析."""
        flows, _, _, _ = self._analysis_payload()
        if not flows:
            QMessageBox.information(
                self, "提示",
                "请先勾选含 Body 的流量，再指定解密/加密字段。",
            )
            return
        result = ask_field_targets(
            self, flows, self._field_targets, default_role="decrypt",
        )
        if result is None:
            return
        self._field_targets = result
        self._refresh_field_targets_label()
        self._log(f"已设置目标字段：{summarize_field_targets(result)}")

    def _prompt_field_targets(self, *, role: str | None = None) -> bool:
        """识别/生成前弹出字段选择；取消则返回 False."""
        flows, _, _, _ = self._analysis_payload()
        if not flows:
            # 无流量时仍允许跑（可能只有 hook/js），但无法选字段
            if self._field_targets is None:
                self._field_targets = {"unrestricted": True, "decrypt": [], "encrypt": [], "resp_decrypt": []}
                self._refresh_field_targets_label()
            return True
        initial = dict(self._field_targets) if self._field_targets else {}
        default_role = "encrypt" if role == "encrypt" else "decrypt"
        result = ask_field_targets(
            self, flows, initial or None, default_role=default_role,
        )
        if result is None:
            return False
        self._field_targets = result
        self._refresh_field_targets_label()
        return True

    def _goal_with_field_targets(self, goal: str) -> str:
        hint = format_field_targets_hint(self._field_targets)
        if not hint:
            return goal
        return f"{goal}\n\n{hint}"

    def _start_agent_task(
        self,
        goal: str,
        *,
        mode: str = "chat",
        auto_generate_role: str | None = None,
    ) -> None:
        if self._agent_worker and self._agent_worker.isRunning():
            self._log("Agent 运行中，请先停止或等待完成")
            return
        if self._analysis_worker and self._analysis_worker.isRunning():
            self._log("旧版分析仍在运行，请稍候…")
            return
        if not goal.strip():
            return
        if mode == "anti_debug":
            if not self._scripts and not self._hooks:
                QMessageBox.warning(
                    self,
                    "提示",
                    "请先启动浏览器采集 JS（或勾选已捕获的脚本）。\n"
                    "有脚本后才能分析无限 debugger。",
                )
                return
        elif mode != "chat" and not self._has_capture_data():
            QMessageBox.warning(
                self, "提示",
                "请先在左侧采集：网页 / 小程序 / App。",
            )
            return
        self._pause_capture_for_ai()
        cfg = self._get_ai_cfg()
        if not cfg:
            return

        self._auto_generate_after_analysis = bool(auto_generate_role)
        self._pending_generate_role = auto_generate_role
        self._analysis_role = auto_generate_role or "decrypt"
        self._agent_mode = mode

        self.agent_view.appendPlainText(f"\n—— 你 ——\n{goal}\n")
        self.agent_view.appendPlainText("—— Agent ——\n")
        self._focus_agent_tab()
        self._set_analysis_buttons_enabled(False)
        self.agent_stop_btn.setEnabled(True)

        self._agent_worker = AgentWorker(
            goal, self._agent_session(), cfg=cfg, mode=mode, parent=self,
        )
        self._agent_worker.log.connect(self._on_agent_log)
        self._agent_worker.finished_ok.connect(self._on_agent_ok)
        self._agent_worker.failed.connect(self._on_agent_fail)
        self._agent_worker.start()
        flows_n = len(self._agent_flows())
        scripts_n = len(self._agent_scripts())
        self._log(
            f"Agent 启动[{mode}]: 勾选流量 {flows_n}/{len(self._flows)} · "
            f"勾选JS {scripts_n}/{len(self._scripts)} · {goal[:60]}"
        )
    def _stop_agent(self):
        if self._agent_worker and self._agent_worker.isRunning():
            self._agent_worker.cancel()
            self._log("正在停止 Agent…")
            self.agent_view.appendPlainText("\n（请求停止…）\n")

    def _on_agent_log(self, msg: str):
        self.agent_view.appendPlainText(msg)
        self.agent_view.moveCursor(QTextCursor.MoveOperation.End)

    def _on_agent_ok(self, text: str):
        self.agent_view.appendPlainText(f"\n✅ {text}\n")
        self.agent_view.moveCursor(QTextCursor.MoveOperation.End)
        self._reset_agent_buttons()
        self._set_analysis_buttons_enabled(True)
        self._agent_worker = None
        self._log("Agent 完成")
        agent_mode = getattr(self, "_agent_mode", "chat")

        if agent_mode == "anti_debug":
            self._handle_anti_debug_agent_result(text)
            # 保持反调试对话模式，便于继续追问（勿自动切回加解密）
            self._set_agent_dialog_mode("anti_debug")
            return

        result = None
        try:
            parsed = _extract_json(text)
            result = _clean_steps(parsed, self._pending_generate_role or self._analysis_role or "decrypt")
        except Exception:
            result = None

        if result and (result.get("steps") or result.get("summary")):
            self._last_result = result
            try:
                formatted = json.dumps(result, ensure_ascii=False, indent=2)
                self.result_view.setPlainText(formatted)
            except Exception:
                self.result_view.setPlainText(text)
            if self._auto_generate_after_analysis:
                self._focus_result_tab()
            self._update_next_hint()

        if self._auto_generate_after_analysis:
            self._auto_generate_after_analysis = False
            gen_role = self._pending_generate_role or "decrypt"
            self._pending_generate_role = None
            if result and result.get("steps"):
                self._log("Agent 已产出步骤，正在生成脚本…")
                self._generate_plugin(silent=False, code_role=gen_role)
            else:
                self._log("Agent 完成但未解析到有效 steps，已跳过生成（可查看 Agent 原文）")
                dropped = (result or {}).get("_dropped") or []
                detail = ""
                if dropped:
                    detail = "\n\n被过滤的步骤:\n- " + "\n- ".join(dropped[:8])
                elif result and result.get("summary"):
                    detail = f"\n\n分析摘要: {result.get('summary')}"
                else:
                    preview = (text or "").strip().replace("\n", " ")
                    if len(preview) > 240:
                        preview = preview[:240] + "…"
                    if preview:
                        detail = f"\n\nAgent 原文摘要: {preview}"
                box = QMessageBox(self)
                box.setIcon(QMessageBox.Icon.Warning)
                box.setWindowTitle("未得到步骤")
                box.setText(
                    "Agent 已结束，但没有可用的 steps 可写入项目。"
                    + detail
                )
                box.setInformativeText(
                    "可点「再试一次」重新生成；或到 Agent 页查看原文后追问。"
                    "若原文有结论但无 JSON，再试一次会强制补一轮 steps。"
                )
                retry_btn = box.addButton("再试一次", QMessageBox.ButtonRole.AcceptRole)
                box.addButton("知道了", QMessageBox.ButtonRole.RejectRole)
                box.exec()
                if box.clickedButton() == retry_btn:
                    self._run_analyze_and_generate(gen_role)
        elif result and result.get("steps"):
            self._log(f"识别到 {len(result['steps'])} 个步骤，可再点「生成解密/加密」落地")
            dropped = result.get("_dropped") or []
            if dropped:
                self._log(f"另有 {len(dropped)} 个步骤因类型/密钥无效被过滤")
        elif result and result.get("_dropped"):
            self._log(
                "识别到候选步骤但均被过滤（多为 key=unknown），可在 Agent 追问补全密钥"
            )

    def _on_agent_fail(self, err: str):
        self.agent_view.appendPlainText(f"\n❌ {err}\n")
        self.agent_view.moveCursor(QTextCursor.MoveOperation.End)
        self._reset_agent_buttons()
        self._set_analysis_buttons_enabled(True)
        self._agent_worker = None
        self._auto_generate_after_analysis = False
        self._pending_generate_role = None
        self._log(f"Agent 失败: {err}")
        if err != "已取消":
            QMessageBox.warning(self, "Agent 失败", err)

    def _reset_agent_buttons(self):
        self.agent_send_btn.setEnabled(True)
        self.agent_stop_btn.setEnabled(False)

    def _build_browser_source(self) -> QWidget:
        """网页采集：URL + 启动 + 流量/Hook."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 2, 0, 0)
        layout.setSpacing(6)

        bar = QHBoxLayout()
        bar.setSpacing(6)
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("https://example.com  （回车启动）")
        self.url_edit.setMinimumHeight(28)
        self.url_edit.returnPressed.connect(self._start_browser)
        bar.addWidget(self.url_edit, 1)

        # 注入：默认只勾「密钥 Hook」；反调试细节由内置默认 / AI 推荐写入，不再单独展示
        inject_btn = QToolButton()
        inject_btn.setText("注入")
        inject_btn.setToolTip("启动时注入的 Hook / 反调试 / 扩展")
        inject_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        inject_menu = QMenu(self)

        self._inject_detail_opts = {
            "functionHook": True,
            "evalHook": True,
            "timerHook": True,
            "timerNuke": False,
            "consoleClear": True,
            "sizeSpoof": True,
            "rewriteResponse": False,
        }

        self._act_hook = inject_menu.addAction("密钥 Hook")
        self._act_hook.setCheckable(True)
        self._act_hook.setChecked(True)
        self._act_anti = inject_menu.addAction("反调试")
        self._act_anti.setCheckable(True)
        self._act_anti.setChecked(False)
        self._act_cdp = inject_menu.addAction("CDP 定位 debugger")
        self._act_cdp.setCheckable(True)
        self._act_cdp.setChecked(False)
        self._act_cdp.setToolTip(
            "开启后：站点 debugger 暂停时记录脚本 URL/行号到日志与 Hook，并立即继续"
        )

        self._act_rewrite = inject_menu.addAction("响应改写 debugger→return")
        self._act_rewrite.setCheckable(True)
        self._act_rewrite.setChecked(False)
        self._act_rewrite.setToolTip(
            "在 JS/HTML 落地前把字面量 debugger 改成 return，"
            "打断「debugger + 递归」；比只 Hook Function 更管用"
        )

        ext_sub = inject_menu.addMenu("浏览器扩展")
        self._act_vm = ext_sub.addAction("油猴（暴力猴）")
        self._act_vm.setCheckable(True)
        self._act_vm.setChecked(True)
        self._act_vm.setToolTip("Violentmonkey，首次经代理下载")
        self._act_reres = ext_sub.addAction("ReRes（请求映射）")
        self._act_reres.setCheckable(True)
        self._act_reres.setChecked(True)
        self._act_reres.setToolTip("密桥内置 MV3 版 ReRes（原版 MV2 新 Chromium 装不上）")
        self._act_cb_hook = ext_sub.addAction("密桥 Hook 扩展")
        self._act_cb_hook.setCheckable(True)
        self._act_cb_hook.setChecked(True)
        self._act_cb_hook.toggled.connect(self._on_inject_cb_hook_toggled)
        ext_sub.addSeparator()
        ext_sub.addAction("重新下载油猴…", self._redownload_browser_ext)

        inject_menu.addSeparator()
        inject_menu.addAction("生成 Hook 脚本…", self._export_hooks_to_tampermonkey)

        inject_btn.setMenu(inject_menu)
        style_sidebar_aux_button(inject_btn)
        bar.addWidget(inject_btn)

        # 兼容旧引用
        self.hook_check = self._act_hook
        self.anti_debug_check = self._act_anti

        self.start_btn = QPushButton("启动")
        self.stop_btn = QPushButton("停止")
        self.stop_btn.setEnabled(False)
        self.start_btn.clicked.connect(self._start_browser)
        self.stop_btn.clicked.connect(self._stop_browser)
        style_button(self.start_btn, "primary")
        style_sidebar_aux_button(self.stop_btn)
        set_btn_icon(self.start_btn, "play", size=14)
        set_btn_icon(self.stop_btn, "stop", size=12)
        self.start_btn.setFixedHeight(28)
        self.stop_btn.setFixedHeight(28)
        self.stop_btn.setFixedWidth(56)
        bar.addWidget(self.start_btn)
        bar.addWidget(self.stop_btn)
        layout.addLayout(bar)

        capture_tabs = QTabWidget()
        flow_page = QWidget()
        fl = QVBoxLayout(flow_page)
        fl.setContentsMargins(0, 2, 0, 0)
        fl.setSpacing(2)
        self.flow_empty_hint = QLabel()
        self.flow_empty_hint.setObjectName("homeEmptyHint")
        self.flow_empty_hint.setWordWrap(True)
        fl.addWidget(self.flow_empty_hint)
        flow_bar = QHBoxLayout()
        flow_bar.setSpacing(4)
        self.flow_sort_combo = QComboBox()
        self.flow_sort_combo.setToolTip("流量列表排序")
        self.flow_sort_combo.addItem("顺序↑", "seq_asc")
        self.flow_sort_combo.addItem("顺序↓", "seq_desc")
        self.flow_sort_combo.addItem("URL", "url")
        self.flow_sort_combo.addItem("方法", "method")
        self.flow_sort_combo.setFixedWidth(72)
        self.flow_sort_combo.currentIndexChanged.connect(self._rebuild_flow_list_view)
        flow_bar.addWidget(self.flow_sort_combo)
        flow_hint = QLabel("勾选送 AI · #序号=捕获顺序")
        style_muted_label(flow_hint)
        flow_bar.addWidget(flow_hint, 1)
        for text, slot in (
            ("全选", lambda: self._set_list_checked(self.flow_list, True)),
            ("全不选", lambda: self._set_list_checked(self.flow_list, False)),
        ):
            b = QPushButton(text)
            style_sidebar_aux_button(b)
            b.clicked.connect(slot)
            flow_bar.addWidget(b)
        fl.addLayout(flow_bar)
        self.flow_list = QListWidget()
        self.flow_list.setToolTip("勾选要送入 AI 的流量；未勾选任何项时自动挑选。#N 为捕获顺序。")
        self.flow_list.itemClicked.connect(self._on_flow_selected)
        fl.addWidget(self.flow_list, 1)
        capture_tabs.addTab(flow_page, "流量")

        hook_page = QWidget()
        hl = QVBoxLayout(hook_page)
        hl.setContentsMargins(0, 2, 0, 0)
        self.hook_view = QPlainTextEdit()
        self.hook_view.setReadOnly(True)
        self.hook_view.setMaximumBlockCount(3000)
        self.hook_view.setPlaceholderText("启动后操作页面，密钥 / 算法会出现在这里")
        hl.addWidget(self.hook_view)
        capture_tabs.addTab(hook_page, "Hook")

        js_page = QWidget()
        jl = QVBoxLayout(js_page)
        jl.setContentsMargins(0, 2, 0, 0)
        jl.setSpacing(2)
        js_bar = QHBoxLayout()
        js_bar.setSpacing(4)
        js_hint = QLabel("勾选要分析的 JS")
        style_muted_label(js_hint)
        js_bar.addWidget(js_hint, 1)
        for text, slot in (
            ("全选", lambda: self._set_list_checked(self.js_list, True)),
            ("全不选", lambda: self._set_list_checked(self.js_list, False)),
        ):
            b = QPushButton(text)
            style_sidebar_aux_button(b)
            b.clicked.connect(slot)
            js_bar.addWidget(b)
        jl.addLayout(js_bar)
        self.js_list = QListWidget()
        self.js_list.setToolTip("网页 / 小程序反编译代码，勾选后优先送入")
        self.js_list.itemClicked.connect(self._on_js_selected)
        jl.addWidget(self.js_list, 1)
        capture_tabs.addTab(js_page, "JS")
        layout.addWidget(capture_tabs, 1)
        return page

    @staticmethod
    def _make_check_item(text: str, data, *, checked: bool = True) -> QListWidgetItem:
        item = QListWidgetItem(text)
        item.setFlags(
            item.flags()
            | Qt.ItemFlag.ItemIsUserCheckable
            | Qt.ItemFlag.ItemIsEnabled
            | Qt.ItemFlag.ItemIsSelectable
        )
        item.setCheckState(
            Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        )
        item.setData(Qt.ItemDataRole.UserRole, data)
        return item

    @staticmethod
    def _set_list_checked(list_w: QListWidget, checked: bool) -> None:
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        for i in range(list_w.count()):
            item = list_w.item(i)
            if item is not None:
                item.setCheckState(state)

    def _checked_flow_indices(self) -> list[int]:
        out: list[int] = []
        for i in range(self.flow_list.count()):
            item = self.flow_list.item(i)
            if item and item.checkState() == Qt.CheckState.Checked:
                idx = item.data(Qt.ItemDataRole.UserRole)
                if isinstance(idx, int):
                    out.append(idx)
        return out

    def _checked_script_urls(self) -> list[str]:
        out: list[str] = []
        for i in range(self.js_list.count()):
            item = self.js_list.item(i)
            if item and item.checkState() == Qt.CheckState.Checked:
                url = item.data(Qt.ItemDataRole.UserRole)
                if url:
                    out.append(str(url))
        return out

    def _analysis_payload(self) -> tuple[list[dict], dict[str, str], bool, bool]:
        """返回 (flows, scripts, user_selected_flows, user_selected_scripts).

        - 列表为空：无素材
        - 有条目且勾选了若干：只送勾选，user_selected=True
        - 有条目但全不勾：送空列表且 user_selected=True（表示刻意不送这类）
        """
        has_flow_items = self.flow_list.count() > 0
        checked_idx = self._checked_flow_indices()
        if has_flow_items:
            flows = [self._flows[i] for i in checked_idx if 0 <= i < len(self._flows)]
            user_flows = True
        else:
            flows = list(self._flows)
            user_flows = False

        has_js_items = self.js_list.count() > 0
        checked_urls = self._checked_script_urls()
        if has_js_items:
            scripts = {
                u: self._scripts[u] for u in checked_urls if u in self._scripts
            }
            user_scripts = True
        else:
            scripts = dict(self._scripts)
            user_scripts = False
        return flows, scripts, user_flows, user_scripts

    def _refresh_js_list(self) -> None:
        if not hasattr(self, "js_list"):
            return
        prev_checked = set(self._checked_script_urls())
        had_items = self.js_list.count() > 0
        self.js_list.clear()
        for url in self._scripts:
            short = url if len(url) <= 90 else ("…" + url[-87:])
            # 新出现的默认勾选；已有列表时保留勾选状态
            checked = (url in prev_checked) if had_items else True
            if not had_items and url.startswith("miniprogram://"):
                checked = True
            self.js_list.addItem(self._make_check_item(short, url, checked=checked))

    def _on_js_selected(self, item: QListWidgetItem) -> None:
        url = item.data(Qt.ItemDataRole.UserRole) if item else None
        if not url or url not in self._scripts:
            return
        content = self._scripts[url]
        preview = content if len(content) <= 8000 else content[:8000] + "\n…(截断)"
        self.flow_detail_view.setPlainText(f"// {url}\n\n{preview}")
        self.result_tabs.setCurrentWidget(self.flow_detail_view)

    def _pick_steps_dialog(self, steps: list[dict], *, title: str = "选择要写入的步骤") -> list[dict] | None:
        """勾选分析结果中的步骤，取消返回 None."""
        if not steps:
            return []
        dlg = QDialog(self)
        dlg.setWindowTitle(title)
        dlg.setMinimumWidth(480)
        dlg.setMinimumHeight(360)
        layout = QVBoxLayout(dlg)
        hint = QLabel("取消勾选不需要的步骤，避免一键覆盖整份项目。默认全选。")
        hint.setWordWrap(True)
        style_muted_label(hint)
        layout.addWidget(hint)
        bar = QHBoxLayout()
        list_w = QListWidget()
        for i, step in enumerate(steps):
            stype = step.get("type", "?")
            params = step.get("params") or {}
            field = params.get("field") or params.get("target") or params.get("source") or ""
            algo = params.get("algo") or params.get("encode_type") or ""
            detail = " · ".join(x for x in (str(field), str(algo)) if x)
            label = f"{i + 1}. {stype}" + (f"  ({detail})" if detail else "")
            list_w.addItem(self._make_check_item(label, i, checked=True))
        for text, checked in (("全选", True), ("全不选", False)):
            b = QPushButton(text)
            style_sidebar_aux_button(b)
            b.clicked.connect(lambda _=False, c=checked: self._set_list_checked(list_w, c))
            bar.addWidget(b)
        bar.addStretch()
        layout.addLayout(bar)
        layout.addWidget(list_w, 1)
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        layout.addWidget(btns)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return None
        picked: list[dict] = []
        for i in range(list_w.count()):
            item = list_w.item(i)
            if item and item.checkState() == Qt.CheckState.Checked:
                idx = item.data(Qt.ItemDataRole.UserRole)
                if isinstance(idx, int) and 0 <= idx < len(steps):
                    picked.append(dict(steps[idx]))
        if not picked:
            QMessageBox.information(self, "提示", "请至少勾选一个步骤")
            return None
        return picked

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
        updates = dlg.collect(
            hook_enabled=self._act_hook.isChecked(),
            anti_debug=self._act_anti.isChecked(),
            cdp_skip_pauses=self._act_cdp.isChecked(),
            inject_opts=self._inject_opts_from_ui(),
        )
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

    def _inject_opts_from_ui(self) -> dict:
        base = {
            "functionHook": True,
            "evalHook": True,
            "timerHook": True,
            "timerNuke": False,
            "consoleClear": True,
            "sizeSpoof": True,
            "rewriteResponse": False,
        }
        stored = getattr(self, "_inject_detail_opts", None)
        if isinstance(stored, dict):
            base.update({k: bool(v) for k, v in stored.items() if k in base})
        base["rewriteResponse"] = bool(
            getattr(self, "_act_rewrite", None) and self._act_rewrite.isChecked()
        )
        return base

    def _apply_inject_opts_to_ui(self, opts: dict) -> None:
        if not isinstance(opts, dict):
            opts = {}
        detail_keys = (
            "functionHook",
            "evalHook",
            "timerHook",
            "timerNuke",
            "consoleClear",
            "sizeSpoof",
        )
        defaults = {
            "functionHook": True,
            "evalHook": True,
            "timerHook": True,
            "timerNuke": False,
            "consoleClear": True,
            "sizeSpoof": True,
        }
        # 旧配置可能把细节全写成 false；无有效开关时回退默认，避免开反调试无效
        if opts and not any(bool(opts.get(k)) for k in detail_keys):
            cur = dict(defaults)
        else:
            cur = dict(defaults)
            for key in detail_keys:
                if key in opts:
                    cur[key] = bool(opts[key])
        self._inject_detail_opts = cur
        if hasattr(self, "_act_rewrite") and "rewriteResponse" in opts:
            self._act_rewrite.setChecked(bool(opts.get("rewriteResponse")))

    def _load_config(self):
        cfg = load_ai_config()
        browser = cfg.get("browser", {})
        if hasattr(self, "_act_hook"):
            self._act_hook.setChecked(bool(browser.get("hook_enabled", True)))
            self._act_anti.setChecked(bool(browser.get("anti_debug", False)))
            self._act_cdp.setChecked(bool(browser.get("cdp_skip_pauses", False)))
            self._apply_inject_opts_to_ui(browser.get("inject_opts") or {})
        if hasattr(self, "_act_vm"):
            self._act_vm.setChecked(bool(browser.get("load_violentmonkey", True)))
            self._act_reres.setChecked(bool(browser.get("load_reres", True)))
            self._act_cb_hook.setChecked(bool(browser.get("load_cb_hook", True)))
        if hasattr(self, "userscript_enable_check"):
            self.userscript_enable_check.blockSignals(True)
            self.userscript_enable_check.setChecked(bool(browser.get("load_cb_hook", True)))
            self.userscript_enable_check.blockSignals(False)
            self._refresh_userscript_preview()
        last_url = (browser.get("last_url") or "").strip()
        if last_url and not self.url_edit.text().strip():
            self.url_edit.setText(last_url)

    def _browser_cfg(self) -> dict:
        return load_ai_config().get("browser", {})

    def _save_config(self):
        """同步注入勾选 / last_url 到配置文件."""
        cfg = load_ai_config()
        browser = cfg.get("browser", {})
        if not isinstance(browser, dict):
            browser = {}
        if hasattr(self, "_act_hook"):
            browser["hook_enabled"] = self._act_hook.isChecked()
            browser["anti_debug"] = self._act_anti.isChecked()
            browser["cdp_skip_pauses"] = self._act_cdp.isChecked()
            browser["inject_opts"] = self._inject_opts_from_ui()
        if hasattr(self, "_act_vm"):
            browser["load_violentmonkey"] = self._act_vm.isChecked()
            browser["load_reres"] = self._act_reres.isChecked()
            # Hook脚本页勾选优先
            if hasattr(self, "userscript_enable_check"):
                browser["load_cb_hook"] = self.userscript_enable_check.isChecked()
                if hasattr(self, "_act_cb_hook"):
                    self._act_cb_hook.setChecked(browser["load_cb_hook"])
            else:
                browser["load_cb_hook"] = self._act_cb_hook.isChecked()
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
            self.api_status.setText(model)
            fg = C.get("ok", C.get("primary", "#7a9a78"))
        else:
            self.api_status.setText("未配置 API")
            fg = C.get("warn", "#b89a5a")
        self.api_status.setStyleSheet(
            f"QLabel#aiReadyChip {{ background:transparent; color:{fg};"
            f" border:none; padding:0 4px; font-size:11px; }}"
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
        for btn in (self.recognize_btn, self.gen_decrypt_btn, self.gen_encrypt_btn):
            btn.setEnabled(ready)
        self._act_hook_analyze.setEnabled(ready)
        tip = (
            "已有采集数据"
            if ready
            else "请先在左侧「网页 / 小程序 / App」采集或反编译"
        )
        self.recognize_btn.setToolTip(f"识别加解密线索（不写文件）— {tip}")
        self.gen_decrypt_btn.setToolTip(f"写出解密端 plugin.py — {tip}")
        self.gen_encrypt_btn.setToolTip(f"写出加密端 plugin.py — {tip}")

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
        clean = {k: v for k, v in flow.items() if not str(k).startswith("_")}
        # 捕获序号（列表展示 / 字段选择用）
        seq = flow.get("_seq")
        if isinstance(seq, int) and seq > 0:
            clean["_seq"] = seq
        return clean

    def _flow_sort_mode(self) -> str:
        combo = getattr(self, "flow_sort_combo", None)
        if combo is None:
            return "seq_asc"
        return str(combo.currentData() or "seq_asc")

    def _sorted_flow_indices(self) -> list[int]:
        idxs = list(range(len(self._flows)))
        mode = self._flow_sort_mode()

        def seq_of(i: int) -> int:
            f = self._flows[i]
            s = f.get("_seq")
            return s if isinstance(s, int) and s > 0 else i + 1

        if mode == "seq_desc":
            idxs.sort(key=seq_of, reverse=True)
        elif mode == "url":
            idxs.sort(key=lambda i: str(self._flows[i].get("url") or ""))
        elif mode == "method":
            idxs.sort(
                key=lambda i: (
                    str(self._flows[i].get("method") or ""),
                    str(self._flows[i].get("url") or ""),
                )
            )
        else:
            idxs.sort(key=seq_of)
        return idxs

    def _flow_list_label(self, idx: int, flow: dict, *, list_prefix: str = "") -> str:
        seq = flow.get("_seq") if isinstance(flow.get("_seq"), int) else idx + 1
        status = flow.get("status", "")
        method = flow.get("method", "")
        url = str(flow.get("url") or "")[:72]
        pending = status == 0 and flow.get("response_body") == "(等待响应…)"
        mid = "… " if pending else ""
        if pending:
            return f"{list_prefix}#{seq} {mid}{method} {url}"
        return f"{list_prefix}#{seq} [{status}] {method} {url}"

    def _rebuild_flow_list_view(self) -> None:
        """按当前排序重排流量列表，保留勾选与选中项."""
        if not hasattr(self, "flow_list"):
            return
        checked: set[int] = set()
        current_idx = None
        had_items = self.flow_list.count() > 0
        for i in range(self.flow_list.count()):
            item = self.flow_list.item(i)
            if item is None:
                continue
            idx = item.data(Qt.ItemDataRole.UserRole)
            if not isinstance(idx, int):
                continue
            if item.checkState() == Qt.CheckState.Checked:
                checked.add(idx)
            if item is self.flow_list.currentItem():
                current_idx = idx

        self.flow_list.clear()
        select_row = 0
        for row, idx in enumerate(self._sorted_flow_indices()):
            flow = self._flows[idx]
            prefix = str(flow.get("_list_prefix") or "")
            is_checked = (idx in checked) if had_items else True
            item = self._make_check_item(
                self._flow_list_label(idx, flow, list_prefix=prefix),
                idx,
                checked=is_checked,
            )
            self.flow_list.addItem(item)
            if current_idx is not None and idx == current_idx:
                select_row = row
        if self.flow_list.count():
            self.flow_list.setCurrentRow(select_row)
        self._update_flow_empty_hint()

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
        ext_proxy = str(browser.get("ext_proxy") or "127.0.0.1:7897").strip()
        if ext_proxy and not ext_proxy.startswith("http"):
            ext_proxy = f"http://{ext_proxy}"
        self._worker = BrowserLabWorker(
            url=url,
            hook_enabled=self._act_hook.isChecked(),
            anti_debug=self._act_anti.isChecked(),
            cdp_skip_pauses=self._act_cdp.isChecked(),
            inject_opts=self._inject_opts_from_ui(),
            use_mitm_proxy=bool(browser.get("use_mitm_proxy", False)),
            mitm_port=int(browser.get("mitm_port", 8080)),
            load_violentmonkey=bool(
                getattr(self, "_act_vm", None) and self._act_vm.isChecked()
            ),
            load_reres=bool(
                getattr(self, "_act_reres", None) and self._act_reres.isChecked()
            ),
            load_cb_hook=self._is_generated_hook_enabled(),
            ext_proxy=ext_proxy or None,
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
        self.start_btn.setText("启动")
        set_btn_icon(self.start_btn, "play", size=14)
        self._worker = None
        self._clear_session_capture()
        self._update_next_hint()

    def _on_flow(self, flow: dict):
        """浏览器采集 → 写入 _flows 并显示在「浏览器 → 流量」列表."""
        self._ingest_flow(flow, show_in_browser_list=True)

    def _on_miniprogram_flow(self, flow: dict):
        """小程序抓包 → 写入 _flows，并出现在可勾选流量列表."""
        self._ingest_flow(flow, show_in_browser_list=True, list_prefix="[小] ")

    def _ingest_flow(self, flow: dict, *, show_in_browser_list: bool, list_prefix: str = ""):
        clean = self._clean_flow(flow)
        idx = len(self._flows)
        clean["_seq"] = idx + 1
        if list_prefix:
            clean["_list_prefix"] = list_prefix
        self._flows.append(clean)
        key = flow.get("_key") or flow.get("key")
        if key is not None and str(key):
            self._flow_keys[str(key)] = idx
        if show_in_browser_list:
            # 非默认排序时整体重建，保证位置正确
            if self._flow_sort_mode() != "seq_asc":
                self._rebuild_flow_list_view()
            else:
                item = self._make_check_item(
                    self._flow_list_label(idx, clean, list_prefix=list_prefix),
                    idx,
                    checked=True,
                )
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
        prev = self._flows[idx]
        clean = self._clean_flow(flow)
        clean["_seq"] = prev.get("_seq") if isinstance(prev.get("_seq"), int) else idx + 1
        if prev.get("_list_prefix"):
            clean["_list_prefix"] = prev["_list_prefix"]
        self._flows[idx] = clean
        if update_browser_list:
            prefix = str(clean.get("_list_prefix") or "")
            for i in range(self.flow_list.count()):
                item = self.flow_list.item(i)
                if item and item.data(Qt.ItemDataRole.UserRole) == idx:
                    item.setText(self._flow_list_label(idx, clean, list_prefix=prefix))
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
            self._refresh_js_list()
            self._refresh_capture_stats()

    def load_miniprogram_scripts(self, scripts: dict[str, str], meta: dict | None = None) -> None:
        """由「小程序」子页注入反编译 JS，供本页右侧 AI 分析."""
        if not scripts:
            return
        self._scripts.update(scripts)
        self._refresh_js_list()
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
            f"已载入小程序脚本 {len(scripts)} 个。请到右侧 Agent 页「AI识别加解密」或「生成解密」。",
            kind="ready",
        )
        self._sync_action_buttons()

    def load_app_scripts(self, scripts: dict[str, str], meta: dict | None = None) -> None:
        """由「App」子页注入 APK 加解密候选代码，供 Agent 参考."""
        if not scripts:
            return
        # 替换旧的 app:// 素材，避免多次导入堆叠
        self._scripts = {
            k: v for k, v in self._scripts.items() if not str(k).startswith("app://")
        }
        self._scripts.update(scripts)
        self._refresh_js_list()
        self._refresh_capture_stats()
        info = ""
        if meta:
            pkg = meta.get("package") or ""
            out = meta.get("out_dir") or ""
            info = f"（package={pkg} 目录={out}）" if pkg or out else ""
        self._log(f"已载入 App 加解密候选 {len(scripts)} 个{info}")
        self._focus_agent_tab()
        self._set_hint(
            f"已载入 App 代码 {len(scripts)} 个。请在 Agent 页「AI识别加解密」或对话追问算法。",
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
        self._update_next_hint()

    def _set_hint(self, text: str, *, kind: str = "info"):
        """更新右侧引导；单行淡字，不占大块."""
        if not hasattr(self, "next_hint"):
            return
        self.next_hint.setText(text)
        colors = {
            "empty": C.get("text_dim", "#7a7c80"),
            "warn": C.get("warn", "#b89a5a"),
            "info": C.get("text_dim", "#7a7c80"),
            "ready": C.get("text", "#c8c9cb"),
            "ok": C.get("ok", "#7a9a78"),
            "busy": C.get("text_dim", "#7a7c80"),
        }
        fg = colors.get(kind, C.get("text_dim", "#7a7c80"))
        self.next_hint.setStyleSheet(
            f"QLabel#aiNextHint {{ background:transparent; color:{fg};"
            f" border:none; padding:0; font-size:11px; }}"
        )

    def _update_next_hint(self):
        if not hasattr(self, "next_hint"):
            return
        if getattr(self, "_busy", False):
            return
        has_data = self._has_capture_data()
        api_ok = bool(load_ai_config().get("api_key"))
        if self._last_plugin_code:
            self._set_hint("已生成插件 →「插件」页查看", kind="ok")
        elif self._last_result:
            self._set_hint("分析完成 → 可点「生成解密/加密」", kind="ready")
        elif has_data:
            parts = []
            if self._flows:
                parts.append(f"流量{len(self._flows)}")
            if self._hooks:
                parts.append(f"Hook{len(self._hooks)}")
            if self._scripts:
                parts.append(f"JS{len(self._scripts)}")
            extra = "" if api_ok else " · 先配置 API"
            self._set_hint(f"已采集 {'/'.join(parts)} → Agent 识别或生成{extra}", kind="ready" if api_ok else "warn")
        else:
            self._set_hint("左侧采集后，到 Agent 识别或生成", kind="empty")
        self._sync_action_buttons()

    def _update_flow_empty_hint(self):
        if self._flows:
            self.flow_empty_hint.hide()
            return
        self.flow_empty_hint.show()
        if self.stop_btn.isEnabled():
            self.flow_empty_hint.setText("等待流量…在页面里登录或点几下触发请求即可。")
        else:
            self.flow_empty_hint.setText("填 URL → 启动 → 在页面操作产生流量")

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
        seq = f.get("_seq")
        seq_line = f"#请求序号 {seq}\n" if isinstance(seq, int) else ""
        req_body = self._safe_flow_text(f.get("request_body", ""))[:8000]
        resp_body = self._safe_flow_text(f.get("response_body", ""))[:8000]
        return (
            f"{seq_line}{f.get('method')} {f.get('url')}\n\n"
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
        if hasattr(self, "js_list"):
            self.js_list.clear()
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
        anti_btn = getattr(self, "anti_debug_agent_btn", None)
        if not enabled:
            self.recognize_btn.setText("识别中…")
            self.gen_decrypt_btn.setText("分析中…")
            self.gen_encrypt_btn.setText("分析中…")
            self.recognize_btn.setEnabled(False)
            self.gen_decrypt_btn.setEnabled(False)
            self.gen_encrypt_btn.setEnabled(False)
            if anti_btn is not None:
                anti_btn.setEnabled(False)
                anti_btn.setText("分析中…")
            self._act_hook_analyze.setEnabled(False)
            self.agent_send_btn.setEnabled(False)
            self._set_hint("Agent 分析中…", kind="busy")
        else:
            self.recognize_btn.setText(self._btn_labels["recognize"])
            self.gen_decrypt_btn.setText(self._btn_labels["decrypt"])
            self.gen_encrypt_btn.setText(self._btn_labels["encrypt"])
            set_btn_icon(self.recognize_btn, "code", size=14)
            set_btn_icon(self.gen_decrypt_btn, "decrypt", size=14)
            set_btn_icon(self.gen_encrypt_btn, "encrypt", size=14)
            if anti_btn is not None:
                anti_btn.setEnabled(True)
                anti_btn.setText(self._btn_labels["anti_debug"])
                set_btn_icon(anti_btn, "search", size=14)
            self._act_hook_analyze.setEnabled(True)
            self.agent_send_btn.setEnabled(True)
            self._sync_action_buttons()
            self._update_next_hint()

    def _run_analyze_and_generate(self, role: str):
        """一键：Agent 分析并生成 plugin.py."""
        if not self._prompt_field_targets(role=role):
            return
        goal = GENERATE_DECRYPT_GOAL if role == "decrypt" else GENERATE_ENCRYPT_GOAL
        goal = self._goal_with_field_targets(goal)
        self._set_agent_dialog_mode("chat")
        self._start_agent_task(
            goal,
            mode="generate",
            auto_generate_role=role,
        )

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

        steps = self._pick_steps_dialog(
            self._last_result["steps"],
            title="选择要写入项目的步骤",
        )
        if steps is None:
            return False
        body_format = detect_body_format(self._flows)
        summary = self._last_result.get("summary", "")
        confidence = self._last_result.get("confidence", "")

        if confidence == "low" and not silent:
            reply = QMessageBox.question(
                self,
                "置信度较低",
                f"AI 分析置信度为 low：\n{summary}\n\n仍要写入选中的 {len(steps)} 个步骤吗？",
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
                f"项目 '{opts['name']}' 已存在，是否覆盖？\n"
                f"（将写入勾选的 {len(steps)} 个步骤）",
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
        self._log(f"已生成项目: {name} → plugins/{name}/plugin.py（{len(steps)} 步）")
        self._sync_to_main_window(name, steps, code, body_format)
        type_label = "加密" if opts.get("code_role") == "encrypt" else "解密"
        self._set_hint(
            f"已生成{type_label}脚本 plugins/{name}/plugin.py（{len(steps)} 步），"
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

        self._pause_capture_for_ai()
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
        flows, scripts, user_flows, user_scripts = self._analysis_payload()
        if not flows and not self._hooks and not scripts:
            QMessageBox.warning(
                self, "提示",
                "当前没有可送入的素材。\n\n"
                "请先采集流量 / Hook / JS，或勾选左侧列表中的项。",
            )
            return
        sel_bits = []
        if user_flows:
            sel_bits.append(f"勾选流量 {len(flows)}")
        else:
            sel_bits.append(f"流量 {len(flows)}（自动）")
        sel_bits.append(f"Hook {len(self._hooks)}")
        if user_scripts:
            sel_bits.append(f"勾选 JS {len(scripts)}")
        else:
            sel_bits.append(f"JS {len(scripts)}（自动）")
        self._log("送入: " + " · ".join(sel_bits))

        self._analysis_role = role
        self._chat_history = build_initial_messages(
            flows,
            list(self._hooks),
            role,
            scripts=scripts,
            focus_hook=focus_hook,
            focus_miniprogram=focus_miniprogram,
            user_selected_flows=user_flows,
            user_selected_scripts=user_scripts,
        )

        self._analysis_worker = AIAnalysisWorker(
            flows,
            list(self._hooks),
            cfg,
            role=role,
            scripts=scripts,
            focus_hook=focus_hook,
            focus_miniprogram=focus_miniprogram,
            user_selected_flows=user_flows,
            user_selected_scripts=user_scripts,
        )
        self._analysis_worker.log.connect(self._log)
        self._analysis_worker.chunk.connect(self._on_analysis_chunk)
        self._analysis_worker.finished_ok.connect(self._on_analysis_done)
        self._analysis_worker.failed.connect(self._on_analysis_failed)
        self._analysis_worker.start()

    def _run_recognize(self):
        """Agent 页「AI识别加解密」."""
        panel = getattr(self, "miniprogram_panel", None)
        if panel is not None and hasattr(panel, "_emit_scripts") and panel._last_result:
            panel._emit_scripts(silent=True)
        if not self._prompt_field_targets(role="decrypt"):
            return
        self._set_agent_dialog_mode("chat")
        self._start_agent_task(
            self._goal_with_field_targets(RECOGNIZE_GOAL),
            mode="recognize",
        )

    def _run_anti_debug_analyze(self):
        """AI 分析无限 debugger / 反调试，并推荐注入勾选."""
        if not self._scripts and not self._hooks:
            QMessageBox.information(
                self,
                "提示",
                "请先启动浏览器并操作页面，采到 JS 后再点「AI分析debugger」。\n"
                "也可在左侧「JS」列表勾选要分析的脚本。",
            )
            return
        n = len(self._scripts)
        self._set_hint(
            f"正在用 AI 分析 {n} 个 JS 中的无限 debugger…结果见 Agent 页",
            kind="busy",
        )
        self._set_agent_dialog_mode("anti_debug")
        self._start_agent_task(ANTI_DEBUG_GOAL, mode="anti_debug")

    def _handle_anti_debug_agent_result(self, text: str) -> None:
        """解析 anti_debug JSON：套用注入勾选 + 写入 AI 生成的 hook_js。"""
        parsed = None
        try:
            parsed = _extract_json(text)
        except Exception:
            parsed = None
        if not isinstance(parsed, dict):
            self.result_view.setPlainText(text)
            self._log("debugger 分析完成（未解析到 JSON，见 Agent 原文）")
            self._set_hint("debugger 分析完成，请看 Agent 原文", kind="ready")
            return

        try:
            self.result_view.setPlainText(json.dumps(parsed, ensure_ascii=False, indent=2))
        except Exception:
            self.result_view.setPlainText(text)

        summary = str(parsed.get("summary") or "").strip()
        advice = str(parsed.get("advice") or "").strip()
        patterns = parsed.get("patterns") or []
        opts = parsed.get("inject_opts") if isinstance(parsed.get("inject_opts"), dict) else {}
        hook_js = str(parsed.get("hook_js") or "").strip()
        # 字面量/递归类模式：强制建议响应改写
        pat_blob = " ".join(str(p) for p in patterns).lower() + " " + summary.lower()
        if any(
            k in pat_blob
            for k in ("literal", "递归", "sojson", "debugger", "while", "rewrite")
        ):
            opts = dict(opts)
            opts.setdefault("rewriteResponse", True)
            opts.setdefault("cdp_skip_pauses", True)
            opts.setdefault("anti_debug", True)

        self._log(
            "debugger 分析: "
            + (summary[:120] if summary else "完成")
            + (f" | 模式: {', '.join(map(str, patterns[:5]))}" if patterns else "")
            + (" | 含 hook_js" if hook_js else "")
        )
        if advice:
            self._set_hint(advice[:200], kind="ready")
        else:
            self._set_hint(summary[:200] or "debugger 分析完成", kind="ready")

        if not opts and not hook_js:
            return

        lines = []
        if summary:
            lines.append(summary)
        if patterns:
            lines.append("识别到: " + ", ".join(str(p) for p in patterns[:8]))
        if hook_js:
            lines.append(f"AI 已生成站点补丁 hook_js（约 {len(hook_js)} 字符）")
        if advice:
            lines.append(advice)
        lines.append(
            "\n是否应用？将：勾选注入项 + 生成/写入 Hook 脚本"
            + ("（含 AI 补丁）" if hook_js else "")
            + "（需重新启动浏览器）"
        )
        reply = QMessageBox.question(
            self,
            "应用反调试方案？",
            "\n".join(lines),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        if opts:
            self._apply_anti_debug_inject_opts(opts)
        # 有 hook_js 时务必开密桥 Hook 扩展
        if hook_js:
            if hasattr(self, "_act_cb_hook"):
                self._act_cb_hook.setChecked(True)
            if hasattr(self, "userscript_enable_check"):
                self.userscript_enable_check.setChecked(True)
            if hasattr(self, "_act_anti"):
                self._act_anti.setChecked(True)
        self._save_config()
        try:
            from core.browser_ext_manager import export_hooks_to_userscript

            paths = export_hooks_to_userscript(
                include_anti_debug=self._act_anti.isChecked(),
                include_crypto_hook=self._act_hook.isChecked(),
                inject_opts=self._inject_opts_from_ui(),
                extra_js=hook_js,
                mark_pending_install=True,
            )
            self._log(f"已写入 Hook: {paths['userscript']}")
            if hasattr(self, "_refresh_userscript_preview"):
                self._refresh_userscript_preview()
            self._focus_userscript_tab()
        except Exception as e:
            self._log(f"写入 Hook 失败（注入勾选已保存）: {e}")
        self._prompt_reopen_browser(
            "已按 AI 识别结果更新注入项"
            + ("，并写入站点补丁 hook_js" if hook_js else "")
            + "。请到「Hook」页查看生成代码。"
        )

    def _prompt_reopen_browser(self, reason: str = "") -> None:
        """扩展/Hook 变更后统一提示重启浏览器。"""
        running = bool(self._worker and self._worker.isRunning())
        msg = reason.strip() + ("\n\n" if reason.strip() else "")
        if running:
            msg += (
                "请先点「停止」，再点「启动」重新打开浏览器，"
                "扩展与油猴脚本才会生效。"
            )
            self._log("请重新打开浏览器以使扩展/Hook 生效")
        else:
            msg += "请点「启动」打开浏览器；若油猴弹出安装确认，请点「安装」。"
        QMessageBox.information(self, "请重新打开浏览器", msg)

    def _export_hooks_to_tampermonkey(self) -> None:
        """按当前注入勾选生成 userscript，同步到 cb_hook，并提示重启。"""
        try:
            from core.browser_ext_manager import export_hooks_to_userscript

            paths = export_hooks_to_userscript(
                include_anti_debug=self._act_anti.isChecked(),
                include_crypto_hook=self._act_hook.isChecked(),
                inject_opts=self._inject_opts_from_ui(),
                mark_pending_install=True,
            )
            self._save_config()
            self._log(f"已生成油猴脚本: {paths['userscript']}")
            self._log(f"已同步密桥 Hook 扩展: {paths['cb_hook_inject']}")
            if hasattr(self, "userscript_enable_check"):
                self.userscript_enable_check.setChecked(True)
            self._refresh_userscript_preview()
            self._focus_userscript_tab()
            self._prompt_reopen_browser(
                "Hook 已生成。可在「Hook」页勾选启用，然后停止并重新启动浏览器。"
            )
        except Exception as e:
            QMessageBox.warning(self, "生成失败", str(e))
            self._log(f"生成油猴脚本失败: {e}")

    def _redownload_browser_ext(self) -> None:
        """强制经代理重新下载油猴 + ReRes。"""
        browser = self._browser_cfg()
        proxy = str(browser.get("ext_proxy") or "127.0.0.1:7897").strip()
        if proxy and not proxy.startswith("http"):
            proxy = f"http://{proxy}"
        self._log(f"开始重新下载扩展（代理 {proxy or '直连'}）…")

        def _work():
            from core.browser_ext_manager import ensure_vendor_extensions

            return ensure_vendor_extensions(
                want_vm=True,
                want_reres=True,
                proxy=proxy or None,
                force=True,
                log=lambda m: self._log(m),
            )

        try:
            # 下载可能较久，仍在 GUI 线程简单跑；失败则提示
            result = _work()
            errs = result.get("errors") or []
            if errs:
                QMessageBox.warning(
                    self,
                    "下载未完全成功",
                    "部分扩展失败：\n" + "\n".join(errs)
                    + f"\n\n请确认代理 {proxy} 可用后重试。",
                )
            else:
                self._prompt_reopen_browser(
                    "油猴 Violentmonkey 与 ReRes 已下载到 browser_ext/vendor/。"
                )
        except Exception as e:
            QMessageBox.warning(self, "下载失败", f"{e}\n\n可配置 browser.ext_proxy: 127.0.0.1:7897")
            self._log(f"扩展下载失败: {e}")

    def _apply_anti_debug_inject_opts(self, opts: dict) -> None:
        """把 AI 返回的 inject_opts 写到注入菜单."""
        if opts.get("anti_debug") is not None and hasattr(self, "_act_anti"):
            self._act_anti.setChecked(bool(opts.get("anti_debug")))
        if opts.get("cdp_skip_pauses") is not None and hasattr(self, "_act_cdp"):
            self._act_cdp.setChecked(bool(opts.get("cdp_skip_pauses")))
        # 若推荐开反调试，默认确保脚本总开关开着
        if any(
            opts.get(k)
            for k in (
                "functionHook", "evalHook", "timerHook", "timerNuke",
                "consoleClear", "sizeSpoof", "rewriteResponse",
            )
        ):
            if hasattr(self, "_act_anti"):
                self._act_anti.setChecked(True)
        self._apply_inject_opts_to_ui(opts)

    def _run_hook_analysis(self):
        """更多菜单：偏 Hook 的 Agent 识别."""
        if not self._prompt_field_targets(role="decrypt"):
            return
        goal = (
            "请优先用 hook.search / hook.list 查密钥与算法，再结合 script 与 flow，"
            "输出加解密结论；末尾尽量附带 steps JSON。"
        )
        self._start_agent_task(self._goal_with_field_targets(goal), mode="recognize")

    def _run_miniprogram_ai(self):
        """兼容旧信号：走 Agent 识别."""
        panel = getattr(self, "miniprogram_panel", None)
        if panel is not None and hasattr(panel, "_emit_scripts") and panel._last_result:
            panel._emit_scripts(silent=True)
        if not self._prompt_field_targets(role="decrypt"):
            return
        self._start_agent_task(
            self._goal_with_field_targets(RECOGNIZE_GOAL),
            mode="recognize",
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

        self._pause_capture_for_ai()
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
        steps = self._pick_steps_dialog(
            self._last_result["steps"],
            title="选择要加载到构建器的步骤",
        )
        if steps is None:
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
        self._log(f"已加载 {len(steps)} 个步骤到可视化构建器")

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
