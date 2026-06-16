"""密桥全局主题 — 简洁工具风 QSS，支持亮/暗切换."""

from __future__ import annotations

import os
from PyQt6.QtGui import QFont, QPalette, QColor
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QLabel, QWidget, QComboBox, QPushButton, QVBoxLayout, QFrame

PALETTES: dict[str, dict[str, str]] = {
    "dark": {
        "bg": "#2b2b2b",
        "surface": "#323232",
        "surface2": "#3c3c3c",
        "border": "#505050",
        "text": "#e0e0e0",
        "text_dim": "#999999",
        "accent": "#6a8aaa",
        "primary": "#8ab88a",
        "danger": "#c07070",
        "warn": "#b0a060",
        "purple": "#a090c0",
        "teal": "#80b0a8",
        "input_bg": "#262626",
        "selection": "#4a5568",
        "code_bg": "#1e1e1e",
        "code_fg": "#D4D4D4",
        "tab_text": "#cccccc",
        "tab_text_selected": "#ffffff",
        "danger_hover_bg": "#4a3535",
    },
    "light": {
        "bg": "#f0f0f0",
        "surface": "#ffffff",
        "surface2": "#e8e8e8",
        "border": "#c8c8c8",
        "text": "#1e1e1e",
        "text_dim": "#666666",
        "accent": "#4a7ab8",
        "primary": "#3d8b47",
        "danger": "#c04040",
        "warn": "#9a7b20",
        "purple": "#7a5cad",
        "teal": "#3d8a80",
        "input_bg": "#ffffff",
        "selection": "#cce4f7",
        "code_bg": "#fafafa",
        "code_fg": "#1e1e1e",
        "tab_text": "#555555",
        "tab_text_selected": "#111111",
        "danger_hover_bg": "#fde8e8",
    },
}

_current_theme = "dark"
C: dict[str, str] = dict(PALETTES["dark"])
THEME_QSS = ""
LOG_COLORS: dict[str, str] = {}
HTTP_LOG_COLORS: dict[str, str] = {}


def current_theme() -> str:
    return _current_theme


