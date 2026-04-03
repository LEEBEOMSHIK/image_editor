"""
ui/text_toolbar.py
텍스트 삽입용 수평 떠있는 툴바 — 드래그 가능한 캔버스 오버레이 위젯
"""
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QLabel, QPushButton,
    QFontComboBox, QSpinBox, QLineEdit, QColorDialog,
    QFrame, QSizePolicy,
)
from PyQt6.QtCore import Qt, pyqtSignal, QPoint
from PyQt6.QtGui import QColor, QFont


class _DragHandle(QLabel):
    def __init__(self, panel: "TextToolBar"):
        super().__init__("⠿", panel)
        self._panel = panel
        self._drag_pos: QPoint | None = None
        self.setFixedWidth(18)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setCursor(Qt.CursorShape.SizeAllCursor)
        self.setStyleSheet("color: #6c7086; font-size: 12px; background: transparent;")

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = (
                event.globalPosition().toPoint()
                - self._panel.mapToGlobal(QPoint(0, 0))
            )
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_pos and event.buttons() == Qt.MouseButton.LeftButton:
            new_global = event.globalPosition().toPoint() - self._drag_pos
            parent = self._panel.parent()
            new_pos = parent.mapFromGlobal(new_global) if parent else new_global
            self._panel.move(new_pos)
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
        super().mouseReleaseEvent(event)


