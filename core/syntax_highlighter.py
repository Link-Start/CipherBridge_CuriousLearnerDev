"""Python 语法高亮 — 跟随亮/暗主题切换配色."""

from __future__ import annotations

from PyQt6.QtCore import QRegularExpression
from PyQt6.QtGui import QColor, QFont, QSyntaxHighlighter, QTextCharFormat

# VS Code Dark+
_DARK_COLORS = {
    "text": "#D4D4D4",
    "comment": "#6A9955",
    "keyword": "#569CD6",
    "string": "#CE9178",
    "number": "#B5CEA8",
    "function": "#DCDCAA",
    "class_name": "#4EC9B0",
    "decorator": "#DCDCAA",
    "builtin": "#569CD6",
    "self": "#9CDCFE",
}

# 浅色代码底备用（GitHub Light）；浅色 UI 默认深色代码区时走 Dark+
_LIGHT_COLORS = {
    "text": "#1f2328",
    "comment": "#656d76",
    "keyword": "#cf222e",
    "string": "#0a3069",
    "number": "#0550ae",
    "function": "#8250df",
    "class_name": "#116329",
    "decorator": "#8250df",
    "builtin": "#cf222e",
    "self": "#953800",
}


def _hex_luminance(hex_color: str) -> float:
    h = hex_color.lstrip("#")
    if len(h) != 6:
        return 1.0
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return (0.299 * r + 0.587 * g + 0.114 * b) / 255.0


def colors_for_theme(theme: str | None = None) -> dict[str, str]:
    """按代码区背景明暗选高亮色（浅色 UI + 深色代码区 → Dark+）。"""
    code_bg = None
    if theme is None:
        try:
            from core.theme import current_theme, C
            theme = current_theme()
            code_bg = C.get("code_bg")
        except Exception:
            theme = "dark"
    if code_bg is None:
        try:
            from core.theme import PALETTES
            code_bg = PALETTES.get(theme or "dark", {}).get("code_bg", "#15181d")
        except Exception:
            code_bg = "#15181d"
    if _hex_luminance(str(code_bg)) < 0.45:
        return _DARK_COLORS
    return _LIGHT_COLORS


_KEYWORDS = (
    "and as assert async await break class continue def del elif else except "
    "finally for from global if import in is lambda nonlocal not or pass raise "
    "return try while with yield"
).split()

_BUILTINS = (
    "False None True Ellipsis NotImplemented "
    "print len str int float bool list dict set tuple range type super "
    "isinstance getattr setattr hasattr open enumerate zip map filter "
    "Exception ValueError TypeError KeyError IndexError RuntimeError"
).split()


def _fmt(color: str, *, bold: bool = False, italic: bool = False) -> QTextCharFormat:
    f = QTextCharFormat()
    f.setForeground(QColor(color))
    if bold:
        f.setFontWeight(QFont.Weight.Bold)
    if italic:
        f.setFontItalic(True)
    return f


