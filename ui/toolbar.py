"""
ui/toolbar.py
왼쪽 도구 패널
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QLabel,
    QSlider, QSpinBox, QHBoxLayout, QComboBox, QFrame, QScrollArea
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor


class ToolButton(QPushButton):
    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setCheckable(True)
        self.setMinimumHeight(36)
        self.setStyleSheet("""
            QPushButton {
                background-color: #313244;
                color: #cdd6f4;
                border: 1px solid #45475a;
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 12px;
                text-align: left;
            }
            QPushButton:hover { background-color: #45475a; }
            QPushButton:checked {
                background-color: #89b4fa;
                color: #1e1e2e;
                border: 1px solid #89b4fa;
                font-weight: bold;
            }
        """)


class ActionButton(QPushButton):
    def __init__(self, text: str, color: str = "#89b4fa", parent=None):
        super().__init__(text, parent)
        self.setMinimumHeight(34)
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {color};
                color: #1e1e2e;
                border: none;
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 12px;
                font-weight: bold;
            }}
            QPushButton:hover {{ background-color: #b4befe; }}
            QPushButton:disabled {{
                background-color: #45475a;
                color: #6c7086;
            }}
        """)


class SectionLabel(QLabel):
    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setStyleSheet("""
            color: #a6adc8;
            font-size: 10px;
            font-weight: bold;
            letter-spacing: 1px;
            padding: 8px 0 4px 0;
        """)


