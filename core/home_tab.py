"""CryptoProxy 主页 — 概览、状态与快捷入口."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QSizePolicy, QVBoxLayout, QWidget,
)

from core.icon_loader import TOPOLOGY_IMAGE
from core.theme import C, style_button, style_muted_label


class _StatChip(QFrame):
    """状态小卡片."""

    def __init__(self, label: str, parent=None):
        super().__init__(parent)
        self.setObjectName("homeStatCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)
        self._label = QLabel(label)
        style_muted_label(self._label)
        self._value = QLabel("—")
        self._value.setObjectName("homeStatValue")
        layout.addWidget(self._label)
        layout.addWidget(self._value)

    def set_value(self, text: str, *, running: bool | None = None) -> None:
        self._value.setText(text)
        if running is True:
            self._value.setStyleSheet(f"color:{C['primary']}; font-weight:600; background:transparent;")
        elif running is False:
            self._value.setStyleSheet(f"color:{C['text_dim']}; background:transparent;")
        else:
            self._value.setStyleSheet("background:transparent;")


class HomeTab(QWidget):
    """工具主页."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._routes: dict[str, QWidget] = {}
        self._tab_widget = None
        self._build_ui()

    def bind_tabs(self, tab_widget, routes: dict[str, QWidget]) -> None:
        self._tab_widget = tab_widget
        self._routes = routes

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        body = QWidget()
        root = QVBoxLayout(body)
        root.setContentsMargins(36, 32, 36, 36)
        root.setSpacing(22)

        # ---- 状态 ----
        self.empty_hint = QLabel(
            "还没有项目：请先在左侧点击「新建」，或在「请求解析器」解析报文后保存项目。"
        )
        self.empty_hint.setObjectName("homeEmptyHint")
        self.empty_hint.setWordWrap(True)
        self.empty_hint.hide()
        root.addWidget(self.empty_hint)
        root.addWidget(self._section("运行状态"))
        stat_row = QHBoxLayout()
        stat_row.setSpacing(10)
        self.chip_project = _StatChip("当前项目")
        self.chip_decrypt = _StatChip("解密端")
        self.chip_encrypt = _StatChip("加密端")
        self.chip_cert = _StatChip("HTTPS 证书")
        for chip in (self.chip_project, self.chip_decrypt, self.chip_encrypt, self.chip_cert):
            chip.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            stat_row.addWidget(chip)
        root.addLayout(stat_row)

        # ---- 部署拓扑图 ----
        root.addWidget(self._section("部署拓扑"))
        self._topo_label = QLabel()
        self._topo_label.setObjectName("homeTopology")
        self._topo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._topo_pixmap = QPixmap(TOPOLOGY_IMAGE)
        self._update_topology_image()
        root.addWidget(self._topo_label)

        # ---- 工作流 ----
        root.addWidget(self._section("四步上手"))
        flow = QFrame()
        flow.setObjectName("homeWorkflow")
        fl = QGridLayout(flow)
        fl.setContentsMargins(16, 14, 16, 14)
        fl.setHorizontalSpacing(14)
        fl.setVerticalSpacing(10)
        steps = [
            ("1", "解析报文", "在请求解析器粘贴抓包，左键点击密文字段"),
            ("2", "组装步骤", "可视化构建器调整顺序，预览生成代码"),
            ("3", "保存项目", "保存后于左侧控制面板选择项目"),
            ("4", "启动代理", "启动解密端 / 加密端，配置浏览器代理"),
        ]
        for row, (num, st, sd) in enumerate(steps):
            badge = QLabel(num)
            badge.setObjectName("homeStepBadge")
            badge.setFixedSize(24, 24)
            badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            st_lbl = QLabel(st)
            st_lbl.setObjectName("homeCardTitle")
            sd_lbl = QLabel(sd)
            sd_lbl.setWordWrap(True)
            style_muted_label(sd_lbl)
            fl.addWidget(badge, row, 0, Qt.AlignmentFlag.AlignTop)
            st_col = QVBoxLayout()
            st_col.setSpacing(2)
            st_col.addWidget(st_lbl)
            st_col.addWidget(sd_lbl)
            fl.addLayout(st_col, row, 1)

        root.addWidget(flow)

        # ---- 底部按钮 ----
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_parser = QPushButton("开始解析报文")
        btn_parser.clicked.connect(lambda: self._go("parser"))
        style_button(btn_parser, "primary")
        btn_builder = QPushButton("打开构建器")
        btn_builder.clicked.connect(lambda: self._go("builder"))
        style_button(btn_builder, "accent")
        btn_row.addWidget(btn_parser)
        btn_row.addWidget(btn_builder)
        root.addLayout(btn_row)
        root.addStretch()

        scroll.setWidget(body)
        outer.addWidget(scroll)

    @staticmethod
    def _section(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("homeSectionTitle")
        return lbl

    def _go(self, key: str) -> None:
        target = self._routes.get(key)
        if target is None or self._tab_widget is None:
            return
        # 嵌套在「设置」中心内的页面
        nested = {
            "analyzer": ("settings", 1),
            "crypto": ("settings", 2),
            "log": ("settings", 3),
        }
        if key in nested:
            settings = self._routes.get("settings")
            page = nested[key][1]
            win = self.window()
            if win is not None and hasattr(win, "open_settings_hub"):
                win.open_settings_hub(page)
                return
            if settings is not None:
                idx = self._tab_widget.indexOf(settings)
                if idx >= 0:
                    self._tab_widget.setCurrentIndex(idx)
                    if hasattr(settings, "show_page"):
                        settings.show_page(page)
                return
        idx = self._tab_widget.indexOf(target)
        if idx >= 0:
            self._tab_widget.setCurrentIndex(idx)

    def refresh_status(self, control) -> None:
        """从控制面板刷新状态卡片."""
        if control is None:
            return

        name = control.profile_combo.currentText() if hasattr(control, "profile_combo") else ""
        count = control.profile_combo.count() if hasattr(control, "profile_combo") else 0
        self.empty_hint.setVisible(count == 0)
        self.chip_project.set_value(name or "未选择")

        dec_running = "运行中" in control.decrypt_status.text()
        dec_port = control.decrypt_port.value() if hasattr(control, "decrypt_port") else "?"
        self.chip_decrypt.set_value(
            f"{'● 运行' if dec_running else '○ 停止'}  :{dec_port}",
            running=dec_running,
        )

        enc_running = "运行中" in control.encrypt_status.text()
        enc_port = control.encrypt_port.value() if hasattr(control, "encrypt_port") else "?"
        self.chip_encrypt.set_value(
            f"{'● 运行' if enc_running else '○ 停止'}  :{enc_port}",
            running=enc_running,
        )

        cert_text = control.cert_status.text() if hasattr(control, "cert_status") else ""
        trusted = "已安装" in cert_text
        self.chip_cert.set_value(
            "已安装" if trusted else ("未安装" if cert_text else "—"),
            running=trusted if cert_text else None,
        )

    def _update_topology_image(self) -> None:
        if self._topo_pixmap.isNull():
            self._topo_label.setText("浏览器/APP → 解密端(:8080) → Burp(:8083) → 加密端(:8081) → 服务器")
            return
        w = max(480, self.width() - 96)
        self._topo_label.setPixmap(
            self._topo_pixmap.scaledToWidth(w, Qt.TransformationMode.SmoothTransformation)
        )

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if hasattr(self, "_topo_label"):
            self._update_topology_image()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._update_topology_image()
        win = self.window()
        if win and hasattr(win, "control"):
            self.refresh_status(win.control)