def build_theme_qss(c: dict[str, str]) -> str:
    return f"""
QWidget {{
    background-color: {c['bg']};
    color: {c['text']};
    font-family: "Segoe UI", "Microsoft YaHei UI", sans-serif;
    font-size: 13px;
}}
QMainWindow {{ background-color: {c['bg']}; }}

#sidebar {{
    background-color: {c['surface']};
    border-right: 1px solid {c['border']};
}}
#appTitle {{
    font-size: 14px;
    font-weight: 600;
    background: transparent;
}}
#appSubtitle {{
    font-size: 11px;
    color: {c['text_dim']};
    background: transparent;
}}
#sidebarBrandCard {{
    background-color: {c['input_bg']};
    border: 1px solid {c['border']};
    border-radius: 8px;
    margin: 0 0 4px 0;
}}
#sidebarBrandLogo {{
    background-color: {c['surface']};
    border: 1px solid {c['border']};
    border-radius: 12px;
    padding: 4px;
}}
#sidebarBrandNameCn {{
    font-size: 20px;
    font-weight: 700;
    letter-spacing: 1px;
    color: {c['text']};
    background: transparent;
}}
#sidebarBrandNameEn {{
    font-size: 13px;
    font-weight: 600;
    color: {c['accent']};
    background: transparent;
    padding-top: 5px;
}}
#sidebarBrandSub {{
    font-size: 12px;
    font-weight: 500;
    color: {c['text']};
    background: transparent;
}}
#sidebarBrandDivider {{
    background-color: {c['border']};
    max-height: 1px;
    margin: 2px 0;
}}
#sidebarBrandCreditMuted {{
    font-size: 10px;
    color: {c['text_dim']};
    background: transparent;
}}
#sidebarBrandCreditOrg {{
    font-size: 10px;
    font-weight: 600;
    color: {c['accent']};
    background: transparent;
}}
#sidebarBrandCreditAuthor {{
    font-size: 10px;
    font-weight: 600;
    color: {c['primary']};
    background: transparent;
}}
#sidebarBrandTitle {{
    font-size: 16px;
    font-weight: 700;
    background: transparent;
}}
#sidebarBrandTagline {{
    font-size: 11px;
    color: {c['text_dim']};
    background: transparent;
}}
QLabel[muted="true"] {{
    color: {c['text_dim']};
    font-size: 12px;
    background: transparent;
}}
QLabel[status="running"] {{ color: {c['primary']}; }}
QLabel[status="stopped"] {{ color: {c['text_dim']}; }}

QGroupBox {{
    background-color: {c['surface']};
    border: 1px solid {c['border']};
    border-radius: 3px;
    margin-top: 12px;
    padding: 12px 8px 8px 8px;
    font-weight: 600;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 6px;
    color: {c['text_dim']};
}}

QLineEdit, QSpinBox, QComboBox, QTextEdit, QPlainTextEdit {{
    background-color: {c['input_bg']};
    border: 1px solid {c['border']};
    border-radius: 3px;
    padding: 5px 8px;
    color: {c['text']};
    selection-background-color: {c['selection']};
}}
QComboBox {{ padding-right: 28px; min-height: 22px; }}
QComboBox::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 24px;
    border-left: 1px solid {c['border']};
    background-color: {c['surface2']};
}}
QComboBox::down-arrow {{
    width: 0; height: 0;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid {c['text_dim']};
}}
QComboBox QAbstractItemView {{
    background-color: {c['surface2']};
    border: 1px solid {c['border']};
    selection-background-color: {c['selection']};
    selection-color: {c['text']};
    outline: none;
    max-height: 320px;
}}
QSpinBox {{ padding-right: 20px; }}
QSpinBox::up-button, QSpinBox::down-button {{
    subcontrol-origin: border;
    background: {c['surface2']};
    border-left: 1px solid {c['border']};
    width: 18px;
}}
QSpinBox::up-button {{ subcontrol-position: top right; }}
QSpinBox::down-button {{ subcontrol-position: bottom right; }}
QSpinBox::up-arrow {{
    width: 0; height: 0;
    border-left: 3px solid transparent;
    border-right: 3px solid transparent;
    border-bottom: 4px solid {c['text_dim']};
}}
QSpinBox::down-arrow {{
    width: 0; height: 0;
    border-left: 3px solid transparent;
    border-right: 3px solid transparent;
    border-top: 4px solid {c['text_dim']};
}}

#codeEditor, QPlainTextEdit#codeEditor {{
    background-color: {c['code_bg']};
    border: 1px solid {c['border']};
    border-radius: 3px;
    padding: 6px;
    font-family: "Cascadia Code", "Consolas", "Courier New", monospace;
    font-size: 12px;
    color: {c['code_fg']};
}}

QPushButton {{
    background-color: {c['surface2']};
    border: 1px solid {c['border']};
    border-radius: 3px;
    padding: 6px 12px;
    color: {c['text']};
    min-height: 20px;
}}
QPushButton:hover {{
    background-color: {c['border']};
}}
QPushButton:pressed {{ background-color: {c['input_bg']}; }}
QPushButton:disabled {{
    color: {c['text_dim']};
    background-color: {c['surface']};
}}
QPushButton[variant="primary"],
QPushButton[variant="accent"],
QPushButton[variant="warn"] {{
    background-color: {c['surface2']};
    border-color: {c['border']};
    color: {c['text']};
}}
QPushButton[variant="primary"]:hover,
QPushButton[variant="accent"]:hover,
QPushButton[variant="warn"]:hover {{
    background-color: {c['border']};
}}
QPushButton[variant="danger"] {{
    border-color: {c['danger']};
    color: {c['danger']};
}}
QPushButton[variant="danger"]:hover {{
    background-color: {c['danger_hover_bg']};
}}
QPushButton[variant="ghost"] {{
    background: transparent;
    border-color: {c['border']};
    color: {c['text_dim']};
}}
QPushButton[variant="ghost"]:hover {{
    color: {c['text']};
    background: {c['surface2']};
}}

QTabWidget::pane {{
    border: 1px solid {c['border']};
    border-radius: 4px;
    background: {c['bg']};
    top: 0px;
    margin-top: 2px;
}}
QTabWidget#mainTabs QTabBar {{
    background: transparent;
}}
QTabWidget#mainTabs QTabBar::tab {{
    background: {c['surface']};
    border: 1px solid {c['border']};
    border-radius: 4px;
    padding: 10px 16px 10px 12px;
    margin: 6px 8px 0 0;
    color: {c['tab_text']};
    min-height: 22px;
}}
QTabWidget#mainTabs QTabBar::tab:selected {{
    background: {c['surface2']};
    border-color: {c['accent']};
    color: {c['tab_text_selected']};
    font-weight: 600;
}}
QTabWidget#mainTabs QTabBar::tab:hover:!selected {{
    background: {c['surface2']};
    border-color: {c['accent']};
    color: {c['tab_text_selected']};
}}

QTreeWidget, QListWidget, QTableWidget {{
    background-color: {c['input_bg']};
    border: 1px solid {c['border']};
    border-radius: 3px;
    outline: none;
    alternate-background-color: {c['surface']};
}}
QTreeWidget::item:selected, QListWidget::item:selected {{
    background-color: {c['selection']};
    color: {c['text']};
}}
QHeaderView::section {{
    background: {c['surface2']};
    border: none;
    border-bottom: 1px solid {c['border']};
    padding: 5px;
    color: {c['text_dim']};
}}

QScrollBar:vertical {{
    background: {c['surface']};
    width: 10px;
}}
QScrollBar::handle:vertical {{
    background: {c['border']};
    min-height: 24px;
}}
QScrollBar::handle:vertical:hover {{ background: {c['text_dim']}; }}
QScrollBar:horizontal {{
    background: {c['surface']};
    height: 10px;
}}
QScrollBar::handle:horizontal {{ background: {c['border']}; }}

QSplitter::handle {{ background: {c['border']}; }}
QSplitter::handle:horizontal {{ width: 1px; }}
QSplitter::handle:vertical {{ height: 1px; }}

QMenu {{
    background: {c['surface2']};
    border: 1px solid {c['border']};
    padding: 2px;
}}
QMenu::item {{ padding: 6px 20px; }}
QMenu::item:selected {{ background: {c['selection']}; }}

QToolButton {{
    background-color: {c['surface2']};
    border: 1px solid {c['border']};
    border-radius: 3px;
    padding: 4px 8px;
    color: {c['text']};
    min-height: 20px;
}}
QToolButton:hover {{ background-color: {c['border']}; }}
QToolButton::menu-indicator {{ image: none; width: 0; }}

QPushButton[sidebarAux="true"] {{
    padding: 3px 8px;
    min-height: 16px;
    font-size: 11px;
    background: transparent;
    border-color: {c['border']};
    color: {c['text_dim']};
}}
QPushButton[sidebarAux="true"]:hover {{
    color: {c['text']};
    background: {c['surface2']};
}}

QFrame[card="true"] {{
    background: {c['surface']};
    border: 1px solid {c['border']};
    border-radius: 3px;
    margin: 2px 0;
}}
QLabel[stepTitle="true"] {{
    font-weight: 600;
    background: transparent;
    font-size: 12px;
}}
QPushButton[compact="true"] {{
    padding: 2px 6px;
    min-height: 14px;
    min-width: 24px;
    max-width: 28px;
    font-size: 12px;
}}

QLabel[feedbackBox="true"] {{
    padding: 6px 8px;
    font-size: 12px;
    border-radius: 3px;
    background: {c['input_bg']};
    border: 1px solid {c['border']};
}}
QLabel[feedbackKind="error"] {{ color: {c['danger']}; border-color: {c['danger']}; }}

#logView {{
    background-color: {c['input_bg']};
    border: 1px solid {c['border']};
    border-radius: 3px;
    font-family: "Consolas", "Courier New", monospace;
    font-size: 11px;
}}

#homeHeroTitle {{
    font-size: 26px;
    font-weight: 700;
    background: transparent;
}}
#homeHeroSub {{
    font-size: 14px;
    color: {c['text_dim']};
    background: transparent;
}}
#homeSectionTitle {{
    font-size: 13px;
    font-weight: 600;
    color: {c['text_dim']};
    background: transparent;
    padding-top: 4px;
}}
#homeStatCard, #homeNavCard, #homeWorkflow {{
    background: {c['surface']};
    border: 1px solid {c['border']};
    border-radius: 4px;
}}
#homeNavCard:hover {{
    background: {c['surface2']};
    border-color: {c['accent']};
}}
#homeStatValue, #homeCardTitle {{
    font-size: 13px;
    font-weight: 600;
    background: transparent;
}}
#homeStepBadge {{
    background: {c['surface2']};
    border: 1px solid {c['border']};
    border-radius: 12px;
    color: {c['accent']};
    font-weight: 700;
    font-size: 11px;
}}
#homeTopology {{
    background: transparent;
    border: none;
    padding: 4px 0;
}}
#homeEmptyHint {{
    background: {c['surface']};
    border: 1px solid {c['border']};
    border-radius: 4px;
    padding: 10px 12px;
    color: {c['text_dim']};
}}
#projectEmptyHint {{
    color: {c['warn']};
    font-size: 12px;
    background: transparent;
}}
"""


