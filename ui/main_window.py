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
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QObject, QTimer, QPoint
from PyQt6.QtGui import QAction, QKeySequence, QShortcut, QIcon

from core.image_processor import ImageProcessor
from ui.canvas import ImageCanvas
from ui.toolbar import Toolbar
from ui.status_bar import StatusBar
from ui.export_dialog import ExportDialog
from ui.layer_panel import LayerPanel
from ui.new_document_dialog import NewDocumentDialog
from ui.quick_tool_panel import QuickToolPanel


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
        self._current_tool_color: tuple = (0, 0, 0, 255)   # 색상 도구 현재 색
        self._color_brush_pending_mask = None               # 색상 브러시 누적 마스크
        self._bg_remove_target_idx: int = -1               # AI 배경 제거 대상 오버레이 인덱스
        self._last_text_settings: dict | None = None        # 마지막 텍스트 서식 설정 (재사용)
        self._pending_text_rect: tuple | None = None         # 텍스트 드래그 영역 임시 저장

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
        else:
            # 시작 시 새 문서 다이얼로그 표시
            self._show_new_document_dialog()

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

        # 퀵 도구 패널 (캔버스 위에 오버레이로 표시, 드래그 가능)
        self._quick_panel = QuickToolPanel(central)
        self._quick_panel.raise_()


    def _make_preview_panel(self, title: str) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background-color: #1e1e2e;")
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 헤더 바 (제목 + 작업 크기 표시)
        header_bar = QWidget()
        header_bar.setStyleSheet(
            "background-color: #181825; border-bottom: 1px solid #313244;"
        )
        h_lay = QHBoxLayout(header_bar)
        h_lay.setContentsMargins(8, 0, 12, 0)
        h_lay.setSpacing(0)

        lbl = QLabel(f"  {title}")
        lbl.setStyleSheet(
            "background: transparent; color: #a6adc8; font-size: 11px;"
            "font-weight: bold; letter-spacing: 1px; padding: 6px 0;"
        )
        h_lay.addWidget(lbl)
        h_lay.addStretch()

        self._workspace_size_lbl = QLabel("")
        self._workspace_size_lbl.setStyleSheet(
            "background: transparent; color: #a6e3a1; font-size: 11px;"
            "font-weight: bold; padding: 6px 0;"
        )
        h_lay.addWidget(self._workspace_size_lbl)

        layout.addWidget(header_bar)
        return w

    # ------------------------------------------------------------------ #
    #  메뉴바
    # ------------------------------------------------------------------ #
    def _build_menu(self):
        menubar = self.menuBar()

        file_menu = menubar.addMenu("파일(&F)")

        act_new = QAction("새 문서(&N)", self)
        act_new.setShortcut(QKeySequence("Ctrl+N"))
        act_new.triggered.connect(self._show_new_document_dialog)
        file_menu.addAction(act_new)

        file_menu.addSeparator()

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

        edit_menu.addSeparator()

        self._act_quick_tool = QAction("퀵 도구 패널 표시(&Q)", self)
        self._act_quick_tool.setCheckable(True)
        self._act_quick_tool.setChecked(True)
        self._act_quick_tool.triggered.connect(self._toggle_quick_panel)
        edit_menu.addAction(self._act_quick_tool)

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
        # 브러시 마스크: 마우스 릴리즈 시 자동 적용
        self._canvas_edit.brush_stroke_done.connect(self._auto_apply_brush)

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

        # 색상 도구
        self._canvas_edit.color_sampled.connect(self._on_color_sampled)
        self._canvas_edit.fill_applied.connect(self._on_fill_applied)
        # 색상 브러시: 마우스 릴리즈 시 자동 적용
        self._canvas_edit.color_brush_done.connect(self._on_color_brush_done)
        tb.sig_color_changed.connect(self._on_tool_color_changed)

        # 도형 그리기 / AI 인페인팅
        self._canvas_edit.shape_committed.connect(self._on_shape_committed)
        self._canvas_edit.inpaint_committed.connect(self._on_inpaint_committed)

        # 텍스트 삽입 (인라인 에디터가 canvas 내부에서 처리 후 시그널 발생)
        self._canvas_edit.text_committed.connect(self._on_text_committed)
        self._canvas_edit.text_edit_committed.connect(self._on_text_edit_committed)
        self._canvas_edit.text_overlay_resized.connect(self._on_text_overlay_resized)

        # 퀵 도구 패널
        qp = self._quick_panel
        qp.sig_mode_changed.connect(self._set_tool_mode)
        qp.sig_action.connect(self._on_quick_action)
        qp.sig_closed.connect(lambda: self._act_quick_tool.setChecked(False))

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
        lp.sig_reset_size.connect(self._on_overlay_reset_size)
        lp.sig_fit_to_canvas.connect(self._on_overlay_fit_canvas)

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
            ("T",           lambda: self._set_tool_mode("text")),
            ("E",           lambda: self._set_tool_mode("select")),  # 선택/편집 모드
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
        """단축키로 모드 전환 — 툴바·퀵패널·캔버스를 동기화"""
        self._toolbar.set_mode(mode)
        self._quick_panel.set_mode(mode)
        self._on_mode_changed(mode)

    # ------------------------------------------------------------------ #
    #  새 문서
    # ------------------------------------------------------------------ #
    def _show_new_document_dialog(self):
        """새 문서 다이얼로그 표시 → 선택한 크기로 빈 캔버스 생성"""
        dlg = NewDocumentDialog(self)
        if dlg.exec():
            w, h = dlg.get_size()
            img = self._processor.new_blank(w, h, (0, 0, 0, 0))
            self._canvas_edit.set_image(img)
            self._canvas_edit.set_original_image(None)  # 새 문서는 미니맵 표시 없음
            self._canvas_edit.clear_overlays()
            self._status.set_size(w, h)
            self._status.set_message(f"새 문서: {w} × {h} px")
            self._workspace_size_lbl.setText(f"작업 크기: {w} × {h} px")
            self._update_edit_state()
            self._do_refresh_layer_panel()

    # ------------------------------------------------------------------ #
    #  퀵 도구 패널 액션
    # ------------------------------------------------------------------ #
    def _on_quick_action(self, action: str):
        if action == "undo":
            self._on_undo()
        elif action == "redo":
            self._on_redo()
        elif action == "remove_bg":
            self._on_remove_bg_auto()
        elif action == "zoom_in":
            self._canvas_edit.zoom_in()
        elif action == "zoom_out":
            self._canvas_edit.zoom_out()
        elif action == "zoom_fit":
            self._canvas_edit.reset_zoom()

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
    #  퀵 패널 초기 위치 지정
    # ------------------------------------------------------------------ #
    def showEvent(self, event):
        super().showEvent(event)
        self._reposition_quick_panel()

    def _reposition_quick_panel(self):
        """캔버스 좌상단 기준으로 퀵 패널 위치 설정"""
        canvas_pos = self._canvas_edit.mapTo(self.centralWidget(), QPoint(0, 0))
        self._quick_panel.move(canvas_pos.x() + 10, canvas_pos.y() + 10)
        self._quick_panel.raise_()

    def _toggle_quick_panel(self, checked: bool):
        """편집 메뉴에서 퀵 도구 패널 표시/숨김 토글"""
        if checked:
            self._reposition_quick_panel()
            self._quick_panel.show()
            self._quick_panel.raise_()
        else:
            self._quick_panel.hide()

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
                # 파일 크기의 새 캔버스 생성 후 첫 번째 레이어로 추가
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
            from PIL import Image as _PIL
            pil_img = _PIL.open(path).convert("RGBA")
            w, h = pil_img.size
            # 파일 크기의 투명 캔버스 생성 (작업 공간)
            canvas_img = self._processor.new_blank(w, h, (0, 0, 0, 0))
            self._canvas_edit.set_image(canvas_img)
            self._canvas_edit.set_original_image(pil_img)   # 미니맵 원본
            self._canvas_edit.clear_overlays()
            # 파일을 첫 번째 레이어로 추가
            name = os.path.basename(path)
            self._canvas_edit.add_overlay(pil_img, name)
            self._status.set_size(w, h)
            self._workspace_size_lbl.setText(f"작업 크기: {w} × {h} px")
            self._status.set_message(f"파일 로드 완료: {path}")
            self._update_edit_state()
            self._do_refresh_layer_panel()
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
        """캔버스에 파일 드롭 — 항상 레이어로 추가 (작업 공간이 없으면 파일 크기로 생성)"""
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

    def _on_overlay_reset_size(self):
        """선택한 레이어를 원본 크기로 복원"""
        idx = self._canvas_edit._active_overlay
        if idx >= 0:
            self._canvas_edit.reset_overlay_size(idx)
            self._status.set_message("레이어 원본 크기로 복원됨")
        else:
            self._status.set_message("크기를 복원할 레이어를 먼저 선택하세요.")

    def _on_overlay_fit_canvas(self):
        """선택한 레이어를 캔버스 크기에 맞춤"""
        idx = self._canvas_edit._active_overlay
        if idx >= 0:
            self._canvas_edit.fit_overlay_to_canvas(idx)
            self._status.set_message("레이어를 캔버스 크기에 맞춤")
        else:
            self._status.set_message("크기를 맞출 레이어를 먼저 선택하세요.")

    def _on_add_overlay_dialog(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "레이어 이미지 추가", "",
            "이미지 파일 (*.png *.jpg *.jpeg *.bmp *.webp *.tiff *.gif)"
        )
        if path:
            if not self._processor.has_image:
                self._load_file(path)
            else:
                self._add_overlay(path)

    def _on_delete_overlay(self, index: int):
        if index < 0:
            return
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
        if index >= 0:
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
            composited = self._get_composited_image()
            if composited:
                self._processor.load_pil(composited)
                self._canvas_edit.set_image(self._processor.current_image)
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
        if not self._processor.has_image and not self._canvas_edit.get_overlays():
            QMessageBox.warning(self, "경고", "저장할 이미지가 없습니다.")
            return
        dlg = ExportDialog(self)
        if dlg.exec():
            path, fmt = dlg.get_result()
            if path and fmt:
                try:
                    composited = self._get_composited_image()
                    if composited is None:
                        QMessageBox.warning(self, "경고", "저장할 이미지가 없습니다.")
                        return
                    tmp = ImageProcessor()
                    tmp.load_pil(composited)
                    tmp.save(path, fmt)
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
        # 텍스트 모드 진입 시 이전 서식 설정을 인라인 에디터에 미리 전달
        if mode == "text" and self._last_text_settings:
            self._canvas_edit._inline_editor._bar.load_settings(self._last_text_settings)
        mode_labels = {
            "none":          "기본 모드",
            "crop":          "드래그로 크롭 영역을 선택하세요",
            "grabcut":       "GrabCut 영역을 드래그로 선택하세요",
            "brush":         "지울 영역을 브러시로 칠하세요 → '브러시 적용' 클릭",
            "pipette":       "색을 추출할 픽셀을 클릭하세요",
            "fill":          "채울 영역을 클릭하세요 (현재 색상으로 채우기)",
            "color_brush":   "색칠할 영역을 브러시로 칠하세요 → '브러시 적용' 클릭",
            "shape_rect":    "드래그로 점선 사각형 영역을 지정하세요",
            "shape_ellipse": "드래그로 점선 원/타원 영역을 지정하세요",
            "inpaint":       "드래그로 AI 채우기 영역을 선택하세요 — 드래그 완료 시 자동 적용",
            "text":          "드래그로 텍스트 박스 영역을 지정하세요",
            "select":        "레이어 클릭으로 편집 — 텍스트 클릭 시 수정, 이미지 클릭 시 선택",
        }
        self._status.set_message(mode_labels.get(mode, ""))

    # ------------------------------------------------------------------ #
    #  레이어 편집 헬퍼
    # ------------------------------------------------------------------ #
    def _get_active_overlay_idx(self) -> int:
        """현재 선택된 오버레이 인덱스 (-1 = 없음)"""
        return self._canvas_edit._active_overlay

    def _apply_to_overlay(self, idx: int, op_fn) -> bool:
        """선택된 오버레이에 처리 함수 적용. op_fn: ImageProcessor → Image"""
        overlays = self._canvas_edit.get_overlays()
        if not (0 <= idx < len(overlays)):
            return False
        tmp = ImageProcessor()
        tmp.load_pil(overlays[idx]['pil'])
        result = op_fn(tmp)
        if result is not None:
            self._canvas_edit.update_overlay_image(idx, result)
            return True
        return False

    def _translate_to_overlay_coords(self, ov: dict, x: int, y: int, w: int, h: int):
        """워크스페이스 좌표를 오버레이 로컬 픽셀 좌표로 변환"""
        ox, oy = ov['x'], ov['y']
        dw, dh = ov['disp_w'], ov['disp_h']
        pw, ph = ov['pil'].width, ov['pil'].height
        sx = pw / dw if dw > 0 else 1.0
        sy = ph / dh if dh > 0 else 1.0
        x_l = int((x - ox) * sx)
        y_l = int((y - oy) * sy)
        w_l = int(w * sx)
        h_l = int(h * sy)
        x_l = max(0, min(x_l, pw - 1))
        y_l = max(0, min(y_l, ph - 1))
        w_l = max(1, min(w_l, pw - x_l))
        h_l = max(1, min(h_l, ph - y_l))
        return x_l, y_l, w_l, h_l

    def _translate_brush_mask_to_overlay(self, mask, ov: dict):
        """워크스페이스 크기 브러시 마스크를 오버레이 로컬 크기로 변환"""
        import cv2
        import numpy as np
        ox, oy = ov['x'], ov['y']
        dw, dh = ov['disp_w'], ov['disp_h']
        pw, ph = ov['pil'].width, ov['pil'].height
        mh, mw = mask.shape[:2]
        x1 = max(0, ox)
        y1 = max(0, oy)
        x2 = min(mw, ox + dw)
        y2 = min(mh, oy + dh)
        if x2 <= x1 or y2 <= y1:
            return np.zeros((ph, pw), dtype=np.uint8)
        crop = mask[y1:y2, x1:x2]
        return cv2.resize(crop, (pw, ph), interpolation=cv2.INTER_NEAREST)

    def _crop_overlay(self, idx: int, x: int, y: int, w: int, h: int):
        """선택된 오버레이를 워크스페이스 기준 사각형으로 크롭"""
        overlays = self._canvas_edit.get_overlays()
        if not (0 <= idx < len(overlays)):
            return
        ov = overlays[idx]
        ox, oy = ov['x'], ov['y']
        dw, dh = ov['disp_w'], ov['disp_h']
        pw, ph = ov['pil'].width, ov['pil'].height
        sx = pw / dw if dw > 0 else 1.0
        sy = ph / dh if dh > 0 else 1.0
        ix1 = max(ox, x)
        iy1 = max(oy, y)
        ix2 = min(ox + dw, x + w)
        iy2 = min(oy + dh, y + h)
        if ix2 <= ix1 or iy2 <= iy1:
            self._status.set_message("크롭 영역이 레이어와 겹치지 않습니다.")
            return
        lx1 = int((ix1 - ox) * sx)
        ly1 = int((iy1 - oy) * sy)
        lx2 = int((ix2 - ox) * sx)
        ly2 = int((iy2 - oy) * sy)
        new_pil = ov['pil'].crop((lx1, ly1, lx2, ly2))
        ov['x'] = ix1
        ov['y'] = iy1
        self._canvas_edit.update_overlay_image(idx, new_pil)
        self._status.set_message(f"레이어 크롭 완료: {new_pil.width}×{new_pil.height}")

    def _get_composited_image(self):
        """보이는 모든 레이어를 기본 캔버스에 합성한 PIL 이미지 반환"""
        if not self._processor.has_image:
            return None
        from PIL import Image as _PIL
        base = self._processor.current_image.copy().convert("RGBA")
        for ov in self._canvas_edit.get_overlays():
            if not ov.get('visible', True):
                continue
            pil = ov['pil'].convert("RGBA")
            if ov['disp_w'] != pil.width or ov['disp_h'] != pil.height:
                pil = pil.resize((ov['disp_w'], ov['disp_h']), _PIL.LANCZOS)
            base.paste(pil, (ov['x'], ov['y']), pil)
        return base

    # ------------------------------------------------------------------ #
    #  배경 제거
    # ------------------------------------------------------------------ #
    def _on_remove_bg_auto(self):
        idx = self._get_active_overlay_idx()
        overlays = self._canvas_edit.get_overlays()
        if idx >= 0 and idx < len(overlays):
            tmp = ImageProcessor()
            tmp.load_pil(overlays[idx]['pil'])
            self._bg_remove_target_idx = idx
            proc = tmp
        elif self._processor.has_image:
            self._bg_remove_target_idx = -1
            proc = self._processor
        else:
            QMessageBox.warning(self, "경고", "이미지를 먼저 불러오세요.")
            return
        self._status.set_message("AI 배경 제거 중... (시간이 걸릴 수 있습니다)")
        self.setEnabled(False)

        self._thread = QThread()
        self._worker = BgRemoveWorker(proc)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_bg_removed)
        self._worker.error.connect(self._on_bg_error)
        self._worker.finished.connect(self._thread.quit)
        self._worker.error.connect(self._thread.quit)
        self._thread.start()

    def _on_bg_removed(self, img):
        self.setEnabled(True)
        idx = self._bg_remove_target_idx
        if idx >= 0:
            self._canvas_edit.update_overlay_image(idx, img)
            self._status.set_message("레이어 배경 제거 완료")
            self._do_refresh_layer_panel()
        else:
            self._canvas_edit.set_image(img)
            self._status.set_message("배경 제거 완료")
            self._update_edit_state()
        self._bg_remove_target_idx = -1

    def _on_bg_error(self, msg: str):
        self.setEnabled(True)
        QMessageBox.critical(self, "배경 제거 오류", msg)
        self._status.set_message("배경 제거 실패")

    def _on_grabcut_auto_apply(self, x: int, y: int, w: int, h: int):
        """GrabCut 드래그 완료 즉시 자동 적용"""
        if w < 5 or h < 5:
            return
        self._status.set_message("GrabCut 처리 중...")
        idx = self._get_active_overlay_idx()
        try:
            if idx >= 0:
                overlays = self._canvas_edit.get_overlays()
                if 0 <= idx < len(overlays):
                    ov = overlays[idx]
                    lx, ly, lw, lh = self._translate_to_overlay_coords(ov, x, y, w, h)
                    if self._apply_to_overlay(idx, lambda p: p.remove_background_grabcut((lx, ly, lw, lh))):
                        self._status.set_message(f"레이어 GrabCut 완료: {lw}×{lh}")
            elif self._processor.has_image:
                img = self._processor.remove_background_grabcut((x, y, w, h))
                self._canvas_edit.set_image(img)
                self._status.set_message(f"GrabCut 완료: ({x},{y}) {w}×{h}")
                self._update_edit_state()
        except Exception as e:
            QMessageBox.critical(self, "오류", str(e))
            self._status.set_message("GrabCut 실패")

    def _on_polygon_cut(self, points: list):
        """다각형 닫힘 즉시 적용"""
        idx = self._get_active_overlay_idx()
        try:
            if idx >= 0:
                overlays = self._canvas_edit.get_overlays()
                if 0 <= idx < len(overlays):
                    ov = overlays[idx]
                    ox, oy = ov['x'], ov['y']
                    dw, dh = ov['disp_w'], ov['disp_h']
                    pw, ph = ov['pil'].width, ov['pil'].height
                    sx = pw / dw if dw > 0 else 1.0
                    sy = ph / dh if dh > 0 else 1.0
                    local_pts = [(int((px - ox) * sx), int((py - oy) * sy)) for px, py in points]
                    if self._apply_to_overlay(idx, lambda p: p.crop_by_polygon(local_pts)):
                        self._status.set_message(f"레이어 다각형 선택 완료: 꼭짓점 {len(points)}개")
            elif self._processor.has_image:
                img = self._processor.crop_by_polygon(points)
                self._canvas_edit.set_image(img)
                self._status.set_message(f"다각형 선택 완료: 꼭짓점 {len(points)}개")
                self._update_edit_state()
        except Exception as e:
            QMessageBox.critical(self, "오류", str(e))

    def _auto_apply_brush(self, mask):
        """브러시 스트로크 완료 시 마스크 자동 적용."""
        if mask is None or not (mask == 255).any():
            return
        idx = self._get_active_overlay_idx()
        try:
            if idx >= 0:
                overlays = self._canvas_edit.get_overlays()
                if 0 <= idx < len(overlays):
                    ov = overlays[idx]
                    local_mask = self._translate_brush_mask_to_overlay(mask, ov)
                    if self._apply_to_overlay(idx, lambda p: p.apply_brush_mask(local_mask)):
                        self._status.set_message("레이어 브러시 마스크 적용 완료")
            elif self._processor.has_image:
                img = self._processor.apply_brush_mask(mask)
                self._canvas_edit.set_image(img)
                self._status.set_message("브러시 마스크 적용 완료")
                self._update_edit_state()
            # 적용 후 마스크 초기화 (다음 스트로크 준비)
            self._canvas_edit.clear_brush_overlay()
        except Exception as e:
            QMessageBox.critical(self, "오류", str(e))

    # ------------------------------------------------------------------ #
    #  색상 도구
    # ------------------------------------------------------------------ #
    def _on_color_sampled(self, r: int, g: int, b: int, a: int):
        """스포이드: 캔버스에서 색 추출 → 현재 색상 업데이트"""
        self._current_tool_color = (r, g, b, a)
        self._toolbar.update_color_swatch(r, g, b, a)
        self._canvas_edit.set_tool_color(r, g, b, a)
        self._status.set_message(f"색상 추출: #{r:02x}{g:02x}{b:02x}  A={a}")

    def _on_tool_color_changed(self, r: int, g: int, b: int, a: int):
        """색상 피커에서 색 변경"""
        self._current_tool_color = (r, g, b, a)
        self._canvas_edit.set_tool_color(r, g, b, a)

    def _on_fill_applied(self, x: int, y: int):
        """채우기: 클릭 위치에 플러드 필 적용"""
        idx = self._get_active_overlay_idx()
        r, g, b, _ = self._current_tool_color
        try:
            if idx >= 0:
                overlays = self._canvas_edit.get_overlays()
                if 0 <= idx < len(overlays):
                    ov = overlays[idx]
                    xl, yl, _, _ = self._translate_to_overlay_coords(ov, x, y, 1, 1)
                    color = self._current_tool_color
                    if self._apply_to_overlay(idx, lambda p: p.fill_color(xl, yl, color)):
                        self._status.set_message(f"레이어 채우기 완료: ({xl},{yl})  #{r:02x}{g:02x}{b:02x}")
            elif self._processor.has_image:
                img = self._processor.fill_color(x, y, self._current_tool_color)
                self._canvas_edit.set_image(img)
                self._status.set_message(f"채우기 완료: ({x},{y})  #{r:02x}{g:02x}{b:02x}")
                self._update_edit_state()
        except Exception as e:
            QMessageBox.critical(self, "오류", str(e))

    def _on_color_brush_done(self, mask):
        """색상 브러시 스트로크 완료: 즉시 자동 적용."""
        if mask is None or not (mask == 255).any():
            return
        idx = self._get_active_overlay_idx()
        try:
            if idx >= 0:
                overlays = self._canvas_edit.get_overlays()
                if 0 <= idx < len(overlays):
                    ov = overlays[idx]
                    local_mask = self._translate_brush_mask_to_overlay(mask, ov)
                    color = self._current_tool_color
                    if self._apply_to_overlay(idx, lambda p: p.apply_color_brush(local_mask, color)):
                        self._status.set_message("레이어 색상 브러시 적용 완료")
            elif self._processor.has_image:
                img = self._processor.apply_color_brush(mask, self._current_tool_color)
                self._canvas_edit.set_image(img)
                self._status.set_message("색상 브러시 적용 완료")
                self._update_edit_state()
            self._color_brush_pending_mask = None
        except Exception as e:
            QMessageBox.critical(self, "오류", str(e))

    # ------------------------------------------------------------------ #
    #  도형 그리기 / AI 인페인팅
    # ------------------------------------------------------------------ #
    def _on_shape_committed(self, shape_type: str, x: int, y: int, w: int, h: int):
        """캔버스에서 도형 드래그 완료 → 이미지에 점선 도형 그리기"""
        if w < 2 or h < 2:
            return
        color = self._current_tool_color
        line_width = self._toolbar.get_shape_line_width()
        dash_len = self._toolbar.get_shape_dash_len()
        kind = "ellipse" if shape_type == "shape_ellipse" else "rect"
        r, g, b, _ = color
        idx = self._get_active_overlay_idx()
        try:
            if idx >= 0:
                overlays = self._canvas_edit.get_overlays()
                if 0 <= idx < len(overlays):
                    ov = overlays[idx]
                    lx, ly, lw, lh = self._translate_to_overlay_coords(ov, x, y, w, h)
                    if self._apply_to_overlay(idx, lambda p: p.draw_dotted_shape(kind, lx, ly, lw, lh, color, line_width, dash_len)):
                        self._status.set_message(
                            f"레이어 점선 {'원/타원' if kind == 'ellipse' else '사각형'} 완료: {lw}×{lh}  #{r:02x}{g:02x}{b:02x}"
                        )
            elif self._processor.has_image:
                img = self._processor.draw_dotted_shape(kind, x, y, w, h, color, line_width, dash_len)
                self._canvas_edit.set_image(img)
                self._status.set_message(
                    f"점선 {'원/타원' if kind == 'ellipse' else '사각형'} 그리기 완료: "
                    f"({x},{y}) {w}×{h}  #{r:02x}{g:02x}{b:02x}"
                )
                self._update_edit_state()
        except Exception as e:
            QMessageBox.critical(self, "오류", str(e))

    def _on_inpaint_committed(self, x: int, y: int, w: int, h: int):
        """캔버스 드래그로 선택한 영역의 투명 픽셀을 AI(OpenCV 인페인팅)로 채우기"""
        if w < 2 or h < 2:
            return
        self._status.set_message("빈 영역 AI 채우기 중...")
        idx = self._get_active_overlay_idx()
        try:
            if idx >= 0:
                overlays = self._canvas_edit.get_overlays()
                if 0 <= idx < len(overlays):
                    ov = overlays[idx]
                    lx, ly, lw, lh = self._translate_to_overlay_coords(ov, x, y, w, h)
                    if self._apply_to_overlay(idx, lambda p: p.inpaint_region(lx, ly, lw, lh)):
                        self._status.set_message(f"레이어 빈 영역 채우기 완료: {lw}×{lh}")
            elif self._processor.has_image:
                img = self._processor.inpaint_region(x, y, w, h)
                self._canvas_edit.set_image(img)
                self._status.set_message(f"빈 영역 채우기 완료: ({x},{y}) {w}×{h}")
                self._update_edit_state()
        except Exception as e:
            QMessageBox.critical(self, "오류", str(e))

    # ------------------------------------------------------------------ #
    #  텍스트 삽입
    # ------------------------------------------------------------------ #
    def _on_text_committed(self, settings: dict, ix: int, iy: int, iw: int, ih: int):
        """인라인 에디터 삽입 확정 → PIL 렌더링 후 오버레이로 추가"""
        # 텍스트 모드 유지 — 완료 후 바로 다음 텍스트 박스 드래그 가능
        self._last_text_settings = settings

        text = settings["text"].strip()
        if not text:
            self._status.set_message("텍스트가 비어 있습니다")
            return

        text_img = self._render_text_to_pil(settings, box_w=iw)
        if text_img is None:
            return

        ox = max(0, ix)
        oy = max(0, iy)
        self._canvas_edit.add_overlay(text_img, f"텍스트: {text[:12]}", drop_widget_pos=None)
        overlays = self._canvas_edit.get_overlays()
        if overlays:
            idx = len(overlays) - 1
            self._canvas_edit.move_overlay(idx, ox, oy)
            # 텍스트 서식 저장 (재편집·리사이즈 재렌더링용)
            saved = dict(settings)
            saved['box_w'] = iw
            overlays[idx]['text_settings'] = saved
        self._status.set_message("텍스트 삽입 완료")

    def _on_text_edit_committed(self, settings: dict, overlay_idx: int,
                                 ix: int, iy: int, iw: int, ih: int):
        """기존 텍스트 오버레이 수정 확정 → 재렌더링 후 인-플레이스 교체"""
        self._last_text_settings = settings

        text = settings["text"].strip()
        if not text:
            self._status.set_message("텍스트가 비어 있습니다")
            return

        text_img = self._render_text_to_pil(settings, box_w=iw)
        if text_img is None:
            return

        # 오버레이 이미지 교체 (update_overlay_image는 disp_w/h를 pil 크기로 초기화)
        self._canvas_edit.update_overlay_image(overlay_idx, text_img)

        # disp_w를 원래 박스 너비로 복원, disp_h는 텍스트 내용 높이로 설정
        overlays = self._canvas_edit.get_overlays()
        if 0 <= overlay_idx < len(overlays):
            ov = overlays[overlay_idx]
            ov['disp_w'] = iw
            ov['disp_h'] = text_img.height
            saved = dict(settings)
            saved['box_w'] = iw
            ov['text_settings'] = saved
            ov['name'] = f"텍스트: {text[:12]}"
        self._status.set_message("텍스트 수정 완료")

    def _on_text_overlay_resized(self, overlay_idx: int, new_disp_w: int):
        """텍스트 오버레이 너비 변경 후 텍스트 재렌더링 (PPT 방식 — 너비 조절 시 자동 리플로우)"""
        from PyQt6.QtGui import QImage as _QI, QPixmap as _QP

        overlays = self._canvas_edit.get_overlays()
        if overlay_idx < 0 or overlay_idx >= len(overlays):
            return
        ov = overlays[overlay_idx]
        settings = ov.get('text_settings')
        if not settings:
            return

        box_w = max(20, new_disp_w)
        text_img = self._render_text_to_pil(settings, box_w=box_w)
        if text_img is None:
            return

        pil = text_img.convert("RGBA")
        data = pil.tobytes("raw", "RGBA")
        qimg = _QI(data, pil.width, pil.height, _QI.Format.Format_RGBA8888)

        # pil/pixmap 직접 교체 (disp_w는 사용자 지정 값 유지, disp_h는 내용 높이)
        ov['pil']    = pil
        ov['pixmap'] = _QP.fromImage(qimg)
        ov['disp_w'] = new_disp_w
        ov['disp_h'] = pil.height
        saved = dict(settings)
        saved['box_w'] = new_disp_w
        ov['text_settings'] = saved

        self._canvas_edit.update()
        self._status.set_message("텍스트 너비 재렌더링 완료")

    def _render_text_to_pil(self, settings: dict, box_w: int | None = None):
        """텍스트 서식 설정을 PIL RGBA 이미지로 렌더링. box_w 지정 시 줄 바꿈 적용."""
        from PIL import Image as _Img, ImageDraw, ImageFont

        text  = settings["text"]
        size  = settings["size"]
        bold  = settings["bold"]
        italic = settings["italic"]
        under = settings["underline"]
        color = settings["color"]          # (r, g, b, a)
        align = settings["align"]
        font_family = settings["font"]

        font = self._find_pil_font(font_family, size, bold, italic)

        dummy = _Img.new("RGBA", (1, 1))
        draw = ImageDraw.Draw(dummy)

        raw_lines = text.split("\n")
        gap_est = max(2, size // 6)

        # box_w 지정 시 자동 줄 바꿈 처리
        if box_w and box_w > gap_est * 4:
            max_text_w = box_w - gap_est * 2
            lines: list[str] = []
            for raw_line in raw_lines:
                if not raw_line.strip():
                    lines.append("")
                    continue
                words = raw_line.split(" ")
                current = ""
                for word in words:
                    test = (current + " " + word).strip() if current else word
                    tw = draw.textbbox((0, 0), test, font=font)[2]
                    if tw <= max_text_w:
                        current = test
                    else:
                        if current:
                            lines.append(current)
                        current = word
                if current:
                    lines.append(current)
        else:
            lines = raw_lines

        # 줄 크기 측정
        line_sizes = [draw.textbbox((0, 0), ln or " ", font=font) for ln in lines]
        line_widths  = [b[2] - b[0] for b in line_sizes]
        line_heights = [b[3] - b[1] for b in line_sizes]
        leading = max(line_heights) if line_heights else size
        gap = max(2, leading // 6)

        total_w = box_w if box_w else (max(line_widths) if line_widths else size) + gap * 2
        total_h = leading * len(lines) + gap * (len(lines) - 1) + gap * 2

        img = _Img.new("RGBA", (max(1, total_w), max(1, total_h)), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        r, g, b, a = color
        pil_color = (r, g, b, a)

        y_cursor = gap
        for i, line in enumerate(lines):
            lw = line_widths[i] if i < len(line_widths) else 0
            if align == "left":
                x_cursor = gap
            elif align == "center":
                x_cursor = (total_w - lw) // 2
            else:  # right
                x_cursor = total_w - lw - gap

            draw.text((x_cursor, y_cursor), line, font=font, fill=pil_color)

            if under:
                uy = y_cursor + leading - gap
                draw.line([(x_cursor, uy), (x_cursor + lw, uy)],
                          fill=pil_color, width=max(1, size // 20))

            y_cursor += leading + gap

        return img

    def _find_pil_font(self, family: str, size: int, bold: bool, italic: bool):
        """시스템에서 폰트 파일을 찾아 PIL ImageFont 반환. 실패 시 기본 폰트."""
        from PIL import ImageFont

        # Windows 폰트 디렉터리 후보
        win_font_dir = "C:/Windows/Fonts"

        # 폰트명 → 파일명 매핑 (Windows 일반 폰트)
        candidates = []
        fname_lower = family.lower().replace(" ", "")

        # 맑은 고딕 / Malgun Gothic
        if "malgun" in fname_lower or "맑은" in family:
            if bold:
                candidates += ["malgunbd.ttf"]
            candidates += ["malgun.ttf"]
        # 나눔고딕
        elif "nanum" in fname_lower or "나눔" in family:
            if bold:
                candidates += ["NanumGothicBold.ttf", "NanumGothic_Bold.ttf"]
            candidates += ["NanumGothic.ttf"]
        # 굴림
        elif "gulim" in fname_lower or "굴림" in family:
            candidates += ["gulim.ttc", "gulim.ttf"]
        # 돋움
        elif "dotum" in fname_lower or "돋움" in family:
            candidates += ["dotum.ttc", "dotum.ttf"]
        # Arial
        elif "arial" in fname_lower:
            if bold and italic:
                candidates += ["arialbi.ttf"]
            elif bold:
                candidates += ["arialbd.ttf"]
            elif italic:
                candidates += ["ariali.ttf"]
            candidates += ["arial.ttf"]
        # Times New Roman
        elif "times" in fname_lower:
            if bold and italic:
                candidates += ["timesbi.ttf"]
            elif bold:
                candidates += ["timesbd.ttf"]
            elif italic:
                candidates += ["timesi.ttf"]
            candidates += ["times.ttf"]
        # Courier New
        elif "courier" in fname_lower:
            if bold and italic:
                candidates += ["courbi.ttf"]
            elif bold:
                candidates += ["courbd.ttf"]
            elif italic:
                candidates += ["couri.ttf"]
            candidates += ["cour.ttf"]
        # 기본 폴백
        else:
            if bold:
                candidates += ["malgunbd.ttf", "arialbd.ttf"]
            candidates += ["malgun.ttf", "arial.ttf"]

        # 후보 탐색
        for fname in candidates:
            path = os.path.join(win_font_dir, fname)
            if os.path.isfile(path):
                try:
                    return ImageFont.truetype(path, size)
                except Exception:
                    pass

        # 마지막 폴백: PIL 기본 폰트
        try:
            return ImageFont.load_default(size=size)
        except Exception:
            return ImageFont.load_default()

    # ------------------------------------------------------------------ #
    #  크롭
    # ------------------------------------------------------------------ #
    def _on_crop_drag(self, x: int, y: int, w: int, h: int):
        idx = self._get_active_overlay_idx()
        try:
            if idx >= 0:
                self._crop_overlay(idx, x, y, w, h)
            elif self._processor.has_image:
                img = self._processor.crop_by_rect(x, y, w, h)
                self._canvas_edit.set_image(img)
                nw, nh = self._processor.get_size()
                self._status.set_size(nw, nh)
                self._workspace_size_lbl.setText(f"작업 크기: {nw} × {nh} px")
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
        idx = self._get_active_overlay_idx()
        try:
            if idx >= 0:
                self._crop_overlay(idx, x, y, w, h)
            elif self._processor.has_image:
                img = self._processor.crop_by_rect(x, y, w, h)
                self._canvas_edit.set_image(img)
                nw, nh = self._processor.get_size()
                self._status.set_size(nw, nh)
                self._workspace_size_lbl.setText(f"작업 크기: {nw} × {nh} px")
                self._status.set_message(f"크롭 완료: {nw}×{nh}")
                self._update_edit_state()
            self._canvas_edit.set_mode("none")
            self._toolbar.set_mode("none")
        except Exception as e:
            QMessageBox.critical(self, "오류", str(e))

    # ------------------------------------------------------------------ #
    #  필터
    # ------------------------------------------------------------------ #
    def _on_filter(self, name: str):
        idx = self._get_active_overlay_idx()
        try:
            if idx >= 0:
                if self._apply_to_overlay(idx, lambda p: p.apply_filter(name)):
                    self._status.set_message(f"레이어 필터 적용: {name}")
            elif self._processor.has_image:
                img = self._processor.apply_filter(name)
                self._canvas_edit.set_image(img)
                self._status.set_message(f"필터 적용: {name}")
                self._update_edit_state()
            else:
                QMessageBox.warning(self, "경고", "편집할 레이어를 선택하세요.")
        except Exception as e:
            QMessageBox.critical(self, "오류", str(e))

    # ------------------------------------------------------------------ #
    #  초기화
    # ------------------------------------------------------------------ #
    def _on_reset(self):
        idx = self._get_active_overlay_idx()
        if idx >= 0:
            self._status.set_message("레이어 복원은 레이어를 삭제 후 다시 추가하세요.")
            return
        if not self._processor.has_image:
            return
        self._processor.reset_to_original()
        self._canvas_edit.set_image(self._processor.current_image)
        w, h = self._processor.get_size()
        self._status.set_size(w, h)
        self._workspace_size_lbl.setText(f"작업 크기: {w} × {h} px")
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
            self._workspace_size_lbl.setText(f"작업 크기: {w} × {h} px")

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
