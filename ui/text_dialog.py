"""
ui/text_dialog.py
텍스트 삽입 다이얼로그 — 폰트·크기·굵기·기울임·밑줄·색상·정렬 설정
"""
import os
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QFontComboBox, QSpinBox, QPushButton, QTextEdit,
    QDialogButtonBox, QColorDialog, QWidget, QFrame,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont, QTextOption


class TextDialog(QDialog):
    """텍스트 서식 및 내용 입력 다이얼로그."""

    def __init__(self, parent=None, prev_settings: dict | None = None):
        super().__init__(parent)
        self.setWindowTitle("텍스트 삽입")
        self.setMinimumWidth(460)
        self.setStyleSheet("""
            QDialog { background-color: #1e1e2e; color: #cdd6f4; }
            QLabel  { color: #cdd6f4; font-size: 12px; }
        """)

        # 기본값 (이전 설정 유지)
        d = prev_settings or {}
        self._color: tuple = d.get("color", (255, 255, 255, 255))
        self._align: str   = d.get("align", "left")

        main = QVBoxLayout(self)
        main.setSpacing(10)
        main.setContentsMargins(14, 14, 14, 14)

        # ── 폰트 행 ──────────────────────────────────────────
        font_row = QHBoxLayout()
        font_row.addWidget(QLabel("폰트:"))

        self._font_combo = QFontComboBox()
        self._font_combo.setCurrentFont(QFont(d.get("font", "맑은 고딕")))
        self._font_combo.setStyleSheet(self._combo_style())
        self._font_combo.setFixedWidth(180)
        font_row.addWidget(self._font_combo)

        font_row.addSpacing(8)
        font_row.addWidget(QLabel("크기:"))
        self._spin_size = QSpinBox()
        self._spin_size.setRange(6, 500)
        self._spin_size.setValue(d.get("size", 36))
        self._spin_size.setStyleSheet(self._spin_style())
        self._spin_size.setFixedWidth(60)
        font_row.addWidget(self._spin_size)
        font_row.addStretch()
        main.addLayout(font_row)

        # ── 서식 버튼 행 ──────────────────────────────────────
        fmt_row = QHBoxLayout()
        self._btn_bold      = self._fmt_btn("가", "굵게 (Bold)",      d.get("bold", False))
        self._btn_italic    = self._fmt_btn("가", "기울임 (Italic)",   d.get("italic", False))
        self._btn_underline = self._fmt_btn("가", "밑줄 (Underline)", d.get("underline", False))
        # 굵게 버튼 폰트 강조
        f = self._btn_bold.font(); f.setBold(True); self._btn_bold.setFont(f)
        # 기울임 버튼 폰트
        fi = self._btn_italic.font(); fi.setItalic(True); self._btn_italic.setFont(fi)
        # 밑줄 버튼 폰트
        fu = self._btn_underline.font(); fu.setUnderline(True); self._btn_underline.setFont(fu)

        fmt_row.addWidget(self._btn_bold)
        fmt_row.addWidget(self._btn_italic)
        fmt_row.addWidget(self._btn_underline)
        fmt_row.addSpacing(12)
        fmt_row.addWidget(self._separator_v())
        fmt_row.addSpacing(12)

        # 색상 버튼
        self._btn_color = QPushButton()
        self._btn_color.setFixedSize(36, 36)
        self._btn_color.setToolTip("글자 색상 선택")
        self._btn_color.clicked.connect(self._pick_color)
        self._refresh_color_btn()
        fmt_row.addWidget(self._btn_color)

        fmt_row.addSpacing(12)
        fmt_row.addWidget(self._separator_v())
        fmt_row.addSpacing(12)

        # 정렬 버튼
        self._btn_align_left   = self._align_btn("≡", "왼쪽 정렬",   "left")
        self._btn_align_center = self._align_btn("≡", "가운데 정렬", "center")
        self._btn_align_right  = self._align_btn("≡", "오른쪽 정렬", "right")
        self._btn_align_left.setText("  ≡")   # 왼쪽 아이콘 구분
        fmt_row.addWidget(self._btn_align_left)
        fmt_row.addWidget(self._btn_align_center)
        fmt_row.addWidget(self._btn_align_right)
        fmt_row.addStretch()
        main.addLayout(fmt_row)
        self._refresh_align_buttons()

        # ── 구분선 ───────────────────────────────────────────
        main.addWidget(self._separator_h())

        # ── 텍스트 입력 ──────────────────────────────────────
        main.addWidget(QLabel("텍스트 내용:"))
        self._text_edit = QTextEdit()
        self._text_edit.setPlainText(d.get("text", ""))
        self._text_edit.setMinimumHeight(100)
        self._text_edit.setStyleSheet("""
            QTextEdit {
                background-color: #313244;
                color: #cdd6f4;
                border: 1px solid #45475a;
                border-radius: 6px;
                padding: 6px;
                font-size: 14px;
            }
        """)
        main.addWidget(self._text_edit)

        # ── 확인/취소 ─────────────────────────────────────────
        bbox = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        bbox.button(QDialogButtonBox.StandardButton.Ok).setText("삽입")
        bbox.button(QDialogButtonBox.StandardButton.Cancel).setText("취소")
        bbox.setStyleSheet("""
            QPushButton {
                background-color: #89b4fa; color: #1e1e2e;
                border: none; border-radius: 6px;
                padding: 6px 20px; font-size: 12px; font-weight: bold;
            }
            QPushButton:hover { background-color: #b4befe; }
            QPushButton[text="취소"] {
                background-color: #45475a; color: #cdd6f4;
            }
            QPushButton[text="취소"]:hover { background-color: #585b70; }
        """)
        bbox.accepted.connect(self.accept)
        bbox.rejected.connect(self.reject)
        main.addWidget(bbox)

        self._text_edit.setFocus()

    # ------------------------------------------------------------------ #
    #  결과 조회
    # ------------------------------------------------------------------ #
    def get_settings(self) -> dict:
        """다이얼로그 결과 반환."""
        return {
            "text":      self._text_edit.toPlainText(),
            "font":      self._font_combo.currentFont().family(),
            "size":      self._spin_size.value(),
            "bold":      self._btn_bold.isChecked(),
            "italic":    self._btn_italic.isChecked(),
            "underline": self._btn_underline.isChecked(),
            "color":     self._color,
            "align":     self._align,
        }

    # ------------------------------------------------------------------ #
    #  내부 헬퍼
    # ------------------------------------------------------------------ #
    def _fmt_btn(self, label: str, tooltip: str, checked: bool) -> QPushButton:
        btn = QPushButton(label)
        btn.setCheckable(True)
        btn.setChecked(checked)
        btn.setToolTip(tooltip)
        btn.setFixedSize(36, 36)
        btn.setStyleSheet(self._toggle_style())
        return btn

    def _align_btn(self, label: str, tooltip: str, align_val: str) -> QPushButton:
        btn = QPushButton(label)
        btn.setCheckable(True)
        btn.setToolTip(tooltip)
        btn.setFixedSize(36, 36)
        btn.setStyleSheet(self._toggle_style())
        btn.clicked.connect(lambda: self._set_align(align_val))
        return btn

    def _set_align(self, val: str):
        self._align = val
        self._refresh_align_buttons()

    def _refresh_align_buttons(self):
        self._btn_align_left.setChecked(self._align == "left")
        self._btn_align_center.setChecked(self._align == "center")
        self._btn_align_right.setChecked(self._align == "right")

    def _pick_color(self):
        r, g, b, a = self._color
        color = QColorDialog.getColor(QColor(r, g, b), self, "글자 색상 선택")
        if color.isValid():
            self._color = (color.red(), color.green(), color.blue(), 255)
            self._refresh_color_btn()

    def _refresh_color_btn(self):
        r, g, b, _ = self._color
        hex_str = f"#{r:02x}{g:02x}{b:02x}"
        contrast = "#000" if (r + g + b) > 384 else "#fff"
        self._btn_color.setToolTip(f"글자 색상: {hex_str}")
        self._btn_color.setStyleSheet(f"""
            QPushButton {{
                background-color: {hex_str};
                border: 2px solid #45475a;
                border-radius: 6px;
            }}
            QPushButton:hover {{ border: 2px solid #89b4fa; }}
        """)

    @staticmethod
    def _toggle_style() -> str:
        return """
            QPushButton {
                background-color: #313244; color: #cdd6f4;
                border: 1px solid #45475a; border-radius: 6px;
                font-size: 14px;
            }
            QPushButton:hover { background-color: #45475a; }
            QPushButton:checked {
                background-color: #89b4fa; color: #1e1e2e;
                border: 1px solid #89b4fa; font-weight: bold;
            }
        """

    @staticmethod
    def _combo_style() -> str:
        return """
            QFontComboBox {
                background-color: #313244; color: #cdd6f4;
                border: 1px solid #45475a; border-radius: 4px;
                padding: 4px;
            }
            QFontComboBox QAbstractItemView {
                background-color: #313244; color: #cdd6f4;
                selection-background-color: #89b4fa;
            }
        """

    @staticmethod
    def _spin_style() -> str:
        return "background:#313244; color:#cdd6f4; border:1px solid #45475a; border-radius:4px; padding:2px;"

    @staticmethod
    def _separator_h() -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("color: #313244; margin: 2px 0;")
        return line

    @staticmethod
    def _separator_v() -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.Shape.VLine)
        line.setFixedHeight(30)
        line.setStyleSheet("color: #45475a;")
        return line
