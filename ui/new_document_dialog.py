"""
ui/new_document_dialog.py
새 문서 만들기 다이얼로그 (Photoshop 스타일 캔버스 크기 선택)
"""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSpinBox, QWidget, QScrollArea, QFrame, QTabWidget,
    QGridLayout, QSizePolicy
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QPainter, QColor, QPen, QFont


# ── 프리셋 정의: (이름, 너비, 높이, 설명) ──
_PRESETS = {
    "사진": [
        ("1920 × 1080", 1920, 1080, "Full HD · 16:9"),
        ("3840 × 2160", 3840, 2160, "4K UHD · 16:9"),
        ("2560 × 1440", 2560, 1440, "2K QHD · 16:9"),
        ("1280 × 720",  1280,  720, "HD · 16:9"),
        ("4000 × 3000", 4000, 3000, "12MP · 4:3"),
        ("3000 × 2000", 3000, 2000, "6MP · 3:2"),
    ],
    "웹 / SNS": [
        ("1920 × 1080", 1920, 1080, "Full HD 배너"),
        ("1200 × 628",  1200,  628, "OG / 소셜 공유"),
        ("1080 × 1080", 1080, 1080, "SNS 정사각형"),
        ("1080 × 1920", 1080, 1920, "스토리 · 9:16"),
        ("1920 × 600",  1920,  600, "웹 배너"),
        ("800 × 800",    800,  800, "아이콘 / 섬네일"),
    ],
    "인쇄": [
        ("2480 × 3508", 2480, 3508, "A4 세로 · 300dpi"),
        ("3508 × 2480", 3508, 2480, "A4 가로 · 300dpi"),
        ("1748 × 2480", 1748, 2480, "A5 세로 · 300dpi"),
        ("3543 × 5315", 3543, 5315, "A3 세로 · 300dpi"),
        ("2835 × 4252", 2835, 4252, "B5 세로 · 300dpi"),
        ("2480 × 2480", 2480, 2480, "명함 · 300dpi"),
    ],
    "AI / 모바일": [
        ("512 × 512",   512,   512, "AI 이미지 생성 (소)"),
        ("768 × 768",   768,   768, "AI 이미지 생성 (중)"),
        ("1024 × 1024", 1024, 1024, "AI 이미지 생성 (대)"),
        ("1080 × 1920", 1080, 1920, "모바일 전체 화면"),
        ("393 × 852",    393,  852, "iPhone 15 Pro"),
        ("360 × 800",    360,  800, "Android 전형"),
    ],
}

_DARK = "#1e1e2e"
_PANEL = "#181825"
_CARD  = "#313244"
_CARD_SEL = "#89b4fa"
_BORDER = "#45475a"
_TEXT  = "#cdd6f4"
_MUTED = "#a6adc8"