class TextToolBar(QWidget):
    """
    텍스트 삽입용 수평 떠있는 퀵 툴바.
    캔버스에서 텍스트 영역을 드래그한 뒤 상단에 표시됩니다.
    폰트·크기·굵기·기울임·밑줄·색상·정렬·텍스트 입력을 한 줄로 처리합니다.
    """

    sig_insert    = pyqtSignal(dict)   # 서식 설정 dict — 삽입 확정 시
    sig_cancelled = pyqtSignal()       # 취소(X) 버튼 시

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setWindowFlags(Qt.WindowType.Widget)
        self.setStyleSheet("""
            TextToolBar {
                background-color: #18182d;
                border: 1px solid #45475a;
                border-radius: 8px;
            }
        """)

        self._color: tuple = (255, 255, 255, 255)
        self._align: str   = "left"

        self._build_ui()
        self.hide()

    # ------------------------------------------------------------------ #
    #  UI 구성
    # ------------------------------------------------------------------ #
    def _build_ui(self):
        row = QHBoxLayout(self)
        row.setContentsMargins(6, 4, 6, 4)
        row.setSpacing(4)

        # ── 드래그 핸들 ──────────────────────────────────────
        row.addWidget(_DragHandle(self))
        row.addWidget(self._sep())

        # ── 폰트 선택 ────────────────────────────────────────
        self._font_combo = QFontComboBox()
        self._font_combo.setCurrentFont(QFont("맑은 고딕"))
        self._font_combo.setFixedWidth(148)
        self._font_combo.setToolTip("폰트 선택")
        self._font_combo.setStyleSheet("""
            QFontComboBox {
                background-color: #313244; color: #cdd6f4;
                border: 1px solid #45475a; border-radius: 4px;
                padding: 3px;
            }
            QFontComboBox QAbstractItemView {
                background-color: #313244; color: #cdd6f4;
                selection-background-color: #89b4fa;
            }
        """)
        row.addWidget(self._font_combo)

        # ── 크기 ─────────────────────────────────────────────
        self._spin_size = QSpinBox()
        self._spin_size.setRange(6, 500)
        self._spin_size.setValue(36)
        self._spin_size.setFixedWidth(55)
        self._spin_size.setToolTip("글자 크기")
        self._spin_size.setStyleSheet(
            "background:#313244; color:#cdd6f4; border:1px solid #45475a;"
            "border-radius:4px; padding:2px;"
        )
        row.addWidget(self._spin_size)
        row.addWidget(self._sep())

        # ── 굵게 / 기울임 / 밑줄 ─────────────────────────────
        self._btn_bold = self._toggle_btn("B", "굵게 (Bold)")
        fb = self._btn_bold.font(); fb.setBold(True); self._btn_bold.setFont(fb)

        self._btn_italic = self._toggle_btn("I", "기울임 (Italic)")
        fi = self._btn_italic.font(); fi.setItalic(True); self._btn_italic.setFont(fi)

        self._btn_underline = self._toggle_btn("U", "밑줄 (Underline)")
        fu = self._btn_underline.font(); fu.setUnderline(True); self._btn_underline.setFont(fu)

        for btn in (self._btn_bold, self._btn_italic, self._btn_underline):
            row.addWidget(btn)
        row.addWidget(self._sep())

        # ── 색상 ─────────────────────────────────────────────
        self._btn_color = QPushButton()
        self._btn_color.setFixedSize(28, 28)
        self._btn_color.setToolTip("글자 색상 선택")
        self._btn_color.clicked.connect(self._pick_color)
        self._refresh_color_btn()
        row.addWidget(self._btn_color)
        row.addWidget(self._sep())

        # ── 정렬 ─────────────────────────────────────────────
        self._btn_al = self._toggle_btn("≡L", "왼쪽 정렬")
        self._btn_ac = self._toggle_btn("≡C", "가운데 정렬")
        self._btn_ar = self._toggle_btn("≡R", "오른쪽 정렬")
        self._btn_al.clicked.connect(lambda: self._set_align("left"))
        self._btn_ac.clicked.connect(lambda: self._set_align("center"))
        self._btn_ar.clicked.connect(lambda: self._set_align("right"))
        for btn in (self._btn_al, self._btn_ac, self._btn_ar):
            row.addWidget(btn)
        self._refresh_align()
        row.addWidget(self._sep())

        # ── 텍스트 입력 ──────────────────────────────────────
        self._text_input = QLineEdit()
        self._text_input.setPlaceholderText("텍스트 입력 후 Enter 또는 삽입 클릭...")
        self._text_input.setMinimumWidth(180)
        self._text_input.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self._text_input.setStyleSheet("""
            QLineEdit {
                background-color: #313244; color: #cdd6f4;
                border: 1px solid #45475a; border-radius: 4px;
                padding: 4px 8px; font-size: 13px;
            }
            QLineEdit:focus { border: 1px solid #89b4fa; }
        """)
        self._text_input.returnPressed.connect(self._on_insert)
        row.addWidget(self._text_input, 1)
        row.addWidget(self._sep())

        # ── 삽입 버튼 ────────────────────────────────────────
        btn_ins = QPushButton("삽입")
        btn_ins.setFixedHeight(28)
        btn_ins.setMinimumWidth(48)
        btn_ins.setToolTip("텍스트 삽입 (Enter)")
        btn_ins.setStyleSheet("""
            QPushButton {
                background-color: #89b4fa; color: #1e1e2e;
                border: none; border-radius: 4px;
                font-size: 12px; font-weight: bold;
                padding: 0 10px;
            }
            QPushButton:hover { background-color: #b4befe; }
            QPushButton:pressed { background-color: #7aa2f7; }
        """)
        btn_ins.clicked.connect(self._on_insert)
        row.addWidget(btn_ins)

        # ── 닫기 버튼 ────────────────────────────────────────
        btn_close = QPushButton("✕")
        btn_close.setFixedSize(24, 24)
        btn_close.setToolTip("취소")
        btn_close.setStyleSheet("""
            QPushButton {
                background: transparent; color: #6c7086;
                border: none; font-size: 12px; font-weight: bold;
            }
            QPushButton:hover { color: #f38ba8; }
        """)
        btn_close.clicked.connect(self._on_cancel)
        row.addWidget(btn_close)

    # ------------------------------------------------------------------ #
    #  외부 API
    # ------------------------------------------------------------------ #
    def load_settings(self, settings: dict):
        """이전 서식 설정을 복원합니다. 텍스트 입력란은 항상 초기화합니다."""
        self._font_combo.setCurrentFont(QFont(settings.get("font", "맑은 고딕")))
        self._spin_size.setValue(settings.get("size", 36))
        self._btn_bold.setChecked(settings.get("bold", False))
        self._btn_italic.setChecked(settings.get("italic", False))
        self._btn_underline.setChecked(settings.get("underline", False))
        self._color = settings.get("color", (255, 255, 255, 255))
        self._refresh_color_btn()
        self._align = settings.get("align", "left")
        self._refresh_align()
        self._text_input.clear()

    def get_settings(self) -> dict:
        return {
            "text":      self._text_input.text(),
            "font":      self._font_combo.currentFont().family(),
            "size":      self._spin_size.value(),
            "bold":      self._btn_bold.isChecked(),
            "italic":    self._btn_italic.isChecked(),
            "underline": self._btn_underline.isChecked(),
            "color":     self._color,
            "align":     self._align,
        }

    def show_toolbar(self, canvas_widget: QWidget):
        """캔버스 상단에 맞춰 툴바를 표시합니다."""
        cvs_pos  = canvas_widget.pos()
        cvs_w    = canvas_widget.width()
        margin   = 8
        target_w = max(600, cvs_w - margin * 2)
        h = self.sizeHint().height() or 40
        self.setGeometry(cvs_pos.x() + margin, cvs_pos.y() + margin, target_w, h)
        self.raise_()
        self.show()
        self._text_input.setFocus()
        self._text_input.selectAll()

    # ------------------------------------------------------------------ #
    #  내부 슬롯
    # ------------------------------------------------------------------ #
    def _on_insert(self):
        settings = self.get_settings()
        self.hide()
        self.sig_insert.emit(settings)

    def _on_cancel(self):
        self.hide()
        self.sig_cancelled.emit()

    def _set_align(self, val: str):
        self._align = val
        self._refresh_align()

    def _refresh_align(self):
        self._btn_al.setChecked(self._align == "left")
        self._btn_ac.setChecked(self._align == "center")
        self._btn_ar.setChecked(self._align == "right")

    def _pick_color(self):
        r, g, b, a = self._color
        color = QColorDialog.getColor(QColor(r, g, b), self, "글자 색상 선택")
        if color.isValid():
            self._color = (color.red(), color.green(), color.blue(), 255)
            self._refresh_color_btn()

    def _refresh_color_btn(self):
        r, g, b, _ = self._color
        hex_str = f"#{r:02x}{g:02x}{b:02x}"
        self._btn_color.setToolTip(f"글자 색상: {hex_str}")
        self._btn_color.setStyleSheet(f"""
            QPushButton {{
                background-color: {hex_str};
                border: 2px solid #45475a;
                border-radius: 4px;
            }}
            QPushButton:hover {{ border: 2px solid #89b4fa; }}
        """)

    def _toggle_btn(self, label: str, tooltip: str) -> QPushButton:
        btn = QPushButton(label)
        btn.setCheckable(True)
        btn.setToolTip(tooltip)
        btn.setFixedSize(28, 28)
        btn.setStyleSheet("""
            QPushButton {
                background-color: #313244; color: #cdd6f4;
                border: 1px solid #45475a; border-radius: 4px;
                font-size: 13px;
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
        line = QFrame()
        line.setFrameShape(QFrame.Shape.VLine)
        line.setFixedHeight(24)
        line.setStyleSheet("color: #45475a; margin: 0 2px;")
        return line