def _activate_palette(theme: str) -> None:
    global C, THEME_QSS, LOG_COLORS, HTTP_LOG_COLORS, _current_theme
    _current_theme = theme if theme in PALETTES else "dark"
    C.clear()
    C.update(PALETTES[_current_theme])
    THEME_QSS = build_theme_qss(C)
    LOG_COLORS = {"ERROR": C["danger"], "WARNING": C["warn"], "INFO": C["text"]}
    HTTP_LOG_COLORS = {"request": C["primary"], "response": C["accent"]}


_activate_palette("dark")


def configure_combo_popup(combo: QComboBox, max_visible: int = 12, max_height: int = 320) -> None:
    """限制下拉列表高度，超出部分滚动."""
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QListView

    combo.setMaxVisibleItems(max_visible)
    view = combo.view()
    if view is None or not isinstance(view, QListView):
        view = QListView()
        combo.setView(view)
    view.setMaximumHeight(max_height)
    view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)


def pick_from_list(
    parent,
    title: str,
    items: list[str] | None = None,
    sections: list[tuple[str, list[str]]] | None = None,
    max_height: int = 360,
) -> str | None:
    """滚动列表选择对话框，用于选项较多时替代超长菜单."""
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import (
        QDialog, QVBoxLayout, QListWidget, QListWidgetItem,
        QDialogButtonBox,
    )

    dlg = QDialog(parent)
    dlg.setWindowTitle(title)
    dlg.setMinimumWidth(440)
    layout = QVBoxLayout(dlg)

    list_w = QListWidget()
    list_w.setMaximumHeight(max_height)

    def add_section(section_title: str, names: list[str], with_header: bool) -> None:
        if with_header and section_title:
            header = QListWidgetItem(f"── {section_title} ──")
            header.setFlags(Qt.ItemFlag.NoItemFlags)
            header.setForeground(QColor(C["text_dim"]))
            list_w.addItem(header)
        for name in names:
            list_w.addItem(name)

    if sections:
        for i, (section_title, names) in enumerate(sections):
            add_section(section_title, names, with_header=True)
    elif items:
        for name in items:
            list_w.addItem(name)

    chosen: dict[str, str | None] = {"value": None}

    def accept_item(item: QListWidgetItem | None) -> None:
        if item and (item.flags() & Qt.ItemFlag.ItemIsSelectable):
            chosen["value"] = item.text()
            dlg.accept()

    list_w.itemDoubleClicked.connect(accept_item)
    layout.addWidget(list_w)

    buttons = QDialogButtonBox(
        QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
    )
    buttons.accepted.connect(lambda: accept_item(list_w.currentItem()))
    buttons.rejected.connect(dlg.reject)
    layout.addWidget(buttons)

    if dlg.exec() == QDialog.DialogCode.Accepted:
        return chosen["value"]
    return None


