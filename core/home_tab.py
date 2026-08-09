"""密桥主页 — 参考 Burp / mitm 工位：状态条 + 双栏（上手 | 拓扑）."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QSizePolicy, QSplitter, QVBoxLayout, QWidget,
)

from core.brand import APP_NAME, APP_NAME_EN, APP_SUBTITLE, APP_VERSION
from core.icon_loader import TOPOLOGY_IMAGE, set_btn_icon
from core.theme import style_button, style_muted_label


class _StatCell(QWidget):
    def __init__(self, label: str, parent=None):
        super().__init__(parent)
        self.setObjectName("homeStatCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(3)
        self._label = QLabel(label)
        self._label.setObjectName("homeStatLabel")
        self._value = QLabel("—")
        self._value.setObjectName("homeStatValue")
        layout.addWidget(self._label)
        layout.addWidget(self._value)

    def set_value(self, text: str, *, running: bool | None = None) -> None:
        self._value.setText(text)
        if running is True:
            self._value.setProperty("state", "running")
        elif running is False:
            self._value.setProperty("state", "stopped")
        else:
            self._value.setProperty("state", "")
        self._value.style().unpolish(self._value)
        self._value.style().polish(self._value)


class HomeTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("homePage")
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
        body.setObjectName("homeBody")
        root = QVBoxLayout(body)
        root.setContentsMargins(24, 18, 24, 24)
        root.setSpacing(14)

        # —— 顶栏：品牌 + CTA（工位工具常见顶栏）——
        header = QFrame()
        header.setObjectName("homeHeader")
        hh = QHBoxLayout(header)
        hh.setContentsMargins(16, 14, 16, 14)
        hh.setSpacing(12)

        brand_col = QVBoxLayout()
        brand_col.setSpacing(2)
        brand = QLabel(f"{APP_NAME}  {APP_NAME_EN}")
        brand.setObjectName("homeHeroTitle")
        brand_col.addWidget(brand)
        sub = QLabel(f"{APP_SUBTITLE}  ·  {APP_VERSION}")
        sub.setObjectName("homeHeroSub")
        brand_col.addWidget(sub)
        hh.addLayout(brand_col, 1)

        for text, key, icon_name, variant in (
            ("解析报文", "parser", "upload", "primary"),
            ("构建器", "builder", "builder", "accent"),
            ("AI 实验室", "ai", "ai", "ghost"),
        ):
            b = QPushButton(text)
            b.setFixedHeight(30)
            b.setMinimumWidth(96)
            style_button(b, variant)
            try:
                set_btn_icon(b, icon_name, size=13)
            except Exception:
                pass
            b.clicked.connect(lambda _=False, k=key: self._go(k))
            hh.addWidget(b)
        root.addWidget(header)

        # —— 运行状态 ——
        root.addWidget(self._section("运行状态"))
        strip = QFrame()
        strip.setObjectName("homeStatStrip")
        stat_row = QHBoxLayout(strip)
        stat_row.setContentsMargins(0, 0, 0, 0)
        stat_row.setSpacing(0)
        self.chip_project = _StatCell("当前项目")
        self.chip_decrypt = _StatCell("解密端")
        self.chip_encrypt = _StatCell("加密端")
        self.chip_cert = _StatCell("HTTPS 证书")
        cells = (self.chip_project, self.chip_decrypt, self.chip_encrypt, self.chip_cert)
        self._stat_seps: list[QFrame] = []
        for i, chip in enumerate(cells):
            chip.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            stat_row.addWidget(chip)
            if i < len(cells) - 1:
                sep = QFrame()
                sep.setObjectName("homeStatSep")
                sep.setFixedWidth(1)
                stat_row.addWidget(sep)
                self._stat_seps.append(sep)
        root.addWidget(strip)

        # —— 双栏：上手 + 拓扑 ——
        split = QSplitter(Qt.Orientation.Horizontal)
        split.setChildrenCollapsible(False)
        split.setHandleWidth(8)

        left = QFrame()
        left.setObjectName("homePanel")
        ll = QVBoxLayout(left)
        ll.setContentsMargins(14, 12, 14, 12)
        ll.setSpacing(10)
        ll.addWidget(self._section("上手流程"))
        flow_tip = QLabel("四步完成一次加解密代理落地")
        style_muted_label(flow_tip)
        ll.addWidget(flow_tip)

        steps = [
            ("1", "解析报文", "粘贴抓包，点选密文字段"),
            ("2", "组装步骤", "构建器调序并预览代码"),
            ("3", "保存项目", "左侧面板选择项目"),
            ("4", "启动代理", "启停解密/加密端"),
        ]
        for num, title, desc in steps:
            row = QHBoxLayout()
            row.setSpacing(10)
            badge = QLabel(num)
            badge.setObjectName("homeStepBadge")
            badge.setFixedSize(22, 22)
            badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            row.addWidget(badge)
            col = QVBoxLayout()
            col.setSpacing(1)
            t = QLabel(title)
            t.setObjectName("homeCardTitle")
            d = QLabel(desc)
            d.setObjectName("homeStepDesc")
            col.addWidget(t)
            col.addWidget(d)
            row.addLayout(col, 1)
            ll.addLayout(row)

        ll.addSpacing(6)
        qlab = QLabel("快捷入口")
        qlab.setObjectName("homeSectionTitle")
        ll.addWidget(qlab)
        qrow = QHBoxLayout()
        qrow.setSpacing(6)
        for text, key, icon_name in (
            ("加解密测试", "crypto", "setting"),
            ("日志", "log", "code"),
            ("插件", "plugin", "edit"),
        ):
            b = QPushButton(text)
            b.setFixedHeight(26)
            style_button(b, "ghost")
            try:
                set_btn_icon(b, icon_name, size=12)
            except Exception:
                pass
            b.clicked.connect(lambda _=False, k=key: self._go(k))
            qrow.addWidget(b)
        qrow.addStretch()
        ll.addLayout(qrow)
        ll.addStretch()
        split.addWidget(left)

        right = QFrame()
        right.setObjectName("homePanel")
        rl = QVBoxLayout(right)
        rl.setContentsMargins(14, 12, 14, 12)
        rl.setSpacing(8)
        rl.addWidget(self._section("部署拓扑"))
        topo_hint = QLabel("浏览器 / APP → 解密端 → Burp → 加密端 → 服务器")
        style_muted_label(topo_hint)
        rl.addWidget(topo_hint)
        self._topo_label = QLabel()
        self._topo_label.setObjectName("homeTopology")
        self._topo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._topo_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self._topo_pixmap = QPixmap(TOPOLOGY_IMAGE)
        self._update_topology_image()
        rl.addWidget(self._topo_label, 1)
        split.addWidget(right)

        split.setStretchFactor(0, 2)
        split.setStretchFactor(1, 3)
        split.setSizes([360, 560])
        root.addWidget(split, 1)

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
        nested = {
            "crypto": ("settings", 1),
            "log": ("settings", 2),
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
        if control is None:
            return

        name = control.profile_combo.currentText() if hasattr(control, "profile_combo") else ""
        self.chip_project.set_value(name or "未选择")

        roles = []
        if name and hasattr(control, "_profile_roles"):
            roles = control._profile_roles(name)

        dec_running = "运行中" in control.decrypt_status.text()
        dec_port = control.decrypt_port.value() if hasattr(control, "decrypt_port") else "?"
        has_decrypt = (not name) or ("decrypt" in roles) or dec_running
        self.chip_decrypt.setVisible(has_decrypt)
        if has_decrypt:
            self.chip_decrypt.set_value(
                f"{'运行' if dec_running else '停止'}  :{dec_port}",
                running=dec_running,
            )

        enc_running = "运行中" in control.encrypt_status.text()
        enc_port = control.encrypt_port.value() if hasattr(control, "encrypt_port") else "?"
        has_encrypt = ("encrypt" in roles) or enc_running
        self.chip_encrypt.setVisible(has_encrypt)
        if has_encrypt:
            self.chip_encrypt.set_value(
                f"{'运行' if enc_running else '停止'}  :{enc_port}",
                running=enc_running,
            )

        if len(self._stat_seps) >= 3:
            self._stat_seps[0].setVisible(self.chip_decrypt.isVisible())
            self._stat_seps[1].setVisible(self.chip_encrypt.isVisible())
            self._stat_seps[2].setVisible(True)

        cert_text = control.cert_status.text() if hasattr(control, "cert_status") else ""
        trusted = "已安装" in cert_text
        self.chip_cert.set_value(
            "已安装" if trusted else ("未安装" if cert_text else "—"),
            running=trusted if cert_text else None,
        )

    def _update_topology_image(self) -> None:
        if self._topo_pixmap.isNull():
            self._topo_label.setText(
                "浏览器/APP → 解密端(:8083) → Burp(:8080) → 加密端(:8081) → 服务器"
            )
            return
        # 双栏内宽度更窄
        avail = max(280, min(self.width() - 420, 720))
        self._topo_label.setPixmap(
            self._topo_pixmap.scaledToWidth(avail, Qt.TransformationMode.SmoothTransformation)
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
