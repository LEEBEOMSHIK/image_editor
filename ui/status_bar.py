"""
ui/status_bar.py
하단 상태 표시줄
"""
from PyQt6.QtWidgets import QStatusBar, QLabel
from PyQt6.QtCore import Qt


class StatusBar(QStatusBar):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            QStatusBar {
                background-color: #181825;
                color: #a6adc8;
                border-top: 1px solid #313244;
                font-size: 11px;
            }
        """)
        lbl_style = "color: #a6adc8; padding: 0 8px;"
        self._lbl_info = QLabel("이미지를 열어 편집을 시작하세요.")
        self._lbl_zoom = QLabel("줌: 100%")
        self._lbl_zoom.setStyleSheet(lbl_style)
        self._lbl_size = QLabel("")
        self._lbl_size.setStyleSheet(lbl_style)
        self.addWidget(self._lbl_info, 1)
        self.addPermanentWidget(self._lbl_zoom)
        self.addPermanentWidget(self._lbl_size)

    def set_message(self, msg: str):
        self._lbl_info.setText(msg)

    def set_size(self, w: int, h: int):
        self._lbl_size.setText(f"{w} × {h} px")

    def set_zoom(self, zoom: float):
        self._lbl_zoom.setText(f"줌: {int(zoom * 100)}%")