def _install_combo_scroll_limit(max_visible: int = 12, max_height: int = 320) -> None:
    if getattr(QComboBox, "_scroll_limit_installed", False):
        return

    _orig_show = QComboBox.showPopup

    def show_popup(self: QComboBox) -> None:
        if self.count() > max_visible:
            configure_combo_popup(self, max_visible, max_height)
        _orig_show(self)

    QComboBox.showPopup = show_popup  # type: ignore[method-assign]
    QComboBox._scroll_limit_installed = True  # type: ignore[attr-defined]


def _repolish(widget: QWidget) -> None:
    widget.style().unpolish(widget)
    widget.style().polish(widget)


repolish_widget = _repolish


def refresh_widget_tree(root: QWidget) -> None:
    """主题切换后刷新控件样式."""
    if root is None:
        return
    root.style().unpolish(root)
    root.style().polish(root)
    for child in root.findChildren(QWidget):
        child.style().unpolish(child)
        child.style().polish(child)


class CollapsibleBox(QFrame):
    """可折叠面板 — 点击标题展开/收起."""

    def __init__(self, title: str, collapsed: bool = True, parent=None):
        super().__init__(parent)
        self._title = title
        self._collapsed = collapsed
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setProperty("card", True)
        repolish_widget(self)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.toggle_btn = QPushButton()
        self.toggle_btn.setFlat(True)
        self.toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggle_btn.clicked.connect(lambda: self.set_collapsed(not self._collapsed))
        outer.addWidget(self.toggle_btn)

        self.body = QWidget()
        self.body_layout = QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(10, 6, 10, 10)
        self.body_layout.setSpacing(6)
        outer.addWidget(self.body)

        self.set_collapsed(collapsed)

    def set_collapsed(self, collapsed: bool) -> None:
        self._collapsed = collapsed
        self.body.setVisible(not collapsed)
        arrow = "▶" if collapsed else "▼"
        self.toggle_btn.setText(f"{arrow}  {self._title}")

    def is_collapsed(self) -> bool:
        return self._collapsed


