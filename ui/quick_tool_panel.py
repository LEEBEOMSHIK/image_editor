"""
ui/quick_tool_panel.py
드래그 가능한 떠있는 도구 패널 (퀵 액세스 - 캔버스 좌상단 오버레이)
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QFrame, QLabel
)
from PyQt6.QtCore import Qt, pyqtSignal, QPoint


class _IconBtn(QPushButton):
    """퀵 패널용 아이콘 전용 버튼"""

    _STYLE_NORMAL = """
        QPushButton {
            background-color: #2a2a3e;
            color: #cdd6f4;
            border: 1px solid #45475a;
            border-radius: 5px;
            font-size: 16px;
            padding: 0;
        }
        QPushButton:hover { background-color: #45475a; }
        QPushButton:checked {
            background-color: #89b4fa;
            color: #1e1e2e;
            border: 1px solid #89b4fa;
        }
    """
    _STYLE_ACTION = """
        QPushButton {
            background-color: #313244;
            color: #cdd6f4;
            border: 1px solid #45475a;
            border-radius: 5px;
            font-size: 16px;
            padding: 0;
        }
        QPushButton:hover { background-color: #45475a; }
        QPushButton:pressed { background-color: #89b4fa; color: #1e1e2e; }
    """

    def __init__(self, icon: str, label: str, tooltip: str = "",
                 checkable: bool = True, parent=None):
        super().__init__(icon, parent)
        self.setCheckable(checkable)
        self.setFixedSize(34, 30)
        self.setToolTip(f"{label}  —  {tooltip}" if tooltip else label)
        self.setStyleSheet(
            self._STYLE_NORMAL if checkable else self._STYLE_ACTION
        )


class _DragHandle(QLabel):
    """드래그 핸들 — 마우스 이벤트를 직접 처리해 패널 이동"""

    def __init__(self, panel: "QuickToolPanel"):
        super().__init__("⠿  퀵 도구", panel)
        self._panel = panel
        self._drag_pos: QPoint | None = None
        self.setFixedHeight(22)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setCursor(Qt.CursorShape.SizeAllCursor)
        self.setStyleSheet(
            "color: #6c7086; font-size: 10px; font-weight: bold; "
            "letter-spacing: 1px; background: transparent;"
        )

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            # panel.mapToGlobal(QPoint(0,0)) → 패널 좌상단의 전역 좌표
            # 전역 마우스 위치 - 전역 패널 위치 = 패널 내 상대 오프셋
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
            if parent:
                new_pos = parent.mapFromGlobal(new_global)
            else:
                new_pos = new_global
            self._panel.move(new_pos)
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
        super().mouseReleaseEvent(event)


class QuickToolPanel(QWidget):
    """
    드래그 가능한 떠있는 퀵 도구 패널.
    MainWindow._canvas_edit 위에 오버레이로 올라갑니다.
    """

    sig_mode_changed = pyqtSignal(str)   # 모드 전환 요청
    sig_action       = pyqtSignal(str)   # "undo", "redo", "remove_bg",
                                         # "zoom_in", "zoom_out", "zoom_fit"
    sig_closed       = pyqtSignal()      # X 버튼으로 패널 닫힘

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setWindowFlags(Qt.WindowType.Widget)

        self._mode_btns: dict[str, _IconBtn] = {}

        self.setFixedWidth(50)
        self.setStyleSheet("""
            QuickToolPanel {
                background-color: #18182d;
                border: 1px solid #45475a;
                border-radius: 10px;
            }
        """)

        self._build_ui()
        self.adjustSize()

    # ------------------------------------------------------------------ #
    #  UI 구성
    # ------------------------------------------------------------------ #
    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(4, 4, 4, 4)
        outer.setSpacing(2)

        # ── 헤더: 드래그 핸들 + 닫기 버튼 ───────────
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(0)

        self._handle = _DragHandle(self)
        header.addWidget(self._handle, 1)

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(16, 16)
        close_btn.setToolTip("퀵 도구 패널 닫기")
        close_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #6c7086;
                border: none;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover { color: #f38ba8; }
        """)
        close_btn.clicked.connect(self._on_close_btn)
        header.addWidget(close_btn)

        outer.addLayout(header)
        outer.addWidget(self._sep())

        # ── 모드 버튼 (세로 단열) ─────────────────
        modes = [
            ("🖐", "none",          "이동 / 선택",   "이동 / 선택  (V)"),
            ("✎",  "select",        "선택/편집",     "선택/편집 모드  (E)  — 텍스트 클릭 시 편집"),
            ("✂",  "crop",          "드래그 크롭",   "드래그 크롭  (C)"),
            ("🔷", "polygon",       "다각형 선택",   "다각형 선택  (P)"),
            ("📦", "grabcut",       "GrabCut 제거", "GrabCut 배경 제거  (G)"),
            ("🖌", "brush",         "브러시 마스크", "브러시 마스크  (B)"),
            ("💉", "pipette",       "스포이드",      "스포이드 (색 추출)"),
            ("🪣", "fill",          "채우기",        "채우기 (플러드 필)"),
            ("🎨", "color_brush",   "색상 브러시",   "색상 브러시"),
            ("□",  "shape_rect",    "사각형 그리기", "점선 사각형 그리기"),
            ("○",  "shape_ellipse", "원/타원 그리기","점선 원/타원 그리기"),
            ("✨", "inpaint",       "AI 인페인팅",   "AI 빈 영역 채우기"),
        ]

        for icon, mode, label, tip in modes:
            btn = _IconBtn(icon, label, tip, checkable=True)
            btn.clicked.connect(lambda checked, m=mode: self._on_mode_btn(m))
            self._mode_btns[mode] = btn
            outer.addWidget(btn)

        outer.addWidget(self._sep())

        # ── 액션 버튼 (Undo·Redo·AI 배경 제거) ─────
        actions = [
            ("↩", "undo",      "실행 취소",      "실행 취소  (Ctrl+Z)"),
            ("↪", "redo",      "다시 실행",      "다시 실행  (Ctrl+Y)"),
            ("🤖", "remove_bg", "AI 배경 제거",   "AI 자동 배경 제거  (A)"),
        ]
        for icon, act, label, tip in actions:
            btn = _IconBtn(icon, label, tip, checkable=False)
            btn.clicked.connect(lambda _, a=act: self.sig_action.emit(a))
            outer.addWidget(btn)

        outer.addWidget(self._sep())

        # ── 줌 버튼 ─────────────────────────────────
        zooms = [
            ("＋", "zoom_in",  "확대",     "확대  (Ctrl+=)"),
            ("－", "zoom_out", "축소",     "축소  (Ctrl+-)"),
            ("⊡",  "zoom_fit", "화면 맞춤","화면 맞춤  (Ctrl+0)"),
        ]
        for icon, act, label, tip in zooms:
            btn = _IconBtn(icon, label, tip, checkable=False)
            btn.clicked.connect(lambda _, a=act: self.sig_action.emit(a))
            outer.addWidget(btn)

    # ------------------------------------------------------------------ #
    #  모드 버튼 토글
    # ------------------------------------------------------------------ #
    def _on_mode_btn(self, mode: str):
        for m, btn in self._mode_btns.items():
            btn.setChecked(m == mode)
        self.sig_mode_changed.emit(mode)

    def _on_close_btn(self):
        self.hide()
        self.sig_closed.emit()

    def set_mode(self, mode: str):
        """외부(단축키 등)에서 모드 동기화"""
        for m, btn in self._mode_btns.items():
            btn.setChecked(m == mode)

    # ------------------------------------------------------------------ #
    #  유틸
    # ------------------------------------------------------------------ #
    @staticmethod
    def _sep() -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("color: #313244; margin: 2px 0;")
        return line