class _PresetCard(QFrame):
    """개별 프리셋 카드 위젯"""

    def __init__(self, name: str, w: int, h: int, desc: str, parent=None):
        super().__init__(parent)
        self.preset_name = name
        self.preset_w = w
        self.preset_h = h
        self._selected = False

        self.setFixedSize(150, 130)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._apply_style(False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        # 문서 아이콘 영역
        self._icon_area = QWidget()
        self._icon_area.setFixedHeight(60)
        self._icon_area.setStyleSheet("background: transparent;")
        layout.addWidget(self._icon_area)

        # 이름
        lbl_name = QLabel(name)
        lbl_name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_name.setStyleSheet(f"color: {_TEXT}; font-size: 11px; font-weight: bold; background: transparent;")
        lbl_name.setWordWrap(True)
        layout.addWidget(lbl_name)

        # 설명
        lbl_desc = QLabel(desc)
        lbl_desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_desc.setStyleSheet(f"color: {_MUTED}; font-size: 10px; background: transparent;")
        layout.addWidget(lbl_desc)

    def _apply_style(self, selected: bool):
        if selected:
            self.setStyleSheet(f"""
                QFrame {{
                    background-color: #1a2a3a;
                    border: 2px solid {_CARD_SEL};
                    border-radius: 8px;
                }}
            """)
        else:
            self.setStyleSheet(f"""
                QFrame {{
                    background-color: {_CARD};
                    border: 1px solid {_BORDER};
                    border-radius: 8px;
                }}
                QFrame:hover {{
                    border: 1px solid #6c7086;
                    background-color: #383852;
                }}
            """)

    def set_selected(self, sel: bool):
        self._selected = sel
        self._apply_style(sel)

    def paintEvent(self, event):
        super().paintEvent(event)
        # 문서 아이콘 그리기
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        icon_rect = self._icon_area.geometry()
        cx = icon_rect.x() + icon_rect.width() // 2
        cy = icon_rect.y() + icon_rect.height() // 2

        w_ratio = self.preset_w / max(self.preset_w, self.preset_h)
        h_ratio = self.preset_h / max(self.preset_w, self.preset_h)
        max_dim = 36
        dw = int(max_dim * w_ratio)
        dh = int(max_dim * h_ratio)
        dw = max(dw, 16)
        dh = max(dh, 16)

        rx = cx - dw // 2
        ry = cy - dh // 2

        if self._selected:
            painter.fillRect(rx, ry, dw, dh, QColor("#1a4080"))
            painter.setPen(QPen(QColor(_CARD_SEL), 1))
        else:
            painter.fillRect(rx, ry, dw, dh, QColor("#45475a"))
            painter.setPen(QPen(QColor("#6c7086"), 1))
        painter.drawRect(rx, ry, dw, dh)

        # 접힌 모서리 표시
        fold = min(8, dw // 3, dh // 3)
        if self._selected:
            painter.fillRect(rx + dw - fold, ry, fold, fold, QColor("#0a1a3a"))
            painter.setPen(QPen(QColor(_CARD_SEL), 1))
        else:
            painter.fillRect(rx + dw - fold, ry, fold, fold, QColor("#313244"))
            painter.setPen(QPen(QColor("#6c7086"), 1))
        painter.drawLine(rx + dw - fold, ry, rx + dw - fold, ry + fold)
        painter.drawLine(rx + dw - fold, ry + fold, rx + dw, ry + fold)
        painter.end()


class NewDocumentDialog(QDialog):
    """새 문서 크기 선택 다이얼로그"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("새 문서")
        self.setFixedSize(720, 520)
        self.setStyleSheet(f"""
            QDialog {{ background-color: {_DARK}; color: {_TEXT}; }}
            QTabWidget::pane {{ border: 1px solid {_BORDER}; background: {_DARK}; }}
            QTabBar::tab {{
                background: {_PANEL}; color: {_MUTED};
                border: 1px solid {_BORDER};
                padding: 6px 16px; font-size: 12px;
            }}
            QTabBar::tab:selected {{ background: {_DARK}; color: {_TEXT}; border-bottom: 2px solid {_CARD_SEL}; }}
            QTabBar::tab:hover {{ background: {_CARD}; color: {_TEXT}; }}
            QScrollArea {{ border: none; background: transparent; }}
            QScrollBar:vertical {{ background: {_PANEL}; width: 6px; margin: 0; }}
            QScrollBar::handle:vertical {{ background: {_BORDER}; border-radius: 3px; min-height: 20px; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
            QLabel {{ color: {_TEXT}; }}
            QSpinBox {{
                background: {_CARD}; color: {_TEXT};
                border: 1px solid {_BORDER}; border-radius: 4px;
                padding: 4px 8px; font-size: 13px;
            }}
        """)

        self._selected_w = 1920
        self._selected_h = 1080
        self._cards: list[_PresetCard] = []

        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── 상단 헤더 ────────────────────────────────
        header = QWidget()
        header.setFixedHeight(52)
        header.setStyleSheet(f"background: {_PANEL}; border-bottom: 1px solid {_BORDER};")
        h_lay = QHBoxLayout(header)
        h_lay.setContentsMargins(20, 0, 20, 0)
        title_lbl = QLabel("새 문서")
        title_lbl.setStyleSheet(f"color: {_TEXT}; font-size: 18px; font-weight: bold;")
        h_lay.addWidget(title_lbl)
        h_lay.addStretch()
        root.addWidget(header)

        # ── 탭 + 카드 그리드 ────────────────────────
        body = QWidget()
        body.setStyleSheet(f"background: {_DARK};")
        body_lay = QVBoxLayout(body)
        body_lay.setContentsMargins(20, 16, 20, 8)
        body_lay.setSpacing(12)

        self._tabs = QTabWidget()
        for tab_name, presets in _PRESETS.items():
            self._tabs.addTab(self._make_preset_tab(presets), tab_name)
        self._tabs.currentChanged.connect(self._on_tab_changed)
        body_lay.addWidget(self._tabs)

        root.addWidget(body, 1)

        # ── 하단 크기 입력 + 버튼 ───────────────────
        footer = QWidget()
        footer.setFixedHeight(80)
        footer.setStyleSheet(f"background: {_PANEL}; border-top: 1px solid {_BORDER};")
        f_lay = QHBoxLayout(footer)
        f_lay.setContentsMargins(20, 0, 20, 0)
        f_lay.setSpacing(12)

        f_lay.addWidget(QLabel("너비:"))
        self._spin_w = QSpinBox()
        self._spin_w.setRange(1, 20000)
        self._spin_w.setValue(self._selected_w)
        self._spin_w.setFixedWidth(90)
        self._spin_w.setSuffix(" px")
        self._spin_w.valueChanged.connect(self._on_custom_size)
        f_lay.addWidget(self._spin_w)

        f_lay.addWidget(QLabel("높이:"))
        self._spin_h = QSpinBox()
        self._spin_h.setRange(1, 20000)
        self._spin_h.setValue(self._selected_h)
        self._spin_h.setFixedWidth(90)
        self._spin_h.setSuffix(" px")
        self._spin_h.valueChanged.connect(self._on_custom_size)
        f_lay.addWidget(self._spin_h)

        f_lay.addStretch()

        btn_cancel = QPushButton("취소")
        btn_cancel.setFixedSize(90, 36)
        btn_cancel.setStyleSheet(f"""
            QPushButton {{
                background: {_CARD}; color: {_TEXT};
                border: 1px solid {_BORDER}; border-radius: 6px; font-size: 13px;
            }}
            QPushButton:hover {{ background: {_BORDER}; }}
        """)
        btn_cancel.clicked.connect(self.reject)
        f_lay.addWidget(btn_cancel)

        btn_create = QPushButton("만들기")
        btn_create.setFixedSize(90, 36)
        btn_create.setStyleSheet("""
            QPushButton {
                background: #89b4fa; color: #1e1e2e;
                border: none; border-radius: 6px;
                font-size: 13px; font-weight: bold;
            }
            QPushButton:hover { background: #b4befe; }
        """)
        btn_create.clicked.connect(self.accept)
        f_lay.addWidget(btn_create)

        root.addWidget(footer)

    def _make_preset_tab(self, presets: list) -> QWidget:
        """탭 하나 안에 카드 그리드 생성"""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        container = QWidget()
        container.setStyleSheet(f"background: {_DARK};")
        grid = QGridLayout(container)
        grid.setContentsMargins(10, 14, 10, 14)
        grid.setSpacing(12)

        for i, (name, w, h, desc) in enumerate(presets):
            card = _PresetCard(name, w, h, desc)
            card.mousePressEvent = lambda e, c=card, pw=w, ph=h: self._select_card(c, pw, ph)
            grid.addWidget(card, i // 4, i % 4)
            self._cards.append(card)

        # 첫 번째 카드 기본 선택
        if presets and self._cards:
            first = self._cards[0]
            first.set_selected(True)
            self._selected_w = first.preset_w
            self._selected_h = first.preset_h
            self._update_spinboxes()

        scroll.setWidget(container)
        return scroll

    def _select_card(self, card: _PresetCard, w: int, h: int):
        for c in self._cards:
            c.set_selected(False)
        card.set_selected(True)
        self._selected_w = w
        self._selected_h = h
        self._update_spinboxes()

    def _update_spinboxes(self):
        if not hasattr(self, '_spin_w'):
            return
        self._spin_w.blockSignals(True)
        self._spin_h.blockSignals(True)
        self._spin_w.setValue(self._selected_w)
        self._spin_h.setValue(self._selected_h)
        self._spin_w.blockSignals(False)
        self._spin_h.blockSignals(False)

    def _on_custom_size(self):
        """직접 입력 시 카드 선택 해제"""
        for c in self._cards:
            c.set_selected(False)
        self._selected_w = self._spin_w.value()
        self._selected_h = self._spin_h.value()

    def _on_tab_changed(self, _):
        """탭 변경 시 첫 카드 선택"""
        scroll = self._tabs.currentWidget()
        if scroll is None:
            return
        container = scroll.widget()
        if container is None:
            return
        for c in self._cards:
            c.set_selected(False)
        # 현재 탭의 첫 카드 선택
        cards_in_tab = [c for c in container.findChildren(_PresetCard)]
        if cards_in_tab:
            first = cards_in_tab[0]
            first.set_selected(True)
            self._selected_w = first.preset_w
            self._selected_h = first.preset_h
            self._update_spinboxes()

    def get_size(self) -> tuple[int, int]:
        """선택된 (너비, 높이) 반환"""
        return self._spin_w.value(), self._spin_h.value()