def style_button(btn, variant: str = "default") -> None:
    """variant: default | primary | danger | accent | warn | ghost"""
    btn.setProperty("variant", "" if variant == "default" else variant)
    _repolish(btn)


def style_muted_label(label: QLabel) -> None:
    label.setProperty("muted", True)
    _repolish(label)


def style_status_label(label: QLabel, running: bool = False) -> None:
    label.setProperty("status", "running" if running else "stopped")
    _repolish(label)


def setup_code_editor(widget) -> None:
    widget.setObjectName("codeEditor")
    from core.syntax_highlighter import attach_python_highlighter
    attach_python_highlighter(widget)


def build_logo_header(parent_layout, icon_path: str | None = None) -> None:
    """侧边栏品牌区 — 图标 + 标题 + 说明，位于项目选择上方."""
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QPixmap
    from PyQt6.QtWidgets import QFrame, QHBoxLayout, QVBoxLayout, QLabel
    from core.icon_loader import MAIN_ICON
    from core.brand import (
        APP_NAME, APP_NAME_EN, APP_SUBTITLE,
        APP_CREDIT_ORG, APP_CREDIT_AUTHOR,
    )

    card = QFrame()
    card.setObjectName("sidebarBrandCard")
    repolish_widget(card)

    outer = QVBoxLayout(card)
    outer.setContentsMargins(12, 12, 12, 10)
    outer.setSpacing(8)

    row = QHBoxLayout()
    row.setSpacing(12)
    row.setAlignment(Qt.AlignmentFlag.AlignTop)

    logo = QLabel()
    logo.setObjectName("sidebarBrandLogo")
    logo.setFixedSize(56, 56)
    logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
    img = icon_path or MAIN_ICON
    if img:
        pm = QPixmap(img).scaled(
            46, 46, Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        if not pm.isNull():
            logo.setPixmap(pm)
    row.addWidget(logo)

    text_col = QVBoxLayout()
    text_col.setSpacing(2)

    title_row = QHBoxLayout()
    title_row.setSpacing(6)
    title_row.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom)
    name_cn = QLabel(APP_NAME)
    name_cn.setObjectName("sidebarBrandNameCn")
    name_en = QLabel(APP_NAME_EN)
    name_en.setObjectName("sidebarBrandNameEn")
    title_row.addWidget(name_cn)
    title_row.addWidget(name_en)
    title_row.addStretch()
    text_col.addLayout(title_row)

    subtitle = QLabel(APP_SUBTITLE)
    subtitle.setObjectName("sidebarBrandSub")
    text_col.addWidget(subtitle)
    row.addLayout(text_col, 1)
    outer.addLayout(row)

    divider = QFrame()
    divider.setObjectName("sidebarBrandDivider")
    divider.setFrameShape(QFrame.Shape.HLine)
    divider.setFixedHeight(1)
    outer.addWidget(divider)

    credit_row = QHBoxLayout()
    credit_row.setSpacing(0)
    credit_row.setAlignment(Qt.AlignmentFlag.AlignLeft)

    def _credit(text: str, role: str) -> QLabel:
        lb = QLabel(text)
        lb.setObjectName({
            "muted": "sidebarBrandCreditMuted",
            "org": "sidebarBrandCreditOrg",
            "author": "sidebarBrandCreditAuthor",
        }[role])
        return lb

    credit_row.addWidget(_credit("由 ", "muted"))
    credit_row.addWidget(_credit(APP_CREDIT_ORG, "org"))
    credit_row.addWidget(_credit(" · ", "muted"))
    credit_row.addWidget(_credit(APP_CREDIT_AUTHOR, "author"))
    credit_row.addWidget(_credit(" 设计开发", "muted"))
    credit_row.addStretch()
    outer.addLayout(credit_row)

    parent_layout.addWidget(card)
    parent_layout.addSpacing(6)


