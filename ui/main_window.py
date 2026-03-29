"""
ui/main_window.py
메인 윈도우 - 모든 컴포넌트 통합
"""
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QFileDialog, QMessageBox, QLabel,
    QScrollArea, QDialog, QTextBrowser, QPushButton, QVBoxLayout as QVBox
)
import os
import sys
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QObject, QTimer
from PyQt6.QtGui import QAction, QKeySequence, QShortcut, QIcon

from core.image_processor import ImageProcessor
from ui.canvas import ImageCanvas
from ui.toolbar import Toolbar
from ui.status_bar import StatusBar
from ui.export_dialog import ExportDialog
from ui.layer_panel import LayerPanel


# ------------------------------------------------------------------ #
#  백그라운드 스레드 (rembg가 느리므로 UI 블로킹 방지)
# ------------------------------------------------------------------ #
class BgRemoveWorker(QObject):
    finished = pyqtSignal(object)   # PIL Image
    error = pyqtSignal(str)

    def __init__(self, processor: ImageProcessor):
        super().__init__()
        self._proc = processor

    def run(self):
        try:
            result = self._proc.remove_background_auto()
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


# ------------------------------------------------------------------ #
#  메인 윈도우
# ------------------------------------------------------------------ #
_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".webp", ".tiff", ".tif", ".gif"}


