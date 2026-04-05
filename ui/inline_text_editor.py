"""
ui/inline_text_editor.py
인라인 텍스트 에디터 — 캔버스 드래그 영역에 직접 올라오는 편집기.
서식 바(위 또는 아래)와 텍스트 입력 영역으로 구성되며, 실시간으로 서식이 반영됩니다.
"""
from PyQt6.QtWidgets import (
    QWidget, QFrame, QHBoxLayout, QPushButton,
    QFontComboBox, QSpinBox, QTextEdit, QColorDialog, QSizePolicy,
)
from PyQt6.QtCore import Qt, pyqtSignal, QRect, QPoint
from PyQt6.QtGui import (
    QColor, QFont, QTextCharFormat, QTextCursor,
    QKeySequence, QShortcut,
)


# ------------------------------------------------------------------ #
#  서식 바
# ------------------------------------------------------------------ #
class _FormatBar(QFrame):
    """드래그 영역 위/아래에 표시되는 수평 서식 미니 툴바."""

    sig_format_changed = pyqtSignal()   # 서식 변경 → 텍스트 에디터에 즉시 반영
    sig_committed      = pyqtSignal()
    sig_cancelled      = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            _FormatBar, QFrame#formatBar {
                background-color: #1e1e2e;
                border: 1px solid #45475a;
                border-radius: 6px;
            }
        """)
        self.setObjectName("formatBar")

        self._color: tuple = (255, 255, 255, 255)
        self._align: str   = "left"

        row = QHBoxLayout(self)
        row.setContentsMargins(6, 2, 6, 2)
        row.setSpacing(3)

        # 폰트
        self._font_combo = QFontComboBox()
        self._font_combo.setCurrentFont(QFont("맑은 고딕"))
        self._font_combo.setFixedWidth(140)
        self._font_combo.setToolTip("폰트")
        self._font_combo.setStyleSheet(self._combo_style())
        self._font_combo.currentFontChanged.connect(self._emit_change)
        row.addWidget(self._font_combo)

        # 크기
        self._spin_size = QSpinBox()
        self._spin_size.setRange(6, 500)
        self._spin_size.setValue(12)
        self._spin_size.setFixedWidth(52)
        self._spin_size.setToolTip("글자 크기")
        self._spin_size.setStyleSheet(self._spin_style())
        self._spin_size.valueChanged.connect(self._emit_change)
        row.addWidget(self._spin_size)

        row.addWidget(self._sep())

        # B / I / U
        self._btn_bold      = self._toggle("B", "굵게 (Bold)")
        self._btn_italic    = self._toggle("I", "기울임 (Italic)")
        self._btn_underline = self._toggle("U", "밑줄 (Underline)")

        fb = self._btn_bold.font();      fb.setBold(True);      self._btn_bold.setFont(fb)
        fi = self._btn_italic.font();    fi.setItalic(True);    self._btn_italic.setFont(fi)
        fu = self._btn_underline.font(); fu.setUnderline(True); self._btn_underline.setFont(fu)

        for b in (self._btn_bold, self._btn_italic, self._btn_underline):
            b.toggled.connect(self._emit_change)
            row.addWidget(b)

        row.addWidget(self._sep())

        # 색상
        self._btn_color = QPushButton()
        self._btn_color.setFixedSize(26, 26)
        self._btn_color.setToolTip("글자 색상")
        self._btn_color.clicked.connect(self._pick_color)
        self._refresh_color()
        row.addWidget(self._btn_color)

        row.addWidget(self._sep())

        # 정렬
        self._btn_al = self._toggle("≡L", "왼쪽 정렬")
        self._btn_ac = self._toggle("≡C", "가운데 정렬")
        self._btn_ar = self._toggle("≡R", "오른쪽 정렬")
        self._btn_al.clicked.connect(lambda: self._set_align("left"))
        self._btn_ac.clicked.connect(lambda: self._set_align("center"))
        self._btn_ar.clicked.connect(lambda: self._set_align("right"))
        for b in (self._btn_al, self._btn_ac, self._btn_ar):
            row.addWidget(b)
        self._refresh_align()

        row.addStretch()
        row.addWidget(self._sep())

        # ✓ 삽입
        btn_ok = QPushButton("✓ 삽입")
        btn_ok.setFixedHeight(26)
        btn_ok.setMinimumWidth(52)
        btn_ok.setToolTip("텍스트 삽입 (Ctrl+Enter)")
        btn_ok.setStyleSheet("""
            QPushButton {
                background-color: #89b4fa; color: #1e1e2e;
                border: none; border-radius: 4px;
                font-size: 12px; font-weight: bold;
                padding: 0 8px;
            }
            QPushButton:hover { background-color: #b4befe; }
            QPushButton:pressed { background-color: #7aa2f7; }
        """)
        btn_ok.clicked.connect(self.sig_committed)
        row.addWidget(btn_ok)

        # ✕ 취소
        btn_x = QPushButton("✕")
        btn_x.setFixedSize(24, 24)
        btn_x.setToolTip("취소 (Esc)")
        btn_x.setStyleSheet("""
            QPushButton {
                background: transparent; color: #6c7086;
                border: none; font-size: 12px; font-weight: bold;
            }
            QPushButton:hover { color: #f38ba8; }
        """)
        btn_x.clicked.connect(self.sig_cancelled)
        row.addWidget(btn_x)

    # ──────────────────────────────────────────── 공개 API ──
    def load_settings(self, s: dict):
        self._font_combo.blockSignals(True)
        self._spin_size.blockSignals(True)
        self._font_combo.setCurrentFont(QFont(s.get("font", "맑은 고딕")))
        self._spin_size.setValue(s.get("size", 12))
        self._btn_bold.setChecked(s.get("bold", False))
        self._btn_italic.setChecked(s.get("italic", False))
        self._btn_underline.setChecked(s.get("underline", False))
        self._color = s.get("color", (255, 255, 255, 255))
        self._refresh_color()
        self._align = s.get("align", "left")
        self._refresh_align()
        self._font_combo.blockSignals(False)
        self._spin_size.blockSignals(False)

    def get_settings(self) -> dict:
        return {
            "font":      self._font_combo.currentFont().family(),
            "size":      self._spin_size.value(),
            "bold":      self._btn_bold.isChecked(),
            "italic":    self._btn_italic.isChecked(),
            "underline": self._btn_underline.isChecked(),
            "color":     self._color,
            "align":     self._align,
        }

    # ──────────────────────────────────────────── 내부 ──────
    def _emit_change(self, *_):
        self.sig_format_changed.emit()

    def _set_align(self, val: str):
        self._align = val
        self._refresh_align()
        self.sig_format_changed.emit()

    def _refresh_align(self):
        self._btn_al.setChecked(self._align == "left")
        self._btn_ac.setChecked(self._align == "center")
        self._btn_ar.setChecked(self._align == "right")

    def _pick_color(self):
        r, g, b, a = self._color
        c = QColorDialog.getColor(QColor(r, g, b), self, "글자 색상 선택")
        if c.isValid():
            self._color = (c.red(), c.green(), c.blue(), 255)
            self._refresh_color()
            self.sig_format_changed.emit()

    def _refresh_color(self):
        r, g, b, _ = self._color
        hx = f"#{r:02x}{g:02x}{b:02x}"
        self._btn_color.setToolTip(f"글자 색상: {hx}")
        self._btn_color.setStyleSheet(f"""
            QPushButton {{
                background-color: {hx};
                border: 2px solid #45475a; border-radius: 4px;
            }}
            QPushButton:hover {{ border: 2px solid #89b4fa; }}
        """)

    def _toggle(self, label: str, tip: str) -> QPushButton:
        btn = QPushButton(label)
        btn.setCheckable(True)
        btn.setToolTip(tip)
        btn.setFixedSize(26, 26)
        btn.setStyleSheet("""
            QPushButton {
                background-color: #313244; color: #cdd6f4;
                border: 1px solid #45475a; border-radius: 4px;
                font-size: 12px;
            }
            QPushButton:hover { background-color: #45475a; }
            QPushButton:checked {
                background-color: #89b4fa; color: #1e1e2e;
                border: 1px solid #89b4fa;
            }
        """)
        return btn

    @staticmethod
    def _sep() -> QFrame:
        f = QFrame()
        f.setFrameShape(QFrame.Shape.VLine)
        f.setFixedHeight(20)
        f.setStyleSheet("color: #45475a; margin: 0 1px;")
        return f

    @staticmethod
    def _combo_style() -> str:
        return """
            QFontComboBox {
                background-color: #313244; color: #cdd6f4;
                border: 1px solid #45475a; border-radius: 4px; padding: 2px;
            }
            QFontComboBox QAbstractItemView {
                background-color: #313244; color: #cdd6f4;
                selection-background-color: #89b4fa;
            }
        """

    @staticmethod
    def _spin_style() -> str:
        return ("background:#313244; color:#cdd6f4; border:1px solid #45475a;"
                "border-radius:4px; padding:2px;")


# ------------------------------------------------------------------ #
#  인라인 텍스트 에디터
# ------------------------------------------------------------------ #
class InlineTextEditor(QWidget):
    """
    캔버스 위에 직접 올라오는 인라인 텍스트 에디터.
    드래그한 rect 위치에 QTextEdit가 표시되고, 바로 위(또는 아래)에
    서식 바가 붙어 실시간으로 글꼴·크기·굵기 등을 변경할 수 있습니다.
    """

    sig_committed = pyqtSignal(dict)   # {"text", "font", "size", ...}
    sig_cancelled = pyqtSignal()

    _BAR_H  = 36   # 서식 바 높이
    _GAP    = 2    # 서식 바 ↔ 텍스트 영역 간격

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.Widget)
        # 배경을 투명으로 해야 바(bar) 영역만 보임 (서식 바가 전체 너비를 사용)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        # 캔버스 위에 그냥 올라오는 자식 위젯이므로 크기는 show_at_rect에서 설정
        self.hide()

        # 서식 바
        self._bar = _FormatBar(self)
        self._bar.sig_format_changed.connect(self._apply_format)
        self._bar.sig_committed.connect(self._on_commit)
        self._bar.sig_cancelled.connect(self._on_cancel)

        # 텍스트 입력 영역
        self._edit = QTextEdit(self)
        self._edit.setAcceptRichText(False)   # 붙여넣기도 순수 텍스트로
        self._edit.setStyleSheet("""
            QTextEdit {
                background-color: #1a1a2e;
                color: #cdd6f4;
                border: 2px dashed #89b4fa;
                border-radius: 4px;
                padding: 4px;
                selection-background-color: #45475a;
            }
        """)

        # 단축키
        QShortcut(QKeySequence("Escape"),        self, activated=self._on_cancel)
        QShortcut(QKeySequence("Ctrl+Return"),   self, activated=self._on_commit)
        QShortcut(QKeySequence("Ctrl+Enter"),    self, activated=self._on_commit)

    # ------------------------------------------------------------------ #
    #  공개 API
    # ------------------------------------------------------------------ #
    def show_at_rect(self, widget_rect: QRect, prev_settings: dict | None = None,
                     initial_text: str = ""):
        """
        canvas 위젯 좌표 widget_rect에 맞춰 에디터를 배치하고 표시합니다.
        서식 바는 부모(캔버스) 전체 너비로 확장되며, 텍스트 영역 위/아래에 배치됩니다.
        initial_text 가 있으면 텍스트 입력 영역을 그 내용으로 초기화합니다.
        """
        if prev_settings:
            self._bar.load_settings(prev_settings)

        bh  = self._BAR_H
        gap = self._GAP
        rw  = max(widget_rect.width(), 200)
        rh  = max(widget_rect.height(), 40)
        rx, ry = widget_rect.x(), widget_rect.y()

        # 서식 바는 부모(캔버스) 전체 너비로 확장
        parent_w = self.parent().width() if self.parent() else rw
        bar_w = max(parent_w, rw)

        bar_above = ry >= bh + gap + 4

        if bar_above:
            # 서식 바 위 → 텍스트 아래
            self.setGeometry(0, ry - bh - gap, bar_w, rh + bh + gap)
            self._bar.setGeometry(0, 0, bar_w, bh)
            self._edit.setGeometry(rx, bh + gap, rw, rh)
        else:
            # 서식 바 아래 → 텍스트 위
            self.setGeometry(0, ry, bar_w, rh + bh + gap)
            self._edit.setGeometry(rx, 0, rw, rh)
            self._bar.setGeometry(0, rh + gap, bar_w, bh)

        # 서식 적용 후 에디터 초기화
        self._edit.clear()
        if initial_text:
            self._edit.setPlainText(initial_text)
        self._apply_format()

        self.raise_()
        self.show()
        self._edit.setFocus()

    def get_settings(self) -> dict:
        s = self._bar.get_settings()
        s["text"] = self._edit.toPlainText()
        return s

    def commit(self):
        """외부(canvas)에서 바깥 클릭 감지 후 확정 트리거."""
        self._on_commit()

    # ------------------------------------------------------------------ #
    #  내부 슬롯
    # ------------------------------------------------------------------ #
    def _apply_format(self):
        """서식 바 변경사항을 QTextEdit 전체 텍스트에 실시간 반영."""
        s   = self._bar.get_settings()
        fmt = QTextCharFormat()
        fmt.setFontFamily(s["font"])
        fmt.setFontPointSize(float(s["size"]))
        weight = QFont.Weight.Bold if s["bold"] else QFont.Weight.Normal
        fmt.setFontWeight(weight)
        fmt.setFontItalic(s["italic"])
        fmt.setFontUnderline(s["underline"])
        r, g, b, a = s["color"]
        fmt.setForeground(QColor(r, g, b, a))

        # 정렬 적용
        align_map = {
            "left":   Qt.AlignmentFlag.AlignLeft,
            "center": Qt.AlignmentFlag.AlignCenter,
            "right":  Qt.AlignmentFlag.AlignRight,
        }
        block_fmt = self._edit.textCursor().blockFormat()
        block_fmt.setAlignment(align_map.get(s["align"], Qt.AlignmentFlag.AlignLeft))

        # 전체 텍스트에 서식 적용 (커서 위치 보존)
        saved = self._edit.textCursor().position()
        cursor = self._edit.textCursor()
        cursor.select(QTextCursor.SelectionType.Document)
        cursor.setCharFormat(fmt)
        cursor.setBlockFormat(block_fmt)
        cursor.clearSelection()
        cursor.setPosition(min(saved, cursor.document().characterCount() - 1))
        self._edit.setTextCursor(cursor)

        # 이후 입력될 글자도 같은 서식 적용
        self._edit.setCurrentCharFormat(fmt)

    def _on_commit(self):
        settings = self.get_settings()
        self.hide()
        self.sig_committed.emit(settings)

    def _on_cancel(self):
        self.hide()
        self.sig_cancelled.emit()