class PythonHighlighter(QSyntaxHighlighter):
    """QPlainTextEdit / QTextEdit 通用 Python 高亮."""

    def __init__(self, document, theme: str | None = None) -> None:
        super().__init__(document)
        self._theme = theme
        self._comment_start = QRegularExpression(r"#")
        self._tri_single_start = QRegularExpression(r"'''")
        self._tri_single_end = QRegularExpression(r"'''")
        self._tri_double_start = QRegularExpression(r'"""')
        self._tri_double_end = QRegularExpression(r'"""')
        self._single_quote = QRegularExpression(r"'[^'\\]*(\\.[^'\\]*)*'")
        self._double_quote = QRegularExpression(r'"[^"\\]*(\\.[^"\\]*)*"')
        self.apply_theme(theme)

    def apply_theme(self, theme: str | None = None) -> None:
        self._theme = theme
        colors = colors_for_theme(theme)
        self._rules: list[tuple[QRegularExpression, QTextCharFormat]] = []

        kw = _fmt(colors["keyword"], bold=True)
        for word in _KEYWORDS:
            self._rules.append((QRegularExpression(rf"\b{word}\b"), kw))

        bi = _fmt(colors["builtin"])
        for word in _BUILTINS:
            self._rules.append((QRegularExpression(rf"\b{word}\b"), bi))

        self._rules.append((QRegularExpression(r"\bself\b"), _fmt(colors["self"])))
        self._rules.append((QRegularExpression(r"@[\w.]+"), _fmt(colors["decorator"])))
        self._rules.append((QRegularExpression(r"(?<=def )\w+"), _fmt(colors["function"])))
        self._rules.append((QRegularExpression(r"(?<=class )\w+"), _fmt(colors["class_name"])))
        self._rules.append(
            (QRegularExpression(r"\b\d+\.?\d*([eE][+-]?\d+)?\b"), _fmt(colors["number"]))
        )

        self._text = _fmt(colors["text"])
        self._comment = _fmt(colors["comment"], italic=True)
        self._string = _fmt(colors["string"])
        self.rehighlight()

    def highlightBlock(self, text: str) -> None:
        self.setFormat(0, len(text), self._text)

        cm = self._comment_start.match(text)
        if cm.hasMatch():
            self.setFormat(cm.capturedStart(), len(text) - cm.capturedStart(), self._comment)

        self.setCurrentBlockState(0)
        start = 0
        if self.previousBlockState() == 1:
            end_expr = self._tri_single_end
        elif self.previousBlockState() == 2:
            end_expr = self._tri_double_end
        else:
            end_expr = None

        if end_expr is not None:
            m = end_expr.match(text, 0)
            if m.hasMatch():
                self.setFormat(0, m.capturedEnd(), self._string)
                start = m.capturedEnd()
            else:
                self.setFormat(0, len(text), self._string)
                self.setCurrentBlockState(self.previousBlockState())
                return

        while start < len(text):
            ts = self._tri_single_start.match(text, start)
            td = self._tri_double_start.match(text, start)
            if ts.hasMatch() and (not td.hasMatch() or ts.capturedStart() <= td.capturedStart()):
                end = self._tri_single_end.match(text, ts.capturedEnd())
                if end.hasMatch():
                    length = end.capturedEnd() - ts.capturedStart()
                    self.setFormat(ts.capturedStart(), length, self._string)
                    start = ts.capturedStart() + length
                else:
                    self.setFormat(ts.capturedStart(), len(text) - ts.capturedStart(), self._string)
                    self.setCurrentBlockState(1)
                    return
            elif td.hasMatch():
                end = self._tri_double_end.match(text, td.capturedEnd())
                if end.hasMatch():
                    length = end.capturedEnd() - td.capturedStart()
                    self.setFormat(td.capturedStart(), length, self._string)
                    start = td.capturedStart() + length
                else:
                    self.setFormat(td.capturedStart(), len(text) - td.capturedStart(), self._string)
                    self.setCurrentBlockState(2)
                    return
            else:
                break

        for expr in (self._double_quote, self._single_quote):
            it = expr.globalMatch(text, start)
            while it.hasNext():
                m = it.next()
                if cm.hasMatch() and m.capturedStart() >= cm.capturedStart():
                    continue
                self.setFormat(m.capturedStart(), m.capturedLength(), self._string)

        comment_at = cm.capturedStart() if cm.hasMatch() else len(text)
        for pattern, fmt in self._rules:
            it = pattern.globalMatch(text)
            while it.hasNext():
                m = it.next()
                if m.capturedStart() >= comment_at:
                    continue
                self.setFormat(m.capturedStart(), m.capturedLength(), fmt)


def attach_python_highlighter(widget) -> PythonHighlighter:
    """给编辑器挂上高亮，返回 highlighter 实例（需保持引用）."""
    from core.theme import current_theme

    existing = getattr(widget, "_python_highlighter", None)
    theme = current_theme()
    if existing is not None:
        existing.apply_theme(theme)
        return existing
    hl = PythonHighlighter(widget.document(), theme=theme)
    widget._python_highlighter = hl
    return hl


def refresh_all_highlighters(root=None) -> None:
    """主题切换后刷新已挂载的语法高亮."""
    from PyQt6.QtWidgets import QApplication, QWidget
    from core.theme import current_theme

    theme = current_theme()
    app = QApplication.instance()
    if app is None:
        return
    widgets = [root] if root is not None else []
    if root is not None and isinstance(root, QWidget):
        widgets.extend(root.findChildren(QWidget))
    else:
        for w in app.topLevelWidgets():
            widgets.append(w)
            widgets.extend(w.findChildren(QWidget))
    seen: set[int] = set()
    for w in widgets:
        hl = getattr(w, "_python_highlighter", None)
        if hl is None:
            continue
        hid = id(hl)
        if hid in seen:
            continue
        seen.add(hid)
        hl.apply_theme(theme)
