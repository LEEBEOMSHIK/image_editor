"""
Image Editor Pro - Main Entry Point
실행 방법: python main.py
"""
import sys

# ★ Qt보다 먼저 rembg/onnxruntime을 로드해야 DLL 충돌이 없습니다.
#   Qt가 먼저 로드되면 onnxruntime_pybind11_state DLL 초기화가 실패합니다.
import core.image_processor  # noqa: F401

from PyQt6.QtWidgets import QApplication
from ui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Image Editor Pro")
    app.setStyle("Fusion")

    import os
    icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'images', 'main.png')
    if os.path.isfile(icon_path):
        from PyQt6.QtGui import QIcon
        app.setWindowIcon(QIcon(icon_path))

    # exe에 파일을 드롭하면 sys.argv[1]로 경로가 전달됨
    initial_path = sys.argv[1] if len(sys.argv) > 1 else None

    window = MainWindow(initial_path=initial_path)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
