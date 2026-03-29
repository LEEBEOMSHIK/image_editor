"""
ui/export_dialog.py
저장 형식 선택 다이얼로그
"""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QComboBox, QFileDialog
)
from PyQt6.QtCore import Qt


class ExportDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("이미지 내보내기")
        self.setFixedSize(320, 160)
        self.setStyleSheet("""
            QDialog { background-color: #1e1e2e; color: #cdd6f4; }
            QLabel  { color: #cdd6f4; }
            QComboBox {
                background: #313244; color: #cdd6f4;
                border: 1px solid #45475a; border-radius: 4px;
                padding: 4px; min-height: 28px;
            }
            QPushButton {
                background: #89b4fa; color: #1e1e2e;
                border: none; border-radius: 6px;
                padding: 8px 16px; font-weight: bold;
            }
            QPushButton:hover { background: #b4befe; }
            QPushButton#cancel {
                background: #45475a; color: #cdd6f4;
            }
        """)
        self._path = None
        self._fmt = None
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        layout.addWidget(QLabel("저장 형식을 선택하세요:"))

        self.combo = QComboBox()
        self.combo.addItems(["PNG", "JPG", "PDF"])
        layout.addWidget(self.combo)

        row = QHBoxLayout()
        btn_cancel = QPushButton("취소")
        btn_cancel.setObjectName("cancel")
        btn_cancel.clicked.connect(self.reject)

        btn_ok = QPushButton("저장 경로 선택")
        btn_ok.clicked.connect(self._on_ok)

        row.addWidget(btn_cancel)
        row.addWidget(btn_ok)
        layout.addLayout(row)

    def _on_ok(self):
        fmt = self.combo.currentText()
        filter_map = {
            "PNG": "PNG 이미지 (*.png)",
            "JPG": "JPEG 이미지 (*.jpg *.jpeg)",
            "PDF": "PDF 문서 (*.pdf)",
        }
        path, _ = QFileDialog.getSaveFileName(
            self, "저장", "", filter_map[fmt]
        )
        if path:
            self._path = path
            self._fmt = fmt
            self.accept()

    def get_result(self):
        return self._path, self._fmt