class Toolbar(QWidget):
    """왼쪽 도구 패널."""

    # --- 시그널 ---
    sig_open  = pyqtSignal()
    sig_save  = pyqtSignal()

    sig_mode_changed   = pyqtSignal(str)
    sig_remove_bg_auto = pyqtSignal()
    sig_apply_brush    = pyqtSignal()
    sig_clear_brush    = pyqtSignal()
    sig_crop_size_preview = pyqtSignal(int, int)   # 크기 지정 크롭 미리보기 모드

    sig_filter  = pyqtSignal(str)
    sig_reset   = pyqtSignal()
    sig_undo    = pyqtSignal()
    sig_redo    = pyqtSignal()
    sig_help    = pyqtSignal()

    sig_zoom_fit = pyqtSignal()
    sig_zoom_in  = pyqtSignal()
    sig_zoom_out = pyqtSignal()

    sig_color_changed      = pyqtSignal(int, int, int, int)  # r, g, b, a (색상 변경)
    sig_apply_color_brush  = pyqtSignal()
    sig_clear_color_brush  = pyqtSignal()

    sig_text_mode = pyqtSignal()   # 텍스트 삽입 모드 진입

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(210)
        self.setStyleSheet("background-color: #181825; border-right: 1px solid #313244;")

        # 세로 스크롤 가능한 내용 영역
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(
            "QScrollArea { border: none; background: transparent; }"
            "QScrollBar:vertical { background: #181825; width: 5px; margin: 0; }"
            "QScrollBar::handle:vertical { background: #45475a; border-radius: 2px; min-height: 20px; }"
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }"
        )
        content = QWidget()
        content.setStyleSheet("background: transparent;")
        scroll.setWidget(content)
        outer.addWidget(scroll)

        self._build_ui(content)

    def _build_ui(self, parent: QWidget):
        layout = QVBoxLayout(parent)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(4)
        self._current_color: tuple = (0, 0, 0, 255)   # (r, g, b, a)

        # ── 파일 ──────────────────────────────────────────
        layout.addWidget(SectionLabel("📁  파일"))
        btn_open = ActionButton("이미지 열기", "#a6e3a1")
        btn_open.setToolTip("이미지 파일 열기  (Ctrl+O)\n또는 창에 파일을 드래그 앤 드롭")
        btn_open.clicked.connect(self.sig_open)
        layout.addWidget(btn_open)

        btn_save = ActionButton("내보내기 / 저장", "#89dceb")
        btn_save.setToolTip("편집 이미지 저장  (Ctrl+E)")
        btn_save.clicked.connect(self.sig_save)
        layout.addWidget(btn_save)

        layout.addWidget(self._separator())

        # ── 실행 취소 / 재실행 ──────────────────────────
        layout.addWidget(SectionLabel("↩  편집"))
        row = QHBoxLayout()
        self.btn_undo = ActionButton("← 실행취소", "#cba6f7")
        self.btn_redo = ActionButton("재실행 →", "#cba6f7")
        self.btn_undo.setToolTip("실행 취소  (Ctrl+Z)")
        self.btn_redo.setToolTip("다시 실행  (Ctrl+Y)")
        self.btn_undo.clicked.connect(self.sig_undo)
        self.btn_redo.clicked.connect(self.sig_redo)
        row.addWidget(self.btn_undo)
        row.addWidget(self.btn_redo)
        layout.addLayout(row)

        layout.addWidget(self._separator())

        # ── 모드: 이동 / 선택 ──────────────────────────
        layout.addWidget(SectionLabel("🖐  모드"))
        self.btn_move = ToolButton("🖐 이동 / 선택  (V)")
        self.btn_move.setToolTip(
            "이동·선택 모드  (단축키: V 또는 Escape)\n"
            "오버레이 이미지를 클릭해 선택·이동하거나\n"
            "빈 공간을 드래그해 캔버스를 이동합니다."
        )
        self.btn_move.clicked.connect(self._on_move_toggle)
        layout.addWidget(self.btn_move)

        layout.addWidget(self._separator())

        # ── 배경 제거 ──────────────────────────────────
        layout.addWidget(SectionLabel("🪄  배경 제거"))

        btn_auto_bg = ActionButton("자동 배경 제거 (AI)", "#f38ba8")
        btn_auto_bg.setToolTip("AI(rembg)로 배경 자동 제거  (단축키: A)")
        btn_auto_bg.clicked.connect(self.sig_remove_bg_auto)
        layout.addWidget(btn_auto_bg)

        self.btn_grabcut = ToolButton("📦 GrabCut 선택")
        self.btn_grabcut.setToolTip(
            "GrabCut 모드  (단축키: G)\n"
            "드래그로 유지할 영역 선택 → 드래그 완료 시 자동 적용"
        )
        self.btn_grabcut.clicked.connect(self._on_grabcut_toggle)
        layout.addWidget(self.btn_grabcut)

        self.btn_brush = ToolButton("🖌 브러시 마스크")
        self.btn_brush.setToolTip(
            "브러시 모드  (단축키: B)\n"
            "지울 영역을 붓으로 칠한 뒤 '브러시 적용' 클릭"
        )
        self.btn_brush.clicked.connect(self._on_brush_toggle)
        layout.addWidget(self.btn_brush)

        brush_row = QHBoxLayout()
        brush_row.addWidget(QLabel("크기:"))
        self.brush_slider = QSlider(Qt.Orientation.Horizontal)
        self.brush_slider.setRange(5, 80)
        self.brush_slider.setValue(20)
        self.brush_slider.setStyleSheet("QSlider::handle:horizontal { background:#89b4fa; }")
        brush_row.addWidget(self.brush_slider)
        layout.addLayout(brush_row)

        btn_row2 = QHBoxLayout()
        btn_apply_brush = ActionButton("브러시 적용")
        btn_apply_brush.setToolTip("칠한 영역을 투명 처리")
        btn_apply_brush.clicked.connect(self.sig_apply_brush)
        btn_clear_brush = ActionButton("초기화", "#fab387")
        btn_clear_brush.setToolTip("브러시 영역 초기화")
        btn_clear_brush.clicked.connect(self._on_clear_brush)
        btn_row2.addWidget(btn_apply_brush)
        btn_row2.addWidget(btn_clear_brush)
        layout.addLayout(btn_row2)

        layout.addWidget(self._separator())

        # ── 색상 도구 ──────────────────────────────────────
        layout.addWidget(SectionLabel("🎨  색상 도구"))

        # 현재 색상 스와치 (클릭하면 색상 선택 다이얼로그)
        self._color_swatch = QPushButton()
        self._color_swatch.setMinimumHeight(32)
        self._color_swatch.setToolTip("현재 선택 색상\n클릭하면 색상 직접 선택")
        self._color_swatch.clicked.connect(self._on_pick_color)
        self._refresh_color_swatch()
        layout.addWidget(self._color_swatch)

        self.btn_pipette = ToolButton("💉 스포이드  (색 추출)")
        self.btn_pipette.setToolTip(
            "스포이드 모드\n이미지의 픽셀을 클릭하면 해당 색을 현재 색상으로 지정합니다."
        )
        self.btn_pipette.clicked.connect(self._on_pipette_toggle)
        layout.addWidget(self.btn_pipette)

        self.btn_fill = ToolButton("🪣 채우기")
        self.btn_fill.setToolTip(
            "채우기 모드\n클릭한 위치부터 유사한 색 영역을 현재 색상으로 채웁니다."
        )
        self.btn_fill.clicked.connect(self._on_fill_toggle)
        layout.addWidget(self.btn_fill)

        self.btn_color_brush = ToolButton("🖌 색상 브러시")
        self.btn_color_brush.setToolTip(
            "색상 브러시 모드\n마우스로 칠한 영역에 현재 색상을 적용합니다.\n"
            "칠한 후 '색상 브러시 적용' 클릭"
        )
        self.btn_color_brush.clicked.connect(self._on_color_brush_toggle)
        layout.addWidget(self.btn_color_brush)

        color_btn_row = QHBoxLayout()
        btn_apply_color_brush = ActionButton("브러시 적용")
        btn_apply_color_brush.setToolTip("색상 브러시로 칠한 영역에 색상 적용")
        btn_apply_color_brush.clicked.connect(self.sig_apply_color_brush)
        btn_clear_color_brush = ActionButton("초기화", "#fab387")
        btn_clear_color_brush.setToolTip("색상 브러시 영역 초기화")
        btn_clear_color_brush.clicked.connect(self._on_clear_color_brush)
        color_btn_row.addWidget(btn_apply_color_brush)
        color_btn_row.addWidget(btn_clear_color_brush)
        layout.addLayout(color_btn_row)

        layout.addWidget(self._separator())

        # ── 도형 그리기 ──────────────────────────────────────
        layout.addWidget(SectionLabel("✏  도형 그리기"))

        self.btn_shape_rect = ToolButton("□ 사각형 점선")
        self.btn_shape_rect.setToolTip(
            "점선 사각형 모드\n"
            "드래그로 사각형 영역을 지정하면\n현재 색상으로 점선 테두리를 그립니다."
        )
        self.btn_shape_rect.clicked.connect(self._on_shape_rect_toggle)
        layout.addWidget(self.btn_shape_rect)

        self.btn_shape_ellipse = ToolButton("○ 원 / 타원 점선")
        self.btn_shape_ellipse.setToolTip(
            "점선 원/타원 모드\n"
            "드래그로 타원 영역을 지정하면\n현재 색상으로 점선 테두리를 그립니다."
        )
        self.btn_shape_ellipse.clicked.connect(self._on_shape_ellipse_toggle)
        layout.addWidget(self.btn_shape_ellipse)

        shape_width_row = QHBoxLayout()
        shape_width_row.addWidget(QLabel("두께:"))
        self._spin_shape_width = QSpinBox()
        self._spin_shape_width.setRange(1, 20)
        self._spin_shape_width.setValue(2)
        self._spin_shape_width.setToolTip("점선 두께 (픽셀)")
        self._spin_shape_width.setStyleSheet(
            "background:#313244; color:#cdd6f4; border:1px solid #45475a; border-radius:4px;"
        )
        shape_width_row.addWidget(self._spin_shape_width)
        shape_width_row.addWidget(QLabel("간격:"))
        self._spin_shape_dash = QSpinBox()
        self._spin_shape_dash.setRange(2, 50)
        self._spin_shape_dash.setValue(12)
        self._spin_shape_dash.setToolTip("점선 대시 길이 (픽셀)")
        self._spin_shape_dash.setStyleSheet(
            "background:#313244; color:#cdd6f4; border:1px solid #45475a; border-radius:4px;"
        )
        shape_width_row.addWidget(self._spin_shape_dash)
        layout.addLayout(shape_width_row)

        layout.addWidget(self._separator())

        # ── 텍스트 ──────────────────────────────────────────
        layout.addWidget(SectionLabel("🔤  텍스트"))

        self.btn_text = ToolButton("T 텍스트 삽입")
        self.btn_text.setToolTip(
            "텍스트 모드  (단축키: T)\n"
            "캔버스를 클릭하면 텍스트 서식 다이얼로그가 열립니다."
        )
        self.btn_text.clicked.connect(self._on_text_toggle)
        layout.addWidget(self.btn_text)

        layout.addWidget(self._separator())

        # ── AI 인페인팅 ──────────────────────────────────────
        layout.addWidget(SectionLabel("✨  빈 영역 채우기"))
        self.btn_inpaint = ToolButton("✨ AI 빈 영역 채우기")
        self.btn_inpaint.setToolTip(
            "AI 채우기 모드\n"
            "드래그로 채울 영역을 선택하면\n"
            "투명(빈) 픽셀을 주변 색으로 자연스럽게 채웁니다."
        )
        self.btn_inpaint.clicked.connect(self._on_inpaint_toggle)
        layout.addWidget(self.btn_inpaint)

        layout.addWidget(self._separator())

        # ── 크롭 ──────────────────────────────────────
        layout.addWidget(SectionLabel("✂  크롭"))

        self.btn_crop_drag = ToolButton("🖱 드래그로 선택")
        self.btn_crop_drag.setToolTip("크롭 드래그 모드  (단축키: C)\n원하는 영역을 드래그")
        self.btn_crop_drag.clicked.connect(self._on_crop_drag_toggle)
        layout.addWidget(self.btn_crop_drag)

        self.btn_polygon = ToolButton("🔷 다각형 선택")
        self.btn_polygon.setToolTip(
            "다각형 선택 모드  (단축키: P)\n"
            "클릭으로 꼭짓점 추가\n"
            "시작점(빨간 점) 클릭 또는 더블클릭으로 완성\n"
            "ESC 또는 Enter로 취소/완성"
        )
        self.btn_polygon.clicked.connect(self._on_polygon_toggle)
        layout.addWidget(self.btn_polygon)

        size_row = QHBoxLayout()
        size_row.addWidget(QLabel("W:"))
        self.spin_w = QSpinBox()
        self.spin_w.setRange(1, 9999)
        self.spin_w.setValue(512)
        size_row.addWidget(self.spin_w)
        size_row.addWidget(QLabel("H:"))
        self.spin_h = QSpinBox()
        self.spin_h.setRange(1, 9999)
        self.spin_h.setValue(512)
        size_row.addWidget(self.spin_h)
        layout.addLayout(size_row)

        for spin in (self.spin_w, self.spin_h):
            spin.setStyleSheet(
                "background:#313244; color:#cdd6f4; border:1px solid #45475a; border-radius:4px;"
            )

        btn_crop_size = ActionButton("📐 크롭 위치 선택")
        btn_crop_size.setToolTip(
            "W·H 크기의 크롭 박스를 미리보기로 표시합니다.\n"
            "박스를 드래그로 원하는 위치에 놓고\n"
            "더블클릭 또는 Enter로 크롭을 적용하세요."
        )
        btn_crop_size.clicked.connect(
            lambda: self.sig_crop_size_preview.emit(self.spin_w.value(), self.spin_h.value())
        )
        layout.addWidget(btn_crop_size)

        layout.addWidget(self._separator())

        # ── 필터 ──────────────────────────────────────
        layout.addWidget(SectionLabel("🎨  필터"))
        self.combo_filter = QComboBox()
        self.combo_filter.addItems([
            "grayscale", "blur", "sharpen", "brightness", "contrast", "sepia"
        ])
        self.combo_filter.setStyleSheet(
            "background:#313244; color:#cdd6f4; border:1px solid #45475a; border-radius:4px; padding:4px;"
        )
        layout.addWidget(self.combo_filter)
        btn_filter = ActionButton("필터 적용")
        btn_filter.clicked.connect(lambda: self.sig_filter.emit(self.combo_filter.currentText()))
        layout.addWidget(btn_filter)

        layout.addWidget(self._separator())

        # ── 뷰 ──────────────────────────────────────────────
        layout.addWidget(SectionLabel("🔍  보기"))
        zoom_row = QHBoxLayout()
        btn_zoom_in = ActionButton("＋ 확대", "#a6adc8")
        btn_zoom_in.setToolTip("확대  (Ctrl+=)")
        btn_zoom_in.clicked.connect(self._emit_zoom_in)
        btn_zoom_out = ActionButton("－ 축소", "#a6adc8")
        btn_zoom_out.setToolTip("축소  (Ctrl+-)")
        btn_zoom_out.clicked.connect(self._emit_zoom_out)
        zoom_row.addWidget(btn_zoom_in)
        zoom_row.addWidget(btn_zoom_out)
        layout.addLayout(zoom_row)

        btn_zoom_fit = ActionButton("화면 맞춤  (Ctrl+0)", "#a6adc8")
        btn_zoom_fit.setToolTip("이미지를 창 크기에 맞게 초기화  (Ctrl+0)")
        btn_zoom_fit.clicked.connect(self.sig_zoom_fit)
        layout.addWidget(btn_zoom_fit)

        layout.addWidget(self._separator())

        # ── 초기화 ────────────────────────────────────
        btn_reset = ActionButton("원본으로 복원", "#f38ba8")
        btn_reset.setToolTip("모든 편집 취소 후 원본 복원  (Ctrl+R)")
        btn_reset.clicked.connect(self.sig_reset)
        layout.addWidget(btn_reset)

        layout.addStretch()

        # ── 도움말 ────────────────────────────────────
        layout.addWidget(self._separator())
        btn_help = QPushButton("❓ 사용 설명서  (F1)")
        btn_help.setMinimumHeight(32)
        btn_help.setStyleSheet("""
            QPushButton {
                background-color: #313244; color: #a6adc8;
                border: 1px solid #45475a; border-radius: 6px;
                padding: 5px 10px; font-size: 11px;
            }
            QPushButton:hover { background-color: #45475a; }
        """)
        btn_help.clicked.connect(self.sig_help)
        layout.addWidget(btn_help)

    # ------------------------------------------------------------------ #
    #  토글 핸들러
    # ------------------------------------------------------------------ #
    def _all_mode_buttons(self):
        return [self.btn_move, self.btn_grabcut, self.btn_brush, self.btn_crop_drag, self.btn_polygon,
                self.btn_pipette, self.btn_fill, self.btn_color_brush,
                self.btn_shape_rect, self.btn_shape_ellipse, self.btn_inpaint, self.btn_text]

    def _clear_mode_buttons(self):
        for btn in self._all_mode_buttons():
            btn.setChecked(False)

    def _on_move_toggle(self):
        self._clear_mode_buttons()
        self.btn_move.setChecked(True)
        self.sig_mode_changed.emit("none")

    def _on_grabcut_toggle(self):
        self._clear_mode_buttons()
        self.btn_grabcut.setChecked(True)
        self.sig_mode_changed.emit("grabcut")

    def _on_brush_toggle(self):
        self._clear_mode_buttons()
        self.btn_brush.setChecked(True)
        self.sig_mode_changed.emit("brush")

    def _on_crop_drag_toggle(self):
        self._clear_mode_buttons()
        self.btn_crop_drag.setChecked(True)
        self.sig_mode_changed.emit("crop")

    def _on_polygon_toggle(self):
        self._clear_mode_buttons()
        self.btn_polygon.setChecked(True)
        self.sig_mode_changed.emit("polygon")

    def _on_clear_brush(self):
        self._clear_mode_buttons()
        self.sig_mode_changed.emit("none")
        self.sig_clear_brush.emit()

    def _on_pipette_toggle(self):
        self._clear_mode_buttons()
        self.btn_pipette.setChecked(True)
        self.sig_mode_changed.emit("pipette")

    def _on_fill_toggle(self):
        self._clear_mode_buttons()
        self.btn_fill.setChecked(True)
        self.sig_mode_changed.emit("fill")

    def _on_color_brush_toggle(self):
        self._clear_mode_buttons()
        self.btn_color_brush.setChecked(True)
        self.sig_mode_changed.emit("color_brush")

    def _on_clear_color_brush(self):
        self._clear_mode_buttons()
        self.sig_mode_changed.emit("none")
        self.sig_clear_color_brush.emit()

    def _on_shape_rect_toggle(self):
        self._clear_mode_buttons()
        self.btn_shape_rect.setChecked(True)
        self.sig_mode_changed.emit("shape_rect")

    def _on_shape_ellipse_toggle(self):
        self._clear_mode_buttons()
        self.btn_shape_ellipse.setChecked(True)
        self.sig_mode_changed.emit("shape_ellipse")

    def _on_inpaint_toggle(self):
        self._clear_mode_buttons()
        self.btn_inpaint.setChecked(True)
        self.sig_mode_changed.emit("inpaint")

    def _on_text_toggle(self):
        self._clear_mode_buttons()
        self.btn_text.setChecked(True)
        self.sig_mode_changed.emit("text")

    def _on_pick_color(self):
        """색상 선택 다이얼로그 열기"""
        from PyQt6.QtWidgets import QColorDialog
        r, g, b, a = self._current_color
        color = QColorDialog.getColor(QColor(r, g, b), self, "색상 선택")
        if color.isValid():
            self._current_color = (color.red(), color.green(), color.blue(), 255)
            self._refresh_color_swatch()
            self.sig_color_changed.emit(*self._current_color)

    def _refresh_color_swatch(self):
        """색상 스와치 버튼 스타일 갱신"""
        r, g, b, a = self._current_color
        hex_str = f"#{r:02x}{g:02x}{b:02x}"
        text_color = "#000000" if (r + g + b) > 384 else "#ffffff"
        self._color_swatch.setText(f"  {hex_str}  (클릭 → 색상 선택)")
        self._color_swatch.setStyleSheet(f"""
            QPushButton {{
                background-color: {hex_str};
                color: {text_color};
                border: 1px solid #45475a;
                border-radius: 6px;
                padding: 6px;
                font-size: 11px;
                text-align: left;
            }}
            QPushButton:hover {{ border: 2px solid #89b4fa; }}
        """)

    def update_color_swatch(self, r: int, g: int, b: int, a: int = 255):
        """스포이드 등 외부에서 색상 업데이트"""
        self._current_color = (r, g, b, a)
        self._refresh_color_swatch()

    def get_current_color(self) -> tuple:
        return self._current_color

    def _emit_zoom_in(self):
        self.sig_zoom_in.emit()

    def _emit_zoom_out(self):
        self.sig_zoom_out.emit()

    # ------------------------------------------------------------------ #
    #  외부에서 모드 버튼 동기화 (단축키 등)
    # ------------------------------------------------------------------ #
    def set_mode(self, mode: str):
        self._clear_mode_buttons()
        mapping = {
            "none":          self.btn_move,
            "grabcut":       self.btn_grabcut,
            "brush":         self.btn_brush,
            "crop":          self.btn_crop_drag,
            "polygon":       self.btn_polygon,
            "pipette":       self.btn_pipette,
            "fill":          self.btn_fill,
            "color_brush":   self.btn_color_brush,
            "shape_rect":    self.btn_shape_rect,
            "shape_ellipse": self.btn_shape_ellipse,
            "inpaint":       self.btn_inpaint,
            "text":          self.btn_text,
        }
        if mode in mapping:
            mapping[mode].setChecked(True)

    # ------------------------------------------------------------------ #
    #  유틸
    # ------------------------------------------------------------------ #
    def set_undo_enabled(self, v: bool):
        self.btn_undo.setEnabled(v)

    def set_redo_enabled(self, v: bool):
        self.btn_redo.setEnabled(v)

    def get_brush_size(self) -> int:
        return self.brush_slider.value()

    def get_shape_line_width(self) -> int:
        return self._spin_shape_width.value()

    def get_shape_dash_len(self) -> int:
        return self._spin_shape_dash.value()

    @staticmethod
    def _separator() -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("color: #313244; margin: 4px 0;")
        return line
