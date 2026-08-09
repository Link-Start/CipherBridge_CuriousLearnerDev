"""密桥全局主题 — 参考 FlatLaf Darcula（Burp）、VS Code Dark+、mitmweb 社区暗色。

布局取向：工位工具（侧栏控制 + 主区 Tab），边框分层、单一蓝强调、少装饰。
"""

from __future__ import annotations

import os
from PyQt6.QtGui import QFont, QPalette, QColor
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QLabel, QWidget, QComboBox, QPushButton, QVBoxLayout, QFrame

# FlatLaf Darcula / JetBrains New UI Dark + VS Code Dark+ 混合；浅色对齐 FlatLaf Light。
PALETTES: dict[str, dict[str, str]] = {
    "dark": {
        "bg": "#1e1f22",
        "surface": "#2b2d30",
        "surface2": "#3c3f41",
        "border": "#45484c",
        "text": "#bcbec4",
        "text_dim": "#8a8f98",
        "accent": "#548af7",
        "primary": "#3574f0",
        "primary_hover": "#4b85f5",
        "danger": "#e16855",
        "warn": "#d5a021",
        "ok": "#499c54",
        "purple": "#8a8a8a",
        "teal": "#8a8a8a",
        "input_bg": "#1e1f22",
        "selection": "#2e436e",
        "code_bg": "#1a1b1e",
        "code_fg": "#bcbec4",
        "tab_text": "#8a8f98",
        "tab_text_selected": "#ffffff",
        "danger_hover_bg": "#3d2a28",
        "primary_fg": "#ffffff",
        "accent_fg": "#ffffff",
        "focus": "#3574f0",
        "badge_bg": "#3c3f41",
        "pane": "#1e1f22",
    },
    "light": {
        "bg": "#f7f8fa",
        "surface": "#ffffff",
        "surface2": "#ebecf0",
        "border": "#d0d3d9",
        "text": "#27282e",
        "text_dim": "#6c707e",
        "accent": "#3574f0",
        "primary": "#3574f0",
        "primary_hover": "#2b5fc7",
        "danger": "#db3b28",
        "warn": "#a67005",
        "ok": "#2e7d32",
        "purple": "#777777",
        "teal": "#777777",
        "input_bg": "#ffffff",
        "selection": "#d4e2ff",
        "code_bg": "#1e1f22",
        "code_fg": "#bcbec4",
        "tab_text": "#6c707e",
        "tab_text_selected": "#1a1b1e",
        "danger_hover_bg": "#fdecea",
        "primary_fg": "#ffffff",
        "accent_fg": "#ffffff",
        "focus": "#3574f0",
        "badge_bg": "#ebecf0",
        "pane": "#f7f8fa",
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
    r = "4px"
    pane = c.get("pane", c["surface"])
    return f"""
QWidget {{
    background-color: {c['bg']};
    color: {c['text']};
    font-family: "Segoe UI", "Microsoft YaHei UI", "PingFang SC", sans-serif;
    font-size: 12px;
}}
QMainWindow {{ background-color: {c['bg']}; }}

#sidebar {{
    background-color: {c['surface']};
    border-right: 1px solid {c['border']};
}}
#sidebar QGroupBox {{
    background-color: transparent;
    border: none;
    border-top: 1px solid {c['border']};
    border-radius: 0;
    margin-top: 10px;
    padding: 10px 4px 6px 4px;
    font-weight: 600;
    font-size: 11px;
    color: {c['text_dim']};
}}
#sidebar QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 0;
    padding: 0 0 6px 0;
    color: {c['text_dim']};
    font-weight: 600;
}}
#sidebar QPushButton {{
    min-height: 28px;
    padding: 4px 10px;
    border-radius: {r};
}}
#sidebar QComboBox, #sidebar QSpinBox {{
    min-height: 26px;
    padding: 3px 6px;
    border-radius: {r};
}}
#workspacePane {{
    background-color: {pane};
    border: none;
    border-radius: 0;
}}
#appTitle {{
    font-size: 14px;
    font-weight: 700;
    background: transparent;
}}
#appSubtitle {{
    font-size: 11px;
    color: {c['text_dim']};
    background: transparent;
}}
#sidebarBrandCard {{
    background: transparent;
    border: none;
    border-radius: 0;
    margin: 0;
    padding-bottom: 12px;
    border-bottom: 1px solid {c['border']};
}}
#sidebarBrandLogo {{
    background: {c['surface2']};
    border: 1px solid {c['border']};
    border-radius: 8px;
    padding: 3px;
}}
#sidebarBrandNameCn {{
    font-size: 15px;
    font-weight: 700;
    color: {c['text']};
    background: transparent;
}}
#sidebarBrandNameEn {{
    font-size: 10px;
    font-weight: 500;
    color: {c['text_dim']};
    background: transparent;
}}
#sidebarBrandVersion {{
    font-size: 9px;
    font-weight: 500;
    color: {c['text_dim']};
    background: transparent;
    border: none;
    border-radius: 0;
    padding: 0;
}}
#sidebarBrandSub {{
    font-size: 10px;
    font-weight: 400;
    color: {c['text_dim']};
    background: transparent;
    padding-top: 1px;
}}
#sidebarBrandDivider {{
    background-color: {c['border']};
    max-height: 1px;
    margin: 2px 0;
}}
#sidebarBrandCreditMuted {{
    font-size: 9px;
    color: {c['text_dim']};
    background: transparent;
    padding-top: 4px;
}}
#sidebarBrandCreditOrg {{
    font-size: 9px;
    font-weight: 500;
    color: {c['text_dim']};
    background: transparent;
}}
#sidebarBrandCreditAuthor {{
    font-size: 9px;
    font-weight: 500;
    color: {c['text_dim']};
    background: transparent;
}}
#sidebarBrandTitle {{
    font-size: 13px;
    font-weight: 600;
    background: transparent;
}}
#sidebarBrandTagline {{
    font-size: 10px;
    color: {c['text_dim']};
    background: transparent;
}}
#aiReadyChip {{
    border-radius: {r};
    padding: 2px 8px;
    font-size: 11px;
}}
#aiNextHint {{
    background: {c['surface']};
    border: 1px solid {c['border']};
    border-radius: {r};
    padding: 8px 10px;
    color: {c['text_dim']};
}}
#aiTargetPanel {{
    background: {c['surface']};
    border: 1px solid {c['border']};
    border-radius: 6px;
}}
#aiTargetPanelTitle {{
    font-size: 11px;
    font-weight: 600;
    color: {c['text']};
    background: transparent;
}}
#aiTargetStatus {{
    font-size: 11px;
    color: {c['text_dim']};
    background: {c['surface2']};
    border: 1px solid {c['border']};
    border-radius: 10px;
    padding: 2px 8px;
}}
#aiTargetStatus[ready="true"] {{
    color: {c['ok']};
    border-color: {c['ok']};
}}
#aiAgentToolbar {{
    background: transparent;
}}
#fieldTargetDialog #ftDialogTitle {{
    font-size: 13px;
    font-weight: 600;
    color: {c['text']};
    background: transparent;
}}
#fieldTargetDialog #ftDialogSub {{
    font-size: 11px;
    color: {c['text_dim']};
    background: transparent;
}}
#fieldTargetDialog #ftStatusChip {{
    font-size: 10px;
    color: {c['text']};
    background: {c['surface2']};
    border: 1px solid {c['border']};
    border-radius: 8px;
    padding: 1px 6px;
}}
#fieldTargetDialog #ftPanel {{
    background: {c['surface']};
    border: 1px solid {c['border']};
    border-radius: 4px;
}}
#fieldTargetDialog #ftPanelTitle {{
    font-size: 11px;
    font-weight: 600;
    background: transparent;
}}
#fieldTargetDialog #ftStepBadge {{
    font-size: 10px;
    font-weight: 700;
    font-family: "Cascadia Code", "Consolas", monospace;
    color: {c['primary_fg']};
    background: {c['primary']};
    border-radius: 8px;
}}
#fieldTargetDialog #ftSegBar {{
    background: {c['surface2']};
    border: 1px solid {c['border']};
    border-radius: 4px;
}}
#fieldTargetDialog QPushButton#ftSegBtn {{
    background: transparent;
    border: none;
    border-radius: 3px;
    color: {c['text_dim']};
    font-size: 11px;
    font-weight: 500;
    padding: 2px 6px;
    min-height: 0;
}}
#fieldTargetDialog QPushButton#ftSegBtn:hover {{
    color: {c['text']};
    background: {c['bg']};
}}
#fieldTargetDialog QPushButton#ftSegBtn:checked {{
    color: {c['primary_fg']};
    background: {c['primary']};
    font-weight: 600;
}}
#fieldTargetDialog #ftFlowList {{
    background: {c['input_bg']};
    border: 1px solid {c['border']};
    border-radius: 3px;
    padding: 0;
    font-size: 11px;
}}
#fieldTargetDialog #ftFlowList::item {{
    padding: 3px 6px;
    border-radius: 2px;
    margin: 0;
}}
#fieldTargetDialog #ftFlowList::item:selected {{
    background: {c['selection']};
    color: {c['text']};
}}
#fieldTargetDialog #ftFieldTree {{
    background: {c['input_bg']};
    border: 1px solid {c['border']};
    border-radius: 3px;
    font-size: 11px;
}}
#fieldTargetDialog #ftFieldTree::item {{
    padding: 1px 0;
}}
#fieldTargetDialog #ftPickedList {{
    background: {c['input_bg']};
    border: 1px solid {c['border']};
    border-radius: 3px;
    font-size: 11px;
}}
#fieldTargetDialog #ftPickedList::item {{
    padding: 2px 6px;
    border-radius: 2px;
}}
#fieldTargetDialog #ftEmptyHint {{
    color: {c['warn']};
    background: {c['surface2']};
    border: 1px solid {c['border']};
    border-radius: 3px;
    padding: 4px 8px;
    font-size: 11px;
}}
#aiHeroBtn {{
    font-size: 12px;
    font-weight: 600;
    min-height: 32px;
    border-radius: {r};
}}
QLabel[muted="true"] {{
    color: {c['text_dim']};
    font-size: 11px;
    background: transparent;
}}
QLabel[status="running"] {{ color: {c['ok']}; font-weight: 600; }}
QLabel[status="stopped"] {{ color: {c['text_dim']}; }}

QGroupBox {{
    background-color: {c['surface']};
    border: 1px solid {c['border']};
    border-radius: 6px;
    margin-top: 12px;
    padding: 12px 10px 10px 10px;
    font-weight: 600;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    padding: 0 6px;
    color: {c['text_dim']};
    background-color: {c['surface']};
}}
#cryptoWorkbench {{
    background-color: transparent;
}}
#cryptoSidePanel {{
    background-color: {c['surface']};
    border: none;
    border-right: 1px solid {c['border']};
    border-radius: 0;
}}
#cryptoSidePanel QLabel {{
    background: transparent;
}}
#cryptoPanelTitle {{
    font-size: 12px;
    font-weight: 600;
    color: {c['text']};
    background: transparent;
    padding: 0 0 2px 0;
}}
#cryptoFieldLabel {{
    font-size: 11px;
    font-weight: 500;
    color: {c['text_dim']};
    background: transparent;
    padding: 0 0 2px 0;
}}
#analyzerEmptyHint {{
    color: {c['text_dim']};
    font-size: 12px;
    background: transparent;
    padding: 20px 12px;
}}

QLineEdit, QSpinBox, QComboBox, QTextEdit, QPlainTextEdit {{
    background-color: {c['input_bg']};
    border: 1px solid {c['border']};
    border-radius: {r};
    padding: 6px 10px;
    color: {c['text']};
    selection-background-color: {c['selection']};
}}
QLineEdit:focus, QSpinBox:focus, QComboBox:focus, QTextEdit:focus, QPlainTextEdit:focus {{
    border: 1px solid {c['focus']};
}}
QComboBox {{ padding-right: 24px; min-height: 22px; }}
QComboBox::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 22px;
    border-left: 1px solid {c['border']};
    background-color: {c['surface2']};
    border-top-right-radius: {r};
    border-bottom-right-radius: {r};
}}
QComboBox::down-arrow {{
    width: 0; height: 0;
    border-left: 3px solid transparent;
    border-right: 3px solid transparent;
    border-top: 4px solid {c['text_dim']};
}}
QComboBox QAbstractItemView {{
    background-color: {c['surface2']};
    border: 1px solid {c['border']};
    selection-background-color: {c['selection']};
    selection-color: {c['text']};
    outline: none;
    max-height: 320px;
}}
QSpinBox {{ padding-right: 18px; }}
QSpinBox::up-button, QSpinBox::down-button {{
    subcontrol-origin: border;
    background: {c['surface2']};
    border-left: 1px solid {c['border']};
    width: 16px;
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

#codeEditor, QPlainTextEdit#codeEditor, QTextEdit#codeEditor {{
    background-color: {c['code_bg']};
    border: 1px solid {c['border']};
    border-radius: {r};
    padding: 10px 12px;
    font-family: "Cascadia Code", "Consolas", "Courier New", monospace;
    font-size: 12px;
    line-height: 1.45;
    color: {c['code_fg']};
    selection-background-color: {c['selection']};
    selection-color: {c['text']};
}}
#logView {{
    background-color: {c['code_bg']};
    border: 1px solid {c['border']};
    border-radius: {r};
    font-family: "Cascadia Code", "Consolas", "Courier New", monospace;
    font-size: 12px;
    color: {c['code_fg']};
    padding: 8px;
}}
#monoField, QPlainTextEdit#monoField, QTextEdit#monoField, QLineEdit#monoField {{
    background-color: {c['code_bg']};
    border: 1px solid {c['border']};
    border-radius: {r};
    padding: 8px 10px;
    font-family: "Cascadia Code", "Consolas", "Courier New", monospace;
    font-size: 12px;
    color: {c['code_fg']};
    selection-background-color: {c['selection']};
}}
#monoField:focus, QPlainTextEdit#monoField:focus, QLineEdit#monoField:focus {{
    border: 1px solid {c['focus']};
}}
QTabWidget#subTabs::pane {{
    border: none;
    border-radius: 0;
    background: transparent;
    padding: 10px 8px 8px 8px;
}}
QTabWidget#subTabs QTabBar {{
    background: {c['surface']};
    border-bottom: 1px solid {c['border']};
}}
QTabWidget#subTabs {{
    background: transparent;
}}
QTabWidget#subTabs QTabBar::tab {{
    background: transparent;
    border: none;
    border-bottom: 2px solid transparent;
    border-radius: 0;
    padding: 8px 14px 7px 14px;
    margin: 0 1px;
    color: {c['tab_text']};
    min-height: 18px;
}}
QTabWidget#subTabs QTabBar::tab:selected {{
    background: transparent;
    border-bottom: 2px solid {c['primary']};
    color: {c['tab_text_selected']};
    font-weight: 600;
}}
QTabWidget#subTabs QTabBar::tab:hover:!selected {{
    background: {c['surface2']};
    color: {c['tab_text_selected']};
}}

QPushButton {{
    background-color: {c['surface']};
    border: 1px solid {c['border']};
    border-radius: {r};
    padding: 6px 16px;
    color: {c['text']};
    min-height: 24px;
}}
QPushButton:hover {{
    background-color: {c['surface2']};
    border-color: {c['text_dim']};
}}
QPushButton:pressed {{ background-color: {c['input_bg']}; }}
QPushButton:disabled {{
    color: {c['text_dim']};
    background-color: {c['surface2']};
    border-color: {c['border']};
}}
QPushButton[variant="primary"] {{
    background-color: {c['primary']};
    border: 1px solid {c['primary']};
    color: {c['primary_fg']};
    font-weight: 600;
}}
QPushButton[variant="primary"]:hover {{
    background-color: {c['primary_hover']};
    border-color: {c['primary_hover']};
    color: {c['primary_fg']};
}}
QPushButton[variant="primary"]:pressed {{
    background-color: {c['surface2']};
    border-color: {c['text_dim']};
    color: {c['text']};
}}
QPushButton[variant="accent"] {{
    background-color: {c['surface2']};
    border: 1px solid {c['accent']};
    color: {c['accent']};
    font-weight: 600;
}}
QPushButton[variant="accent"]:hover {{
    background-color: {c['primary']};
    border-color: {c['primary']};
    color: {c['primary_fg']};
}}
QPushButton[variant="warn"] {{
    background-color: transparent;
    border: 1px solid {c['warn']};
    color: {c['warn']};
}}
QPushButton[variant="warn"]:hover {{
    background-color: {c['surface2']};
}}
QPushButton[variant="danger"] {{
    background-color: transparent;
    border: 1px solid {c['danger']};
    color: {c['danger']};
}}
QPushButton[variant="danger"]:hover {{
    background-color: {c['danger_hover_bg']};
}}
QPushButton[variant="danger_fill"] {{
    background-color: {c['danger']};
    border: 1px solid {c['danger']};
    color: #ffffff;
    font-weight: 600;
}}
QPushButton[variant="danger_fill"]:hover {{
    background-color: #b54a46;
    border-color: #b54a46;
}}
QPushButton[variant="danger_fill"]:disabled {{
    background-color: {c['surface2']};
    border-color: {c['border']};
    color: {c['text_dim']};
}}
QPushButton[variant="ghost"] {{
    background: transparent;
    border-color: {c['border']};
    color: {c['text_dim']};
}}
QPushButton[variant="ghost"]:hover {{
    color: {c['text']};
    background: {c['surface2']};
    border-color: {c['border']};
}}

QTabWidget::pane {{
    border: 1px solid {c['border']};
    border-radius: {r};
    background: {pane};
    top: -1px;
    padding: 8px;
}}
QTabBar {{
    background: {c['surface']};
    border-bottom: 1px solid {c['border']};
}}
QTabBar::tab {{
    background: transparent;
    border: none;
    border-bottom: 2px solid transparent;
    border-radius: 0;
    padding: 8px 14px 7px 14px;
    margin: 0 1px;
    color: {c['tab_text']};
    min-height: 18px;
}}
QTabBar::tab:selected {{
    background: transparent;
    border-bottom: 2px solid {c['primary']};
    color: {c['tab_text_selected']};
    font-weight: 600;
}}
QTabBar::tab:hover:!selected {{
    color: {c['tab_text_selected']};
    background: {c['surface2']};
}}
QTabBar::scroller {{
    width: 20px;
    background: {c['surface']};
    border: none;
}}
QTabBar QToolButton {{
    background: {c['surface']};
    border: 1px solid {c['border']};
    border-radius: {r};
    padding: 2px;
}}
QTabBar QToolButton:hover {{
    background: {c['surface2']};
}}
QTabWidget#mainTabs::pane {{
    border: none;
    border-radius: 0;
    background: transparent;
    padding: 10px 12px 12px 12px;
}}
QTabWidget#mainTabs {{
    background: transparent;
}}
QTabWidget#mainTabs QTabBar {{
    background: {c['surface']};
    border: none;
    border-bottom: 1px solid {c['border']};
    min-height: 38px;
    padding-left: 6px;
}}
QTabWidget#mainTabs QTabBar::tab {{
    background: transparent;
    border: none;
    border-bottom: 2px solid transparent;
    border-radius: 0;
    padding: 10px 16px 8px 16px;
    margin: 0 1px;
    color: {c['tab_text']};
    min-height: 20px;
}}
QTabWidget#mainTabs QTabBar::tab:selected {{
    background: transparent;
    border: none;
    border-bottom: 2px solid {c['primary']};
    color: {c['tab_text_selected']};
    font-weight: 600;
}}
QTabWidget#mainTabs QTabBar::tab:hover:!selected {{
    background: {c['surface2']};
    color: {c['tab_text_selected']};
}}

QTreeWidget, QListWidget, QTableWidget {{
    background-color: {c['input_bg']};
    border: 1px solid {c['border']};
    border-radius: {r};
    outline: none;
    alternate-background-color: {c['surface']};
    padding: 2px;
}}
QTreeWidget::item, QListWidget::item {{
    padding: 5px 8px;
    border-radius: {r};
    margin: 1px 2px;
}}
QTreeWidget::item:hover, QListWidget::item:hover {{
    background-color: {c['surface2']};
}}
QTreeWidget::item:selected, QListWidget::item:selected {{
    background-color: {c['selection']};
    color: {c['text']};
}}
QHeaderView::section {{
    background: {c['surface2']};
    border: none;
    border-bottom: 1px solid {c['border']};
    padding: 6px 8px;
    color: {c['text_dim']};
    font-weight: 600;
}}

QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 2px;
}}
QScrollBar::handle:vertical {{
    background: {c['border']};
    min-height: 28px;
    border-radius: 4px;
}}
QScrollBar::handle:vertical:hover {{ background: {c['text_dim']}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
QScrollBar:horizontal {{
    background: transparent;
    height: 10px;
    margin: 2px;
}}
QScrollBar::handle:horizontal {{
    background: {c['border']};
    min-width: 28px;
    border-radius: 4px;
}}
QScrollBar::handle:horizontal:hover {{ background: {c['text_dim']}; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{ background: transparent; }}

QSplitter::handle {{ background: {c['border']}; }}
QSplitter::handle:hover {{ background: {c['text_dim']}; }}
QSplitter::handle:horizontal {{ width: 1px; margin: 0; }}
QSplitter::handle:vertical {{ height: 1px; margin: 0; }}
#cryptoWorkbench QSplitter::handle:horizontal {{
    width: 1px;
    margin: 0;
    background: {c['border']};
}}
#cryptoWorkbench QSplitter::handle:vertical {{
    height: 1px;
    margin: 0;
    background: {c['border']};
}}

QMenu {{
    background: {c['surface2']};
    border: 1px solid {c['border']};
    border-radius: {r};
    padding: 4px;
}}
QMenu::item {{
    padding: 7px 20px;
    border-radius: 4px;
}}
QMenu::item:selected {{ background: {c['selection']}; }}
QMenu::separator {{
    height: 1px;
    background: {c['border']};
    margin: 4px 8px;
}}

QToolTip {{
    background-color: {c['surface2']};
    color: {c['text']};
    border: 1px solid {c['border']};
    padding: 6px 10px;
    border-radius: {r};
    font-size: 11px;
    opacity: 255;
}}

QToolButton {{
    background-color: {c['surface']};
    border: 1px solid {c['border']};
    border-radius: {r};
    padding: 4px 8px;
    color: {c['text']};
    min-height: 18px;
}}
QToolButton:hover {{ background-color: {c['surface2']}; }}
QToolButton::menu-indicator {{ image: none; width: 0; }}

QCheckBox {{
    spacing: 6px;
    background: transparent;
}}
QCheckBox::indicator {{
    width: 15px;
    height: 15px;
    border-radius: 4px;
    border: 1px solid {c['border']};
    background: {c['input_bg']};
}}
QCheckBox::indicator:checked {{
    background: {c['accent']};
    border-color: {c['accent']};
}}
QCheckBox::indicator:hover {{
    border-color: {c['accent']};
}}

QPushButton[sidebarAux="true"],
QToolButton[sidebarAux="true"] {{
    padding: 4px;
    min-height: 24px;
    min-width: 24px;
    font-size: 11px;
    background: transparent;
    border: 1px solid transparent;
    border-radius: {r};
    color: {c['text']};
}}
QPushButton[sidebarAux="true"]:hover,
QToolButton[sidebarAux="true"]:hover {{
    color: {c['text']};
    background: {c['surface2']};
    border-color: {c['border']};
}}

QFrame[card="true"] {{
    background: {c['surface']};
    border: 1px solid {c['border']};
    border-radius: {r};
    margin: 1px 0;
}}
QLabel[stepTitle="true"] {{
    font-weight: 600;
    background: transparent;
    font-size: 12px;
}}
QPushButton[compact="true"] {{
    padding: 1px 5px;
    min-height: 14px;
    min-width: 22px;
    max-width: 26px;
    font-size: 11px;
    border-radius: {r};
}}

QLabel[feedbackBox="true"] {{
    padding: 8px 10px;
    font-size: 11px;
    border-radius: {r};
    background: {c['input_bg']};
    border: 1px solid {c['border']};
}}
QLabel[feedbackKind="error"] {{ color: {c['danger']}; border-color: {c['danger']}; }}

#homeHeader {{
    background: {c['surface']};
    border: 1px solid {c['border']};
    border-radius: 8px;
}}
#homeHeroTitle {{
    font-size: 18px;
    font-weight: 700;
    color: {c['text']};
    background: transparent;
}}
#homeHeroSub {{
    font-size: 11px;
    color: {c['text_dim']};
    background: transparent;
}}
#homeHeroTip {{
    font-size: 11px;
    color: {c['text_dim']};
    background: transparent;
}}
#homeSectionTitle {{
    font-size: 11px;
    font-weight: 700;
    color: {c['text_dim']};
    background: transparent;
    letter-spacing: 0.3px;
}}
#homeStatStrip {{
    background: {c['surface']};
    border: 1px solid {c['border']};
    border-radius: 8px;
}}
#homeStatSep {{
    background-color: {c['border']};
    max-width: 1px;
    border: none;
}}
#homeStatCard {{
    background: transparent;
    border: none;
}}
#homeStatLabel {{
    font-size: 11px;
    color: {c['text_dim']};
    background: transparent;
}}
#homeStatValue {{
    font-size: 13px;
    font-weight: 600;
    color: {c['text']};
    background: transparent;
}}
#homeStatValue[state="running"] {{
    color: {c['ok']};
}}
#homeStatValue[state="stopped"] {{
    color: {c['text_dim']};
}}
#homePanel {{
    background: {c['surface']};
    border: 1px solid {c['border']};
    border-radius: 8px;
}}
#homeCardTitle {{
    font-size: 12px;
    font-weight: 600;
    background: transparent;
}}
#homeStepBadge {{
    background: {c['primary']};
    border: none;
    border-radius: 11px;
    color: {c['primary_fg']};
    font-weight: 700;
    font-size: 11px;
    font-family: "Cascadia Code", "Consolas", monospace;
}}
#homeStepDesc {{
    font-size: 11px;
    color: {c['text_dim']};
    background: transparent;
}}
#homeStepCard {{
    background: {c['surface']};
    border: 1px solid {c['border']};
    border-radius: 8px;
}}
#homeTopoCard {{
    background: {c['surface']};
    border: 1px solid {c['border']};
    border-radius: 8px;
}}
#homeTopology {{
    background: transparent;
    border: none;
    padding: 4px 0;
}}
#homeEmptyHint {{
    background: transparent;
    border: none;
    border-left: 2px solid {c['border']};
    padding: 4px 0 4px 10px;
    color: {c['text_dim']};
}}
#projectEmptyHint {{
    color: {c['text_dim']};
    font-size: 11px;
    background: transparent;
}}
QDialogButtonBox QPushButton {{
    min-width: 76px;
}}
"""


def _activate_palette(theme: str) -> None:
    global C, THEME_QSS, LOG_COLORS, HTTP_LOG_COLORS, _current_theme
    _current_theme = theme if theme in PALETTES else "dark"
    C.clear()
    C.update(PALETTES[_current_theme])
    THEME_QSS = build_theme_qss(C)
    # 日志/代码区均为深色底，语义色固定用亮色系，避免浅色主题正文色渗入
    LOG_COLORS.clear()
    LOG_COLORS.update({
        "ERROR": "#f48771",
        "WARNING": "#dcdcaa",
        "INFO": C["code_fg"],
    })
    HTTP_LOG_COLORS.clear()
    HTTP_LOG_COLORS.update({"request": C.get("ok", "#7a9a78"), "response": C.get("accent", "#8a9aab")})


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
    """variant: default | primary | danger | danger_fill | accent | warn | ghost"""
    btn.setProperty("variant", "" if variant == "default" else variant)
    _repolish(btn)


def style_muted_label(label: QLabel) -> None:
    label.setProperty("muted", True)
    _repolish(label)


def style_status_label(label: QLabel, running: bool = False) -> None:
    label.setProperty("status", "running" if running else "stopped")
    _repolish(label)


def setup_code_editor(widget) -> None:
    """标记为代码编辑器并挂语法高亮；配色走全局 QSS，随主题切换。"""
    widget.setObjectName("codeEditor")
    # 勿写死内联样式，否则切主题后背景/字色不会更新
    widget.setStyleSheet("")
    from core.syntax_highlighter import attach_python_highlighter
    attach_python_highlighter(widget)


def setup_mono_field(widget) -> None:
    """密文/明文等等宽输入区，随主题切换，不加语法高亮。"""
    widget.setObjectName("monoField")
    widget.setStyleSheet("")


def setup_sub_tabs(tab_widget) -> None:
    """设置内页等二级 Tab，样式对齐主 Tab 下划线风格。"""
    from PyQt6.QtCore import QSize
    tab_widget.setObjectName("subTabs")
    tab_widget.setDocumentMode(True)
    tab_widget.setMovable(False)
    tab_widget.setIconSize(QSize(16, 16))
    bar = tab_widget.tabBar()
    bar.setExpanding(False)
    bar.setUsesScrollButtons(True)
    bar.setDrawBase(False)
    bar.setElideMode(Qt.TextElideMode.ElideRight)
    repolish_widget(tab_widget)


def build_logo_header(parent_layout, icon_path: str | None = None) -> None:
    """侧边栏品牌区 — 图标 + 名称一行，不搞徽章堆砌."""
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QPixmap
    from PyQt6.QtWidgets import QFrame, QHBoxLayout, QVBoxLayout, QLabel
    from core.icon_loader import MAIN_ICON
    from core.brand import (
        APP_NAME, APP_NAME_EN, APP_SUBTITLE, APP_VERSION,
        APP_CREDIT_AUTHOR, APP_TAGLINE,
    )

    card = QFrame()
    card.setObjectName("sidebarBrandCard")
    repolish_widget(card)

    outer = QVBoxLayout(card)
    outer.setContentsMargins(2, 2, 2, 8)
    outer.setSpacing(4)

    row = QHBoxLayout()
    row.setSpacing(8)
    row.setAlignment(Qt.AlignmentFlag.AlignVCenter)

    logo = QLabel()
    logo.setObjectName("sidebarBrandLogo")
    logo.setFixedSize(28, 28)
    logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
    img = icon_path or MAIN_ICON
    if img:
        pm = QPixmap(img).scaled(
            28, 28, Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        if not pm.isNull():
            logo.setPixmap(pm)
    row.addWidget(logo)

    text_col = QVBoxLayout()
    text_col.setSpacing(0)
    name_cn = QLabel(f"{APP_NAME}  {APP_NAME_EN}  {APP_VERSION}")
    name_cn.setObjectName("sidebarBrandNameCn")
    text_col.addWidget(name_cn)
    subtitle = QLabel(APP_SUBTITLE)
    subtitle.setObjectName("sidebarBrandSub")
    subtitle.setWordWrap(True)
    text_col.addWidget(subtitle)
    row.addLayout(text_col, 1)
    outer.addLayout(row)

    credit = QLabel(APP_TAGLINE)
    credit.setObjectName("sidebarBrandCreditMuted")
    credit.setWordWrap(True)
    credit.setToolTip(f"作者：{APP_CREDIT_AUTHOR}")
    outer.addWidget(credit)

    parent_layout.addWidget(card)


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


def apply_soft_shadow(
    widget: QWidget,
    *,
    blur: int = 14,
    x: int = 0,
    y: int = 0,
    alpha: int = 45,
) -> None:
    """轻阴影（参考 TrafficEye），透明度低，避免糊成卡片墙."""
    from PyQt6.QtWidgets import QGraphicsDropShadowEffect

    effect = QGraphicsDropShadowEffect(widget)
    effect.setBlurRadius(blur)
    effect.setOffset(x, y)
    effect.setColor(QColor(0, 0, 0, max(0, min(255, alpha))))
    widget.setGraphicsEffect(effect)


def setup_main_tabs(tab_widget) -> None:
    """主界面 Tab — 主色底线选中，侧栏同高条。"""
    from PyQt6.QtCore import QSize
    tab_widget.setObjectName("mainTabs")
    tab_widget.setIconSize(QSize(16, 16))
    tab_widget.setDocumentMode(True)
    tab_widget.setMovable(False)
    bar = tab_widget.tabBar()
    bar.setExpanding(False)
    bar.setUsesScrollButtons(True)
    bar.setDrawBase(False)
    bar.setElideMode(Qt.TextElideMode.ElideRight)
    bar.setIconSize(QSize(16, 16))
    repolish_widget(tab_widget)


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
    p.setColor(QPalette.ColorRole.ToolTipBase, QColor(C["surface2"]))
    p.setColor(QPalette.ColorRole.ToolTipText, QColor(C["text"]))
    for group in (
        QPalette.ColorGroup.Active,
        QPalette.ColorGroup.Inactive,
        QPalette.ColorGroup.Disabled,
    ):
        p.setColor(group, QPalette.ColorRole.ToolTipBase, QColor(C["surface2"]))
        p.setColor(group, QPalette.ColorRole.ToolTipText, QColor(C["text"]))
        p.setColor(group, QPalette.ColorRole.WindowText, QColor(C["text"]))
        p.setColor(group, QPalette.ColorRole.Text, QColor(C["text"]))
    app.setPalette(p)
    try:
        from core.syntax_highlighter import refresh_all_highlighters
        refresh_all_highlighters()
    except ImportError:
        pass
    return name
