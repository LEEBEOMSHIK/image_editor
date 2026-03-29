"""
ui/layer_panel.py
레이어 패널 — 오버레이 이미지 목록 관리
"""
import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QScrollArea, QFrame, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap, QImage
from PIL import Image


class _LayerRow(QWidget):
    """개별 레이어 행"""
    sig_select     = pyqtSignal()
    sig_delete     = pyqtSignal()
    sig_toggle_vis = pyqtSignal(bool)

    def __init__(self, name: str, visible: bool, selected: bool,
                 thumb: QPixmap | None = None, parent=None):
        super().__init__(parent)
        self.setFixedHeight(40)
        self._selected = selected
        self._build(name, visible, thumb)
        self._refresh_style()

    def _build(self, name: str, visible: bool, thumb: QPixmap | None):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(3)

        # 가시성 토글
        self.btn_vis = QPushButton("👁" if visible else "–")
        self.btn_vis.setFixedSize(22, 22)
        self.btn_vis.setCheckable(True)
        self.btn_vis.setChecked(visible)
        self.btn_vis.setStyleSheet(
            "QPushButton{background:transparent;border:none;font-size:13px;color:#cdd6f4;}"
            "QPushButton:!checked{color:#45475a;}"
        )
        self.btn_vis.toggled.connect(self._on_vis_toggle)
        layout.addWidget(self.btn_vis)

        # 썸네일
        if thumb:
            lbl_thumb = QLabel()
            lbl_thumb.setPixmap(thumb.scaled(28, 28,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation))
            lbl_thumb.setFixedSize(30, 30)
            lbl_thumb.setStyleSheet("background:#313244; border-radius:3px;")
            layout.addWidget(lbl_thumb)

        # 이름
        self.lbl_name = QLabel(name)
        self.lbl_name.setStyleSheet("color:#cdd6f4; font-size:11px;")
        self.lbl_name.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout.addWidget(self.lbl_name, 1)

        # 삭제
        btn_del = QPushButton("✕")
        btn_del.setFixedSize(18, 18)
        btn_del.setStyleSheet(
            "QPushButton{background:transparent;color:#6c7086;border:none;font-size:10px;}"
            "QPushButton:hover{color:#f38ba8;background:#45475a;border-radius:3px;}"
        )
        btn_del.clicked.connect(self.sig_delete)
        layout.addWidget(btn_del)

    def _on_vis_toggle(self, checked: bool):
        self.btn_vis.setText("👁" if checked else "–")
        self.sig_toggle_vis.emit(checked)

    def set_selected(self, v: bool):
        self._selected = v
        self._refresh_style()

    def _refresh_style(self):
        bg = "#2a2a3e" if self._selected else "transparent"
        border = "border-left:3px solid #89b4fa;" if self._selected else "border-left:3px solid transparent;"
        self.setStyleSheet(f"background:{bg}; {border} border-radius:4px;")

    def mousePressEvent(self, event):
        self.sig_select.emit()
        super().mousePressEvent(event)


