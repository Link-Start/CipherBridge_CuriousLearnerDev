"""Python 语法高亮 — VS Code Dark+ 配色."""

from __future__ import annotations

from PyQt6.QtCore import QRegularExpression
from PyQt6.QtGui import QColor, QFont, QSyntaxHighlighter, QTextCharFormat

# VS Code Dark+ 色板
_PY_COLORS = {
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

    def __init__(self, document) -> None:
        super().__init__(document)
        self._rules: list[tuple[QRegularExpression, QTextCharFormat]] = []

        kw = _fmt(_PY_COLORS["keyword"])
        for word in _KEYWORDS:
            self._rules.append((QRegularExpression(rf"\b{word}\b"), kw))

        bi = _fmt(_PY_COLORS["builtin"])
        for word in _BUILTINS:
            self._rules.append((QRegularExpression(rf"\b{word}\b"), bi))

        self._rules.append((QRegularExpression(r"\bself\b"), _fmt(_PY_COLORS["self"])))
        self._rules.append((QRegularExpression(r"@[\w.]+"), _fmt(_PY_COLORS["decorator"])))
        self._rules.append((QRegularExpression(r"(?<=def )\w+"), _fmt(_PY_COLORS["function"])))
        self._rules.append((QRegularExpression(r"(?<=class )\w+"), _fmt(_PY_COLORS["class_name"])))
        self._rules.append((QRegularExpression(r"\b\d+\.?\d*([eE][+-]?\d+)?\b"), _fmt(_PY_COLORS["number"])))

        self._text = _fmt(_PY_COLORS["text"])
        self._comment = _fmt(_PY_COLORS["comment"], italic=True)
        self._string = _fmt(_PY_COLORS["string"])

        self._comment_start = QRegularExpression(r"#")
        self._tri_single_start = QRegularExpression(r"'''")
        self._tri_single_end = QRegularExpression(r"'''")
        self._tri_double_start = QRegularExpression(r'"""')
        self._tri_double_end = QRegularExpression(r'"""')
        self._single_quote = QRegularExpression(r"'[^'\\]*(\\.[^'\\]*)*'")
        self._double_quote = QRegularExpression(r'"[^"\\]*(\\.[^"\\]*)*"')

    def highlightBlock(self, text: str) -> None:
        self.setFormat(0, len(text), self._text)

        # 单行注释
        cm = self._comment_start.match(text)
        if cm.hasMatch():
            self.setFormat(cm.capturedStart(), len(text) - cm.capturedStart(), self._comment)

        # 多行三引号字符串
        self.setCurrentBlockState(0)
        start = 0
        if self.previousBlockState() == 1:
            end_expr = self._tri_single_end
            state_done = 0
        elif self.previousBlockState() == 2:
            end_expr = self._tri_double_end
            state_done = 0
        else:
            end_expr = None
            state_done = 0

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

        # 单行引号字符串（跳过多行区域之后）
        for expr in (self._double_quote, self._single_quote):
            it = expr.globalMatch(text, start)
            while it.hasNext():
                m = it.next()
                if cm.hasMatch() and m.capturedStart() >= cm.capturedStart():
                    continue
                self.setFormat(m.capturedStart(), m.capturedLength(), self._string)

        # 关键字等（跳过注释区域）
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
    existing = getattr(widget, "_python_highlighter", None)
    if existing is not None:
        return existing
    hl = PythonHighlighter(widget.document())
    widget._python_highlighter = hl
    return hl