def style_feedback(label: QLabel, kind: str = "success") -> None:
    """状态文字 — 仅改字色，不加边框."""
    label.setProperty("feedbackBox", False)
    colors = {
        "success": C["primary"],
        "error": C["danger"],
        "warn": C["warn"],
        "info": C["accent"],
        "muted": C["text_dim"],
    }
    label.setStyleSheet(
        f"color:{colors.get(kind, C['text'])}; background:transparent; border:none;"
    )


def style_feedback_box(label: QLabel, kind: str = "neutral") -> None:
    label.setProperty("feedbackBox", True)
    label.setProperty("feedbackKind", kind if kind != "neutral" else "")
    _repolish(label)


def style_step_title(label: QLabel) -> None:
    label.setProperty("stepTitle", True)
    _repolish(label)


def style_compact_button(btn, variant: str = "default") -> None:
    btn.setProperty("compact", True)
    style_button(btn, variant)


def style_sidebar_aux_button(btn) -> None:
    """侧栏次要操作 — 小字、浅色，不抢主按钮视觉."""
    btn.setProperty("sidebarAux", True)
    _repolish(btn)


def setup_main_tabs(tab_widget) -> None:
    """主界面 Tab — 卡片式标签栏 + 图标."""
    from PyQt6.QtCore import QSize
    tab_widget.setObjectName("mainTabs")
    tab_widget.setIconSize(QSize(22, 22))
    tab_widget.setDocumentMode(True)
    bar = tab_widget.tabBar()
    bar.setExpanding(False)
    bar.setUsesScrollButtons(True)
    bar.setDrawBase(False)


def setup_log_view(widget) -> None:
    widget.setObjectName("logView")


def apply_theme(app: QApplication, theme: str | None = None) -> str:
    """应用主题，返回实际使用的 theme 名 (dark/light)."""
    from core.app_settings import get_theme

    name = theme or get_theme()
    if name not in PALETTES:
        name = "dark"

    _activate_palette(name)
    try:
        from core.icon_loader import clear_icon_cache
        clear_icon_cache()
    except ImportError:
        pass

    app.setStyle("Fusion")
    app.setFont(QFont("Microsoft YaHei UI", 10))
    app.setStyleSheet(THEME_QSS)
    _install_combo_scroll_limit()
    p = QPalette()
    p.setColor(QPalette.ColorRole.Window, QColor(C["bg"]))
    p.setColor(QPalette.ColorRole.WindowText, QColor(C["text"]))
    p.setColor(QPalette.ColorRole.Base, QColor(C["input_bg"]))
    p.setColor(QPalette.ColorRole.AlternateBase, QColor(C["surface"]))
    p.setColor(QPalette.ColorRole.Text, QColor(C["text"]))
    p.setColor(QPalette.ColorRole.Button, QColor(C["surface2"]))
    p.setColor(QPalette.ColorRole.ButtonText, QColor(C["text"]))
    p.setColor(QPalette.ColorRole.Highlight, QColor(C["selection"]))
    p.setColor(QPalette.ColorRole.HighlightedText, QColor(C["text"]))
    app.setPalette(p)
    return name