class LayerPanel(QWidget):
    """레이어 패널"""
    sig_select     = pyqtSignal(int)        # 인덱스 (-1 = 기본 이미지)
    sig_delete     = pyqtSignal(int)
    sig_toggle_vis = pyqtSignal(int, bool)
    sig_merge_all  = pyqtSignal()
    sig_add_image  = pyqtSignal()           # 파일 다이얼로그로 추가

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(168)
        self.setStyleSheet("background:#181825; border-left:1px solid #313244;")
        self._rows: list[_LayerRow] = []
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 8)
        layout.setSpacing(0)

        # 헤더
        header = QLabel("  레이어")
        header.setStyleSheet(
            "background:#1e1e2e; color:#89b4fa; font-size:11px; font-weight:bold;"
            "letter-spacing:1px; padding:7px; border-bottom:1px solid #313244;"
        )
        layout.addWidget(header)

        # 이미지 추가 버튼
        btn_add = QPushButton("＋  이미지 추가")
        btn_add.setToolTip("파일을 열어 새 레이어로 추가하거나\n이미지를 캔버스에 드래그 앤 드롭하세요")
        btn_add.setStyleSheet(
            "QPushButton{background:#313244;color:#a6e3a1;border:none;"
            "padding:6px;font-size:11px;font-weight:bold;border-bottom:1px solid #313244;}"
            "QPushButton:hover{background:#45475a;}"
        )
        btn_add.clicked.connect(self.sig_add_image)
        layout.addWidget(btn_add)

        # 레이어 목록
        self._list_container = QWidget()
        self._list_layout = QVBoxLayout(self._list_container)
        self._list_layout.setContentsMargins(4, 4, 4, 4)
        self._list_layout.setSpacing(2)
        self._list_layout.addStretch()

        scroll = QScrollArea()
        scroll.setWidget(self._list_container)
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(
            "QScrollArea{border:none;background:transparent;}"
            "QScrollBar:vertical{background:#181825;width:6px;}"
            "QScrollBar::handle:vertical{background:#45475a;border-radius:3px;}"
        )
        layout.addWidget(scroll, 1)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color:#313244; margin:2px 0;")
        layout.addWidget(sep)

        # 병합 버튼
        btn_merge = QPushButton("⬇  모두 병합")
        btn_merge.setToolTip("모든 레이어를 기본 이미지에 합성합니다")
        btn_merge.setStyleSheet(
            "QPushButton{background:#313244;color:#f9e2af;border:none;"
            "padding:7px;margin:2px 6px 0;font-size:11px;font-weight:bold;border-radius:5px;}"
            "QPushButton:hover{background:#45475a;}"
        )
        btn_merge.clicked.connect(self.sig_merge_all)
        layout.addWidget(btn_merge)

    # ------------------------------------------------------------------ #
    #  공개 메서드
    # ------------------------------------------------------------------ #
    def update_layers(self, layers: list[dict], active_idx: int):
        """레이어 목록 전체 갱신"""
        # 기존 행 제거
        for row in self._rows:
            self._list_layout.removeWidget(row)
            row.deleteLater()
        self._rows.clear()

        insert_pos = 0

        # 오버레이 (위에서 아래 순 — 마지막 인덱스가 최상단)
        for i in range(len(layers) - 1, -1, -1):
            ov = layers[i]
            name = ov.get('name', f'레이어 {i + 1}')
            thumb = _make_thumbnail(ov['pil'])
            row = _LayerRow(name=name, visible=ov.get('visible', True),
                            selected=(i == active_idx), thumb=thumb)
            ii = i
            row.sig_select.connect(lambda idx=ii: self.sig_select.emit(idx))
            row.sig_delete.connect(lambda idx=ii: self.sig_delete.emit(idx))
            row.sig_toggle_vis.connect(lambda v, idx=ii: self.sig_toggle_vis.emit(idx, v))
            self._list_layout.insertWidget(insert_pos, row)
            self._rows.append(row)
            insert_pos += 1

        # 기본 이미지 행 (항상 맨 아래)
        base_row = _LayerRow(name="기본 이미지", visible=True,
                             selected=(active_idx == -1))
        base_row.sig_select.connect(lambda: self.sig_select.emit(-1))
        base_row.sig_delete.connect(lambda: self.sig_delete.emit(-1))
        base_row.sig_toggle_vis.connect(lambda v: self.sig_toggle_vis.emit(-1, v))
        self._list_layout.insertWidget(insert_pos, base_row)
        self._rows.append(base_row)


# ------------------------------------------------------------------ #
#  유틸
# ------------------------------------------------------------------ #
def _make_thumbnail(pil_img: Image.Image) -> QPixmap:
    thumb = pil_img.convert("RGBA").copy()
    thumb.thumbnail((28, 28), Image.LANCZOS)
    data = thumb.tobytes("raw", "RGBA")
    qimg = QImage(data, thumb.width, thumb.height, QImage.Format.Format_RGBA8888)
    return QPixmap.fromImage(qimg)