class MainWindow(QMainWindow):
    def __init__(self, initial_path: str | None = None):
        super().__init__()
        self.setWindowTitle("Image Editor Pro")
        # 앱 아이콘
        icon_path = self._get_icon_path()
        if icon_path:
            self.setWindowIcon(QIcon(icon_path))
        self.setMinimumSize(1000, 680)
        self.resize(1200, 750)

        self._processor = ImageProcessor()
        self._grabcut_rect = None    # GrabCut 선택 사각형 저장
        self._thread = None
        self._worker = None

        self._layer_refresh_timer = QTimer(self)
        self._layer_refresh_timer.setSingleShot(True)
        self._layer_refresh_timer.setInterval(50)
        self._layer_refresh_timer.timeout.connect(self._do_refresh_layer_panel)

        self._apply_dark_theme()
        self._build_ui()
        self._build_menu()
        self._connect_signals()
        self._setup_shortcuts()
        self._update_edit_state()

        # 드래그 앤 드롭 허용
        self.setAcceptDrops(True)

        # exe에 파일을 드롭하거나 커맨드라인 인수로 열기
        if initial_path:
            self._load_file(initial_path)

    # ------------------------------------------------------------------ #
    #  테마
    # ------------------------------------------------------------------ #
    def _apply_dark_theme(self):
        self.setStyleSheet("""
            QMainWindow { background-color: #1e1e2e; }
            QMenuBar {
                background-color: #181825;
                color: #cdd6f4;
                border-bottom: 1px solid #313244;
            }
            QMenuBar::item:selected { background-color: #313244; }
            QMenu {
                background-color: #1e1e2e;
                color: #cdd6f4;
                border: 1px solid #313244;
            }
            QMenu::item:selected { background-color: #313244; }
            QSplitter::handle { background-color: #313244; }
            QScrollArea { background: transparent; border: none; }
            QLabel { color: #cdd6f4; }
        """)

    # ------------------------------------------------------------------ #
    #  UI 구성
    # ------------------------------------------------------------------ #
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # 왼쪽 도구 패널
        self._toolbar = Toolbar()
        root.addWidget(self._toolbar)

        # 중앙: 편집 결과 (전체 너비 사용, 원본은 캔버스 우상단 오버레이로 표시)
        edit_panel = self._make_preview_panel("편집 결과")
        self._canvas_edit = ImageCanvas()
        edit_panel.layout().addWidget(self._canvas_edit)
        root.addWidget(edit_panel, 1)

        # 레이어 패널 (오른쪽)
        self._layer_panel = LayerPanel()
        root.addWidget(self._layer_panel)

        # 상태바
        self._status = StatusBar()
        self.setStatusBar(self._status)

    @staticmethod
    def _make_preview_panel(title: str) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background-color: #1e1e2e;")
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        lbl = QLabel(f"  {title}")
        lbl.setStyleSheet("""
            background-color: #181825;
            color: #a6adc8;
            font-size: 11px;
            font-weight: bold;
            letter-spacing: 1px;
            padding: 6px;
            border-bottom: 1px solid #313244;
        """)
        layout.addWidget(lbl)
        return w

    # ------------------------------------------------------------------ #
    #  메뉴바
    # ------------------------------------------------------------------ #
    def _build_menu(self):
        menubar = self.menuBar()

        file_menu = menubar.addMenu("파일(&F)")
        act_open = QAction("열기(&O)", self)
        act_open.setShortcut(QKeySequence.StandardKey.Open)
        act_open.triggered.connect(self._on_open)
        file_menu.addAction(act_open)

        act_save = QAction("내보내기(&E)", self)
        act_save.setShortcut(QKeySequence("Ctrl+E"))
        act_save.triggered.connect(self._on_save)
        file_menu.addAction(act_save)
        file_menu.addSeparator()

        act_quit = QAction("종료(&Q)", self)
        act_quit.setShortcut(QKeySequence.StandardKey.Quit)
        act_quit.triggered.connect(self.close)
        file_menu.addAction(act_quit)

        edit_menu = menubar.addMenu("편집(&E)")
        act_undo = QAction("실행 취소(&U)", self)
        act_undo.setShortcut(QKeySequence.StandardKey.Undo)
        act_undo.triggered.connect(self._on_undo)
        edit_menu.addAction(act_undo)

        act_redo = QAction("다시 실행(&R)", self)
        act_redo.setShortcut(QKeySequence.StandardKey.Redo)
        act_redo.triggered.connect(self._on_redo)
        edit_menu.addAction(act_redo)

        help_menu = menubar.addMenu("도움말(&H)")
        act_help = QAction("사용 설명서(&M)", self)
        act_help.setShortcut(QKeySequence("F1"))
        act_help.triggered.connect(self._show_help)
        help_menu.addAction(act_help)

    # ------------------------------------------------------------------ #
    #  시그널 연결
    # ------------------------------------------------------------------ #
    def _connect_signals(self):
        tb = self._toolbar

        # 파일
        tb.sig_open.connect(self._on_open)
        tb.sig_save.connect(self._on_save)

        # Undo/Redo
        tb.sig_undo.connect(self._on_undo)
        tb.sig_redo.connect(self._on_redo)

        # 모드
        tb.sig_mode_changed.connect(self._on_mode_changed)

        # 배경 제거
        tb.sig_remove_bg_auto.connect(self._on_remove_bg_auto)
        tb.sig_apply_brush.connect(self._on_apply_brush)
        tb.sig_clear_brush.connect(self._canvas_edit.clear_brush_overlay)

        # 크롭
        tb.sig_crop_size_preview.connect(self._on_crop_size_preview)
        tb.sig_reset.connect(self._on_reset)

        # 필터
        tb.sig_filter.connect(self._on_filter)

        # 캔버스 이벤트
        self._canvas_edit.crop_selected.connect(self._on_crop_drag)
        # GrabCut: 드래그 완료 즉시 자동 적용
        self._canvas_edit.grabcut_selected.connect(self._on_grabcut_auto_apply)
        # 다각형: 닫힘 즉시 적용
        self._canvas_edit.polygon_closed.connect(self._on_polygon_cut)

        # 크기 지정 크롭: 더블클릭/Enter 확정 시 적용
        self._canvas_edit.crop_size_committed.connect(self._on_crop_size_committed)

        # 줌 변경 → 상태바 표시
        self._canvas_edit.zoom_changed.connect(
            lambda z: self._status.set_zoom(z)
        )

        # 브러시 크기 슬라이더
        tb.brush_slider.valueChanged.connect(self._canvas_edit.set_brush_size)

        # 도움말
        tb.sig_help.connect(self._show_help)

        # 캔버스 드롭 → 기본 이미지 or 오버레이
        self._canvas_edit.file_dropped.connect(self._on_canvas_file_dropped)

        # 줌 버튼
        tb.sig_zoom_in.connect(self._canvas_edit.zoom_in)
        tb.sig_zoom_out.connect(self._canvas_edit.zoom_out)
        tb.sig_zoom_fit.connect(self._canvas_edit.reset_zoom)

        # 오버레이 변경 → 레이어 패널 갱신
        self._canvas_edit.overlays_changed.connect(self._refresh_layer_panel)
        self._canvas_edit.overlay_selected.connect(self._refresh_layer_panel)

        # 레이어 패널 신호
        lp = self._layer_panel
        lp.sig_add_image.connect(self._on_add_overlay_dialog)
        lp.sig_select.connect(self._canvas_edit.select_overlay)
        lp.sig_delete.connect(self._on_delete_overlay)
        lp.sig_toggle_vis.connect(self._on_toggle_overlay_vis)
        lp.sig_merge_all.connect(self._on_merge_all_overlays)

    # ------------------------------------------------------------------ #
    #  단축키
    # ------------------------------------------------------------------ #
    def _setup_shortcuts(self):
        shortcuts = [
            ("Escape",      self._on_shortcut_escape),
            ("Return",      self._on_shortcut_enter),
            ("Enter",       self._on_shortcut_enter),
            ("V",           lambda: self._set_tool_mode("none")),   # 이동/선택 모드
            ("A",           self._on_remove_bg_auto),
            ("G",           lambda: self._set_tool_mode("grabcut")),
            ("B",           lambda: self._set_tool_mode("brush")),
            ("C",           lambda: self._set_tool_mode("crop")),
            ("P",           lambda: self._set_tool_mode("polygon")),
            ("Ctrl+R",      self._on_reset),
            # 줌
            ("Ctrl+=",      self._canvas_edit.zoom_in),
            ("Ctrl++",      self._canvas_edit.zoom_in),
            ("Ctrl+-",      self._canvas_edit.zoom_out),
            ("Ctrl+0",      self._canvas_edit.reset_zoom),
        ]
        for key, slot in shortcuts:
            QShortcut(QKeySequence(key), self).activated.connect(slot)

    def _set_tool_mode(self, mode: str):
        """단축키로 모드 전환 — 툴바 버튼과 캔버스를 동기화"""
        self._toolbar.set_mode(mode)
        self._on_mode_changed(mode)

    def _on_shortcut_escape(self):
        self._canvas_edit.cancel_polygon()
        self._set_tool_mode("none")   # 툴바 이동/선택 버튼도 자동 활성화됨
        self._status.set_message("이동 / 선택 모드")

    def _on_shortcut_enter(self):
        """Enter: 다각형 완성 또는 크기 크롭 확정"""
        mode = self._canvas_edit._mode
        if mode == "polygon" and len(self._canvas_edit._poly_image_pts) >= 3:
            self._canvas_edit._close_polygon()
        elif mode == "crop_size":
            self._canvas_edit.commit_crop_size()

    # ------------------------------------------------------------------ #
    #  드래그 앤 드롭
    # ------------------------------------------------------------------ #
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if any(self._is_image_path(u.toLocalFile()) for u in urls):
                event.acceptProposedAction()
                return
        event.ignore()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if self._is_image_path(path):
                # 메인 윈도우 드롭은 항상 기본 이미지로 열기
                self._load_file(path)
                break
        event.acceptProposedAction()

    @staticmethod
    def _is_image_path(path: str) -> bool:
        import os
        return os.path.splitext(path)[1].lower() in _IMAGE_EXTENSIONS

    # ------------------------------------------------------------------ #
    #  공통 파일 로드
    # ------------------------------------------------------------------ #
    def _load_file(self, path: str):
        try:
            img = self._processor.load(path)
            self._canvas_edit.set_image(img)
            self._canvas_edit.set_original_image(self._processor.original_image)
            w, h = self._processor.get_size()
            self._status.set_size(w, h)
            self._status.set_message(f"파일 로드 완료: {path}")
            self._update_edit_state()
            self._do_refresh_layer_panel()   # 기본 이미지 로드 후 레이어 패널 즉시 갱신
        except Exception as e:
            QMessageBox.critical(self, "오류", f"파일을 열 수 없습니다:\n{e}")

    # ------------------------------------------------------------------ #
    #  도움말
    # ------------------------------------------------------------------ #
    def _show_help(self):
        dlg = HelpDialog(self)
        dlg.exec()

    # ------------------------------------------------------------------ #
    #  파일 핸들러
    # ------------------------------------------------------------------ #
    def _on_open(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "이미지 열기", "",
            "이미지 파일 (*.png *.jpg *.jpeg *.bmp *.webp *.tiff *.gif)"
        )
        if path:
            self._load_file(path)

    # ------------------------------------------------------------------ #
    #  레이어 / 오버레이 핸들러
    # ------------------------------------------------------------------ #
    def _on_canvas_file_dropped(self, path: str, pos):
        """캔버스에 파일 드롭 — 기본 이미지가 없으면 열기, 있으면 오버레이로 추가"""
        if not self._processor.has_image:
            self._load_file(path)
        else:
            self._add_overlay(path, pos)

    def _add_overlay(self, path: str, drop_pos=None):
        try:
            from PIL import Image
            pil_img = Image.open(path)
            name = __import__('os').path.basename(path)
            self._canvas_edit.add_overlay(pil_img, name, drop_pos)
            self._status.set_message(f"레이어 추가: {name}")
        except Exception as e:
            QMessageBox.critical(self, "오류", f"이미지를 불러올 수 없습니다:\n{e}")

    def _on_add_overlay_dialog(self):
        if not self._processor.has_image:
            QMessageBox.warning(self, "경고", "먼저 기본 이미지를 열어주세요.")
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "레이어 이미지 추가", "",
            "이미지 파일 (*.png *.jpg *.jpeg *.bmp *.webp *.tiff *.gif)"
        )
        if path:
            self._add_overlay(path)

    def _on_delete_overlay(self, index: int):
        if index == -1:
            # 기본 이미지 삭제
            reply = QMessageBox.question(
                self, "삭제 확인",
                "기본 이미지를 삭제하시겠습니까?\n모든 레이어와 편집 내용이 초기화됩니다.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
            self._canvas_edit.clear_overlays()
            self._canvas_edit.set_base_visible(True)
            self._canvas_edit._pil_image = None
            self._canvas_edit._pixmap = None
            self._canvas_edit._orig_pixmap = None
            self._canvas_edit.update()
            self._processor._original = None
            self._processor._current = None
            self._processor._history.clear()
            self._processor._redo_stack.clear()
            self._do_refresh_layer_panel()
            self._update_edit_state()
            self._status.set_message("기본 이미지를 삭제했습니다.")
        else:
            reply = QMessageBox.question(
                self, "삭제 확인",
                "이 레이어를 삭제하시겠습니까?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
            self._canvas_edit.remove_overlay(index)
            self._status.set_message("레이어 삭제")

    def _on_toggle_overlay_vis(self, index: int, visible: bool):
        if index == -1:
            self._canvas_edit.set_base_visible(visible)
        else:
            self._canvas_edit.set_overlay_visible(index, visible)
        self._canvas_edit.update()

    def _on_merge_all_overlays(self):
        overlays = self._canvas_edit.get_overlays()
        if not overlays:
            QMessageBox.information(self, "알림", "병합할 레이어가 없습니다.")
            return
        if not self._processor.has_image:
            return
        try:
            for ov in overlays:
                if ov.get('visible', True):
                    self._processor.merge_overlay(ov['pil'], ov['x'], ov['y'])
            img = self._processor.current_image
            self._canvas_edit.set_image(img)
            self._canvas_edit.clear_overlays()
            self._status.set_message(f"레이어 {len(overlays)}개 병합 완료")
            self._update_edit_state()
        except Exception as e:
            QMessageBox.critical(self, "병합 오류", str(e))

    def _refresh_layer_panel(self, *_):
        self._layer_refresh_timer.start()

    def _do_refresh_layer_panel(self):
        overlays = self._canvas_edit.get_overlays()
        active = self._canvas_edit._active_overlay
        self._layer_panel.update_layers(overlays, active)

    @staticmethod
    def _get_icon_path() -> str | None:
        candidates = [
            os.path.join(os.path.dirname(__file__), '..', 'images', 'main.png'),
            os.path.join(getattr(sys, '_MEIPASS', ''), 'images', 'main.png'),
        ]
        for p in candidates:
            if os.path.isfile(p):
                return os.path.normpath(p)
        return None

    def _on_save(self):
        if not self._processor.has_image:
            QMessageBox.warning(self, "경고", "저장할 이미지가 없습니다.")
            return
        dlg = ExportDialog(self)
        if dlg.exec():
            path, fmt = dlg.get_result()
            if path and fmt:
                try:
                    self._processor.save(path, fmt)
                    self._status.set_message(f"저장 완료: {path}")
                except Exception as e:
                    QMessageBox.critical(self, "저장 오류", str(e))

    # ------------------------------------------------------------------ #
    #  Undo / Redo
    # ------------------------------------------------------------------ #
    def _on_undo(self):
        if self._processor.undo():
            self._refresh_edit_canvas()
            self._status.set_message("실행 취소")
        self._update_edit_state()

    def _on_redo(self):
        if self._processor.redo():
            self._refresh_edit_canvas()
            self._status.set_message("다시 실행")
        self._update_edit_state()

    # ------------------------------------------------------------------ #
    #  모드 변경
    # ------------------------------------------------------------------ #
    def _on_mode_changed(self, mode: str):
        self._canvas_edit.set_mode(mode)
        mode_labels = {
            "none": "기본 모드",
            "crop": "드래그로 크롭 영역을 선택하세요",
            "grabcut": "GrabCut 영역을 드래그로 선택하세요",
            "brush": "지울 영역을 브러시로 칠하세요 → '브러시 적용' 클릭",
        }
        self._status.set_message(mode_labels.get(mode, ""))

    # ------------------------------------------------------------------ #
    #  배경 제거
    # ------------------------------------------------------------------ #
    def _on_remove_bg_auto(self):
        if not self._processor.has_image:
            QMessageBox.warning(self, "경고", "이미지를 먼저 불러오세요.")
            return
        self._status.set_message("AI 배경 제거 중... (시간이 걸릴 수 있습니다)")
        self.setEnabled(False)

        self._thread = QThread()
        self._worker = BgRemoveWorker(self._processor)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_bg_removed)
        self._worker.error.connect(self._on_bg_error)
        self._worker.finished.connect(self._thread.quit)
        self._worker.error.connect(self._thread.quit)
        self._thread.start()

    def _on_bg_removed(self, img):
        self.setEnabled(True)
        self._canvas_edit.set_image(img)
        self._status.set_message("배경 제거 완료")
        self._update_edit_state()

    def _on_bg_error(self, msg: str):
        self.setEnabled(True)
        QMessageBox.critical(self, "배경 제거 오류", msg)
        self._status.set_message("배경 제거 실패")

    def _on_grabcut_auto_apply(self, x: int, y: int, w: int, h: int):
        """GrabCut 드래그 완료 즉시 자동 적용"""
        if not self._processor.has_image:
            return
        if w < 5 or h < 5:
            return
        self._status.set_message("GrabCut 처리 중...")
        try:
            img = self._processor.remove_background_grabcut((x, y, w, h))
            self._canvas_edit.set_image(img)
            self._status.set_message(f"GrabCut 완료: ({x},{y}) {w}×{h}")
            self._update_edit_state()
            self._set_tool_mode("none")   # 작업 후 이동/선택 모드로 자동 복귀
        except Exception as e:
            QMessageBox.critical(self, "오류", str(e))
            self._status.set_message("GrabCut 실패")

    def _on_polygon_cut(self, points: list):
        """다각형 닫힘 즉시 적용"""
        if not self._processor.has_image:
            return
        try:
            img = self._processor.crop_by_polygon(points)
            self._canvas_edit.set_image(img)
            self._status.set_message(f"다각형 선택 완료: 꼭짓점 {len(points)}개")
            self._update_edit_state()
            self._set_tool_mode("none")   # 작업 후 이동/선택 모드로 자동 복귀
        except Exception as e:
            QMessageBox.critical(self, "오류", str(e))

    def _on_apply_brush(self):
        if not self._processor.has_image:
            QMessageBox.warning(self, "경고", "이미지를 먼저 불러오세요.")
            return
        mask = self._canvas_edit._brush_mask
        if mask is None or not (mask == 255).any():
            QMessageBox.warning(self, "경고", "먼저 지울 영역을 브러시로 칠하세요.")
            return
        try:
            img = self._processor.apply_brush_mask(mask)
            self._canvas_edit.set_image(img)
            self._status.set_message("브러시 마스크 적용 완료")
            self._update_edit_state()
        except Exception as e:
            QMessageBox.critical(self, "오류", str(e))

    # ------------------------------------------------------------------ #
    #  크롭
    # ------------------------------------------------------------------ #
    def _on_crop_drag(self, x: int, y: int, w: int, h: int):
        if not self._processor.has_image:
            return
        try:
            img = self._processor.crop_by_rect(x, y, w, h)
            self._canvas_edit.set_image(img)
            nw, nh = self._processor.get_size()
            self._status.set_size(nw, nh)
            self._status.set_message(f"크롭 완료: {nw}×{nh}")
            self._update_edit_state()
        except Exception as e:
            QMessageBox.critical(self, "오류", str(e))

    def _on_crop_size_preview(self, width: int, height: int):
        """크기 지정 크롭 미리보기 모드 진입"""
        if not self._processor.has_image:
            QMessageBox.warning(self, "경고", "이미지를 먼저 불러오세요.")
            return
        self._toolbar.set_mode("crop_size")
        self._canvas_edit.set_crop_size_preview(width, height)
        self._status.set_message(
            f"크롭 박스({width}×{height})를 드래그로 위치 조정 후 더블클릭 또는 Enter로 적용"
        )

    def _on_crop_size_committed(self, x: int, y: int, w: int, h: int):
        """크기 지정 크롭 확정 적용"""
        if not self._processor.has_image:
            return
        try:
            img = self._processor.crop_by_rect(x, y, w, h)
            self._canvas_edit.set_image(img)
            self._canvas_edit.set_mode("none")
            self._toolbar.set_mode("none")
            nw, nh = self._processor.get_size()
            self._status.set_size(nw, nh)
            self._status.set_message(f"크롭 완료: {nw}×{nh}")
            self._update_edit_state()
        except Exception as e:
            QMessageBox.critical(self, "오류", str(e))

    # ------------------------------------------------------------------ #
    #  필터
    # ------------------------------------------------------------------ #
    def _on_filter(self, name: str):
        if not self._processor.has_image:
            QMessageBox.warning(self, "경고", "이미지를 먼저 불러오세요.")
            return
        try:
            img = self._processor.apply_filter(name)
            self._canvas_edit.set_image(img)
            self._status.set_message(f"필터 적용: {name}")
            self._update_edit_state()
        except Exception as e:
            QMessageBox.critical(self, "오류", str(e))

    # ------------------------------------------------------------------ #
    #  초기화
    # ------------------------------------------------------------------ #
    def _on_reset(self):
        if not self._processor.has_image:
            return
        self._processor.reset_to_original()
        self._canvas_edit.set_image(self._processor.current_image)
        w, h = self._processor.get_size()
        self._status.set_size(w, h)
        self._status.set_message("원본으로 복원했습니다.")
        self._update_edit_state()

    # ------------------------------------------------------------------ #
    #  내부 유틸
    # ------------------------------------------------------------------ #
    def _refresh_edit_canvas(self):
        if self._processor.current_image:
            self._canvas_edit.set_image(self._processor.current_image)
            w, h = self._processor.get_size()
            self._status.set_size(w, h)

    def _update_edit_state(self):
        self._toolbar.set_undo_enabled(self._processor.can_undo())
        self._toolbar.set_redo_enabled(self._processor.can_redo())


# ------------------------------------------------------------------ #
#  도움말 대화상자
# ------------------------------------------------------------------ #
class HelpDialog(QDialog):
    _CONTENT = """
<style>
  body  { background:#1e1e2e; color:#cdd6f4; font-family:sans-serif; font-size:13px; margin:16px; }
  h2    { color:#89b4fa; border-bottom:1px solid #313244; padding-bottom:6px; }
  h3    { color:#cba6f7; margin-top:18px; margin-bottom:4px; }
  table { border-collapse:collapse; width:100%; margin-bottom:10px; }
  td    { padding:5px 8px; vertical-align:top; }
  td:first-child { color:#a6e3a1; white-space:nowrap; font-weight:bold; width:160px; }
  tr:nth-child(even) td { background:#181825; }
  .tip  { background:#313244; border-left:3px solid #89b4fa;
          padding:6px 10px; border-radius:4px; margin-top:12px; }
  .kbd  { background:#313244; border:1px solid #45475a; border-radius:3px;
          padding:1px 5px; font-size:12px; color:#f9e2af; }
  .new  { color:#a6e3a1; font-size:10px; font-weight:bold;
          background:#1e3a2e; border:1px solid #2d5a3d; border-radius:3px; padding:1px 5px; }
</style>

<h2>Image Editor Pro — 사용 설명서</h2>

<h3>⌨ 단축키 모음</h3>
<table>
  <tr><td><span class="kbd">Ctrl+O</span></td><td>이미지 열기</td></tr>
  <tr><td><span class="kbd">Ctrl+E</span></td><td>내보내기 / 저장</td></tr>
  <tr><td><span class="kbd">Ctrl+Z</span></td><td>실행 취소</td></tr>
  <tr><td><span class="kbd">Ctrl+Y</span></td><td>다시 실행</td></tr>
  <tr><td><span class="kbd">Ctrl+R</span></td><td>원본으로 복원</td></tr>
  <tr><td><span class="kbd">A</span></td><td>AI 자동 배경 제거</td></tr>
  <tr><td><span class="kbd">G</span></td><td>GrabCut 모드</td></tr>
  <tr><td><span class="kbd">B</span></td><td>브러시 마스크 모드</td></tr>
  <tr><td><span class="kbd">C</span></td><td>크롭 드래그 모드</td></tr>
  <tr><td><span class="kbd">P</span></td><td>다각형 선택 모드</td></tr>
  <tr><td><span class="kbd">Enter</span></td><td>다각형 완성 (현재 꼭짓점으로 닫기)</td></tr>
  <tr><td><span class="kbd">Escape</span></td><td>현재 모드 초기화</td></tr>
  <tr><td><span class="kbd">F1</span></td><td>사용 설명서 열기</td></tr>
</table>

<h3>📁 파일</h3>
<table>
  <tr><td>이미지 열기</td><td>PNG, JPG, BMP, WEBP, TIFF, GIF 파일을 불러옵니다.</td></tr>
  <tr><td>내보내기 / 저장</td><td>편집된 이미지를 PNG·JPG·BMP·PDF 등으로 저장합니다.<br>투명 배경은 반드시 PNG로 저장하세요.</td></tr>
  <tr><td>드래그 앤 드롭</td><td>이미지 파일을 <b>앱 창에 드래그</b>하면 바로 열립니다.<br>탐색기에서 <b>exe 파일 위에 이미지를 드롭</b>해도 자동으로 열립니다.</td></tr>
</table>

<h3>🪄 배경 제거</h3>
<table>
  <tr><td>자동 배경 제거 (AI) <span class="kbd">A</span></td><td>AI(rembg) 모델로 배경을 한 번에 제거합니다.<br>첫 실행 시 AI 모델을 다운로드하므로 시간이 걸립니다.</td></tr>
  <tr><td>GrabCut 선택 <span class="kbd">G</span></td>
      <td>① <b>G</b>키 또는 버튼 클릭<br>
          ② 편집 이미지에서 <b>남길 물체를 포함하도록 드래그</b> (주황 박스)<br>
          ③ <b>드래그를 놓으면 자동으로 배경 제거</b> — 별도 적용 버튼 없음<br>
          ④ 여러 번 반복하여 정밀하게 다듬을 수 있습니다</td></tr>
  <tr><td>브러시 마스크 <span class="kbd">B</span></td>
      <td>① <b>B</b>키 또는 버튼 클릭<br>
          ② 지울 영역을 붓으로 칠합니다 (빨간 오버레이)<br>
          ③ 크기 슬라이더로 브러시 굵기 조절<br>
          ④ <b>브러시 적용</b> 버튼 클릭 → 칠한 영역이 투명해짐<br>
          ⑤ <b>초기화</b>로 브러시 영역을 다시 시작할 수 있습니다</td></tr>
</table>

<h3>✂ 크롭 / 선택</h3>
<table>
  <tr><td>드래그로 선택 <span class="kbd">C</span></td>
      <td>이미지 위에서 드래그 → 파란 박스 영역으로 즉시 크롭됩니다</td></tr>
  <tr><td>다각형 선택 <span class="new">NEW</span> <span class="kbd">P</span></td>
      <td>① <b>P</b>키 또는 버튼 클릭<br>
          ② 클릭으로 꼭짓점을 하나씩 추가합니다<br>
          ③ 완성 방법 (택1):<br>
          &nbsp;&nbsp;• <b>시작점(빨간 점)</b> 클릭<br>
          &nbsp;&nbsp;• <b>더블클릭</b><br>
          &nbsp;&nbsp;• <b>Enter</b>키<br>
          ④ 다각형 내부만 남기고 나머지가 투명해집니다<br>
          ⑤ <b>ESC</b>키로 취소할 수 있습니다</td></tr>
  <tr><td>크기로 크롭</td><td>W·H 값을 입력하고 버튼 클릭 → 이미지 중앙 기준 크롭</td></tr>
</table>

<h3>🎨 필터</h3>
<table>
  <tr><td>grayscale</td><td>흑백으로 변환합니다</td></tr>
  <tr><td>blur</td><td>이미지를 부드럽게 흐립니다</td></tr>
  <tr><td>sharpen</td><td>이미지를 선명하게 만듭니다</td></tr>
  <tr><td>brightness</td><td>밝기를 높입니다</td></tr>
  <tr><td>contrast</td><td>대비(명암)를 높입니다</td></tr>
  <tr><td>sepia</td><td>빈티지 세피아 톤으로 변환합니다</td></tr>
</table>

<h3>🔄 기타</h3>
<table>
  <tr><td>원본으로 복원 <span class="kbd">Ctrl+R</span></td><td>모든 편집을 취소하고 처음 불러온 원본으로 돌아갑니다</td></tr>
</table>

<div class="tip">
  <b>💡 활용 팁</b><br>
  • 투명 배경 결과는 <b>PNG</b>로 저장해야 투명도가 유지됩니다.<br>
  • AI 자동 제거 후 GrabCut / 브러시로 세밀하게 다듬으면 더 깔끔한 결과를 얻을 수 있습니다.<br>
  • 다각형 선택은 복잡한 형태의 오려내기에 유용합니다.<br>
  • 실수했을 때는 <span class="kbd">Ctrl+Z</span>로 언제든지 되돌릴 수 있습니다.
</div>
"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("사용 설명서")
        self.resize(640, 580)
        self.setStyleSheet("background-color: #1e1e2e; color: #cdd6f4;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 12)

        browser = QTextBrowser()
        browser.setOpenExternalLinks(False)
        browser.setStyleSheet("""
            QTextBrowser {
                background-color: #1e1e2e;
                color: #cdd6f4;
                border: none;
                font-size: 13px;
            }
            QScrollBar:vertical { background: #181825; width: 8px; }
            QScrollBar::handle:vertical { background: #45475a; border-radius: 4px; }
        """)
        browser.setHtml(self._CONTENT)
        layout.addWidget(browser)

        btn_close = QPushButton("닫기")
        btn_close.setFixedWidth(100)
        btn_close.setStyleSheet("""
            QPushButton {
                background-color: #313244; color: #cdd6f4;
                border: 1px solid #45475a; border-radius: 6px; padding: 6px 14px;
            }
            QPushButton:hover { background-color: #45475a; }
        """)
        btn_close.clicked.connect(self.accept)

        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 12, 0)
        row_layout.addStretch()
        row_layout.addWidget(btn_close)
        layout.addWidget(row)
