"""
ui/canvas.py
이미지 표시 및 마우스 인터랙션 캔버스
"""
import os
import numpy as np
from PyQt6.QtWidgets import QLabel, QSizePolicy
from PyQt6.QtCore import Qt, QPoint, QRect, pyqtSignal
from PyQt6.QtGui import (
    QPixmap, QImage, QPainter, QPen, QColor, QCursor, QBrush, QPolygon
)
from PIL import Image

# 작업 영역 배경 타일 이미지 (투명도 표시용)
_BG_TILE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'images', 'img_2.png'
)


class ImageCanvas(QLabel):
    """
    중앙 이미지 캔버스.
    - 이미지 표시 / 줌 (마우스 휠) / 패닝 (가운데 버튼 드래그)
    - 크롭 드래그 선택 (파란 박스)
    - GrabCut 선택 (주황 박스, 드래그 완료 시 자동 적용)
    - 브러시 마스킹
    - 다각형 선택
    - 크기 지정 크롭 미리보기 (노란 박스, 드래그로 위치 조정)
    """

    crop_selected       = pyqtSignal(int, int, int, int)   # x, y, w, h (이미지 좌표)
    grabcut_selected    = pyqtSignal(int, int, int, int)
    brush_stroke_done   = pyqtSignal(object)
    polygon_closed      = pyqtSignal(object)               # list[(x,y)]
    crop_size_committed = pyqtSignal(int, int, int, int)  # x, y, w, h (이미지 좌표)
    zoom_changed        = pyqtSignal(float)
    file_dropped        = pyqtSignal(str, object)          # path, QPoint(위젯 좌표)
    overlay_selected    = pyqtSignal(int)                  # 선택된 오버레이 인덱스 (-1=없음)
    overlay_moved       = pyqtSignal(int, int, int)        # index, x, y (이미지 좌표)
    overlays_changed    = pyqtSignal()                     # 추가/삭제 등 목록 변경
    # 색상 도구
    color_sampled       = pyqtSignal(int, int, int, int)  # r, g, b, a (스포이드)
    fill_applied        = pyqtSignal(int, int)             # x, y (이미지 좌표)
    color_brush_done    = pyqtSignal(object)               # mask array
    shape_committed     = pyqtSignal(str, int, int, int, int)  # shape_type, x, y, w, h (이미지 좌표)
    inpaint_committed   = pyqtSignal(int, int, int, int)       # x, y, w, h (이미지 좌표)
    text_rect_selected = pyqtSignal(int, int, int, int)         # x, y, w, h (이미지 좌표) — 텍스트 박스 드래그 영역

    MODE_NONE         = "none"
    MODE_CROP         = "crop"
    MODE_GRABCUT      = "grabcut"
    MODE_BRUSH        = "brush"
    MODE_POLYGON      = "polygon"
    MODE_CROP_SIZE    = "crop_size"   # 크기 지정 크롭 미리보기
    MODE_PIPETTE      = "pipette"     # 스포이드 (색 추출)
    MODE_FILL         = "fill"        # 채우기 (플러드 필)
    MODE_COLOR_BRUSH   = "color_brush"   # 색상 브러시
    MODE_SHAPE_RECT    = "shape_rect"    # 점선 사각형 그리기
    MODE_SHAPE_ELLIPSE = "shape_ellipse" # 점선 원/타원 그리기
    MODE_INPAINT       = "inpaint"       # AI 빈 영역 채우기 영역 드래그
    MODE_TEXT          = "text"          # 텍스트 삽입

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(400, 400)
        self.setStyleSheet("background-color: #1e1e2e; border: 1px solid #313244;")
        self.setMouseTracking(True)

        self._mode = self.MODE_NONE
        self._pil_image: Image.Image | None = None
        self._pixmap: QPixmap | None = None   # fit-to-window 스케일 픽스맵
        self._scale = 1.0                     # 이미지 → 픽스맵 배율 (fit-to-window)

        # 줌 / 패닝
        self._zoom = 1.0                      # 추가 줌 배율 (1.0 = fit)
        self._pan_offset = QPoint(0, 0)
        self._pan_start: QPoint | None = None
        self._pan_start_offset = QPoint(0, 0)

        # 드래그 선택 (크롭 / GrabCut)
        self._drag_start: QPoint | None = None
        self._selection_rect: QRect | None = None

        # 브러시
        self._brush_size = 20
        self._brush_mask: np.ndarray | None = None
        self._brush_overlay: QPixmap | None = None
        self._drawing = False

        # 색상 도구
        self._tool_color: tuple = (0, 0, 0, 255)              # 현재 선택 색 (RGBA)
        self._color_brush_mask: np.ndarray | None = None      # 색상 브러시 마스크
        self._color_brush_overlay: QPixmap | None = None      # 색상 브러시 미리보기
        self._color_drawing = False

        # 도형 그리기
        self._shape_drag_start: QPoint | None = None
        self._shape_rect: QRect | None = None

        # 인페인팅 영역 드래그
        self._inpaint_drag_start: QPoint | None = None
        self._inpaint_rect: QRect | None = None

        # 텍스트 박스 드래그
        self._text_drag_start: QPoint | None = None
        self._text_rect: QRect | None = None

        # 다각형
        self._poly_image_pts: list[tuple[int, int]] = []
        self._cursor_pos: QPoint | None = None

        # 크기 지정 크롭 미리보기
        self._crop_preview_rect: QRect | None = None   # 이미지 좌표
        self._crop_drag_start: QPoint | None = None
        self._crop_drag_start_rect: QRect | None = None

        # 오버레이 레이어
        # 각 항목: {'pil': PIL, 'pixmap': QPixmap, 'x': int, 'y': int,
        #           'visible': bool, 'name': str}
        self._overlays: list[dict] = []
        self._active_overlay: int = -1       # 선택된 오버레이 인덱스
        self._ov_drag_start: QPoint | None = None
        self._ov_drag_start_pos: tuple[int, int] | None = None
        self._ov_resize_corner: int = -1          # active resize corner (-1=none, 0=TL,1=TR,2=BL,3=BR)
        self._ov_resize_start: tuple | None = None  # (drag_pos, orig_x, orig_y, orig_disp_w, orig_disp_h)

        # 왼쪽 버튼 패닝 (MODE_NONE, 오버레이 없는 빈 공간)
        self._left_pan_start: QPoint | None = None
        self._left_pan_start_offset: QPoint | None = None

        # 기본 이미지 가시성 / 선택
        self._base_visible: bool = True
        self._base_selected: bool = False   # 레이어 패널에서 기본 이미지 선택 시 True

        # 원본 이미지 미리보기 (우상단 고정)
        self._orig_pixmap: QPixmap | None = None          # 원본 이미지 픽스맵
        self._minimap_w = 160                             # 미리보기 너비 (리사이즈 가능)
        self._minimap_resize_start: tuple | None = None  # (start_pos, start_w)
        self._minimap_hovered: bool = False               # 미니맵 위에 마우스 있는지

        # 드래그 앤 드롭 활성화
        self.setAcceptDrops(True)

        # 작업 영역 배경 타일 픽스맵
        self._bg_tile_pixmap: QPixmap | None = None
        try:
            tile_img = Image.open(_BG_TILE_PATH).convert("RGBA")
            tile_data = tile_img.tobytes("raw", "RGBA")
            tile_qimg = QImage(tile_data, tile_img.width, tile_img.height,
                               QImage.Format.Format_RGBA8888)
            self._bg_tile_pixmap = QPixmap.fromImage(tile_qimg)
        except Exception:
            pass

    # ------------------------------------------------------------------ #
    #  공개 메서드
    # ------------------------------------------------------------------ #
    def set_image(self, pil_img: Image.Image):
        self._pil_image = pil_img
        self._refresh_pixmap()
        self._init_brush_mask()
        self._color_brush_overlay = None
        self._color_brush_mask = None

    def set_original_image(self, pil_img: Image.Image):
        """원본 이미지를 우상단 미리보기용으로 저장"""
        if pil_img is None:
            self._orig_pixmap = None
            return
        img = pil_img.convert("RGBA")
        data = img.tobytes("raw", "RGBA")
        qimg = QImage(data, img.width, img.height, QImage.Format.Format_RGBA8888)
        self._orig_pixmap = QPixmap.fromImage(qimg)
        self.update()

    def set_mode(self, mode: str):
        self._mode = mode
        self._selection_rect = None
        if mode != self.MODE_POLYGON:
            self.cancel_polygon()
        if mode != self.MODE_CROP_SIZE:
            self._crop_preview_rect = None
        if mode not in (self.MODE_SHAPE_RECT, self.MODE_SHAPE_ELLIPSE):
            self._shape_rect = None
            self._shape_drag_start = None
        if mode != self.MODE_INPAINT:
            self._inpaint_rect = None
            self._inpaint_drag_start = None
        if mode != self.MODE_TEXT:
            self._text_drag_start = None
            self._text_rect = None
        cursors = {
            self.MODE_BRUSH:         Qt.CursorShape.CrossCursor,
            self.MODE_CROP:          Qt.CursorShape.CrossCursor,
            self.MODE_GRABCUT:       Qt.CursorShape.CrossCursor,
            self.MODE_POLYGON:       Qt.CursorShape.CrossCursor,
            self.MODE_CROP_SIZE:     Qt.CursorShape.SizeAllCursor,
            self.MODE_PIPETTE:       Qt.CursorShape.CrossCursor,
            self.MODE_FILL:          Qt.CursorShape.CrossCursor,
            self.MODE_COLOR_BRUSH:   Qt.CursorShape.CrossCursor,
            self.MODE_SHAPE_RECT:    Qt.CursorShape.CrossCursor,
            self.MODE_SHAPE_ELLIPSE: Qt.CursorShape.CrossCursor,
            self.MODE_INPAINT:       Qt.CursorShape.CrossCursor,
            self.MODE_TEXT:          Qt.CursorShape.CrossCursor,
        }
        self.setCursor(QCursor(cursors.get(mode, Qt.CursorShape.ArrowCursor)))
        self.update()

    def set_brush_size(self, size: int):
        self._brush_size = size

    def set_tool_color(self, r: int, g: int, b: int, a: int = 255):
        """색상 도구에서 사용할 현재 색상 설정"""
        self._tool_color = (r, g, b, a)
        self._color_brush_overlay = None   # 미리보기 색 재생성

    def clear_brush_overlay(self):
        self._brush_overlay = None
        self._init_brush_mask()
        self.update()

    def cancel_polygon(self):
        self._poly_image_pts = []
        self._cursor_pos = None
        self.update()

    def set_crop_size_preview(self, w: int, h: int):
        """크기 지정 크롭 미리보기 모드 진입"""
        if self._pil_image is None:
            return
        iw, ih = self._pil_image.size
        cw, ch = min(w, iw), min(h, ih)
        x = max(0, (iw - cw) // 2)
        y = max(0, (ih - ch) // 2)
        self._crop_preview_rect = QRect(x, y, cw, ch)
        self._mode = self.MODE_CROP_SIZE
        self.setCursor(QCursor(Qt.CursorShape.SizeAllCursor))
        self.update()

    # ── 오버레이 ──────────────────────────────────────────────────────── #
    def add_overlay(self, pil_img: Image.Image, name: str,
                    drop_widget_pos: QPoint | None = None) -> int:
        """오버레이 이미지 추가. drop_widget_pos가 있으면 그 위치를 기준으로 배치."""
        img = pil_img.convert("RGBA")
        data = img.tobytes("raw", "RGBA")
        from PyQt6.QtGui import QImage as _QI
        qimg = _QI(data, img.width, img.height, _QI.Format.Format_RGBA8888)
        pixmap = QPixmap.fromImage(qimg)

        if drop_widget_pos and self._pil_image:
            pt = self._widget_to_image(drop_widget_pos)
            x = max(0, pt.x() - img.width // 2)
            y = max(0, pt.y() - img.height // 2)
        else:
            x = y = 0

        self._overlays.append({
            'pil': pil_img, 'pixmap': pixmap,
            'x': x, 'y': y,
            'visible': True, 'name': name,
            'disp_w': pil_img.width, 'disp_h': pil_img.height,
        })
        idx = len(self._overlays) - 1
        self._active_overlay = idx
        self.overlays_changed.emit()
        self.overlay_selected.emit(idx)
        self.update()
        return idx

    def remove_overlay(self, index: int):
        if 0 <= index < len(self._overlays):
            self._overlays.pop(index)
            self._active_overlay = -1
            self.overlays_changed.emit()
            self.overlay_selected.emit(-1)
            self.update()

    def set_overlay_visible(self, index: int, visible: bool):
        if 0 <= index < len(self._overlays):
            self._overlays[index]['visible'] = visible
            self.update()

    def set_base_visible(self, visible: bool):
        """기본 이미지 가시성 전환"""
        self._base_visible = visible
        self.update()

    def select_overlay(self, index: int):
        self._active_overlay = index
        self._base_selected = (index == -1)   # -1이면 기본 이미지 선택
        self.overlay_selected.emit(index)
        self.update()

    def get_overlays(self) -> list[dict]:
        return self._overlays

    def move_overlay(self, index: int, x: int, y: int):
        """오버레이 위치를 이미지 좌표로 설정"""
        if 0 <= index < len(self._overlays):
            self._overlays[index]['x'] = x
            self._overlays[index]['y'] = y
            self.update()

    def clear_overlays(self):
        self._overlays.clear()
        self._active_overlay = -1
        self.overlays_changed.emit()
        self.update()

    def reset_overlay_size(self, index: int):
        """오버레이를 원본 크기로 초기화"""
        if 0 <= index < len(self._overlays):
            ov = self._overlays[index]
            ov['disp_w'] = ov['pil'].width
            ov['disp_h'] = ov['pil'].height
            self.update()

    def fit_overlay_to_canvas(self, index: int):
        """선택한 오버레이를 작업 크기(캔버스)에 꽉 차게 확대"""
        if 0 <= index < len(self._overlays) and self._pil_image:
            cw, ch = self._pil_image.size
            self._overlays[index]['disp_w'] = cw
            self._overlays[index]['disp_h'] = ch
            self._overlays[index]['x'] = 0
            self._overlays[index]['y'] = 0
            self.update()

    def update_overlay_image(self, index: int, new_pil: Image.Image):
        """오버레이의 PIL 이미지와 픽스맵을 갱신합니다."""
        if 0 <= index < len(self._overlays):
            ov = self._overlays[index]
            pil = new_pil.convert("RGBA") if new_pil.mode != "RGBA" else new_pil.copy()
            ov['pil'] = pil
            data = pil.tobytes("raw", "RGBA")
            qimg = QImage(data, pil.width, pil.height, QImage.Format.Format_RGBA8888)
            ov['pixmap'] = QPixmap.fromImage(qimg)
            ov['disp_w'] = pil.width
            ov['disp_h'] = pil.height
            self.overlays_changed.emit()
            self.update()

    def reset_zoom(self):
        self._zoom = 1.0
        self._pan_offset = QPoint(0, 0)
        self.zoom_changed.emit(self._zoom)
        self.update()

    def zoom_in(self):
        self._apply_zoom(1.25)

    def zoom_out(self):
        self._apply_zoom(1 / 1.25)

    def get_image_rect(self) -> QRect:
        """줌·패닝이 적용된 이미지 표시 영역 (위젯 좌표)"""
        if self._pixmap is None:
            return QRect()
        pw = int(self._pixmap.width() * self._zoom)
        ph = int(self._pixmap.height() * self._zoom)
        ww, wh = self.width(), self.height()
        x = (ww - pw) // 2 + self._pan_offset.x()
        y = (wh - ph) // 2 + self._pan_offset.y()
        return QRect(x, y, pw, ph)

    # ------------------------------------------------------------------ #
    #  내부: 픽스맵 갱신 (fit-to-window 스케일)
    # ------------------------------------------------------------------ #
    def _refresh_pixmap(self):
        if self._pil_image is None:
            return
        img = self._pil_image.convert("RGBA")
        data = img.tobytes("raw", "RGBA")
        qimg = QImage(data, img.width, img.height, QImage.Format.Format_RGBA8888)
        raw_pm = QPixmap.fromImage(qimg)

        max_w = max(self.width() - 20, 100)
        max_h = max(self.height() - 20, 100)
        scaled = raw_pm.scaled(
            max_w, max_h,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._scale = scaled.width() / img.width
        self._pixmap = scaled
        self._brush_overlay = None
        self.update()

    def _init_brush_mask(self):
        if self._pil_image is None:
            return
        w, h = self._pil_image.size
        self._brush_mask = np.zeros((h, w), dtype=np.uint8)

    # ------------------------------------------------------------------ #
    #  줌
    # ------------------------------------------------------------------ #
    def _apply_zoom(self, factor: float, anchor: QPoint = None):
        if self._pixmap is None:
            return
        new_zoom = max(0.1, min(self._zoom * factor, 10.0))
        if abs(new_zoom - self._zoom) < 1e-6:
            return

        if anchor is None:
            self._zoom = new_zoom
        else:
            old_rect = self.get_image_rect()
            if old_rect.width() > 0:
                rel_x = (anchor.x() - old_rect.x()) / old_rect.width()
                rel_y = (anchor.y() - old_rect.y()) / old_rect.height()
            else:
                rel_x = rel_y = 0.5

            self._zoom = new_zoom
            new_pw = int(self._pixmap.width() * new_zoom)
            new_ph = int(self._pixmap.height() * new_zoom)
            ww, wh = self.width(), self.height()
            new_rect_x = int(anchor.x() - rel_x * new_pw)
            new_rect_y = int(anchor.y() - rel_y * new_ph)
            self._pan_offset = QPoint(
                new_rect_x - (ww - new_pw) // 2,
                new_rect_y - (wh - new_ph) // 2,
            )

        self.zoom_changed.emit(self._zoom)
        self.update()

    # ------------------------------------------------------------------ #
    #  좌표 변환
    # ------------------------------------------------------------------ #
    def _widget_to_image(self, pt: QPoint) -> QPoint:
        rect = self.get_image_rect()
        if rect.width() == 0:
            return QPoint(0, 0)
        # 위젯 → 픽스맵(fit-to-window) → 이미지
        ix = int((pt.x() - rect.x()) / (self._scale * self._zoom))
        iy = int((pt.y() - rect.y()) / (self._scale * self._zoom))
        if self._pil_image:
            ix = max(0, min(ix, self._pil_image.width - 1))
            iy = max(0, min(iy, self._pil_image.height - 1))
        return QPoint(ix, iy)

    def _image_to_widget(self, ix: int, iy: int) -> QPoint:
        rect = self.get_image_rect()
        return QPoint(
            int(rect.x() + ix * self._scale * self._zoom),
            int(rect.y() + iy * self._scale * self._zoom),
        )

    # ------------------------------------------------------------------ #
    #  paintEvent
    # ------------------------------------------------------------------ #
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0x1e, 0x1e, 0x2e))

        if self._pixmap:
            rect = self.get_image_rect()
            # img_2.png 타일 패턴을 작업 영역 배경으로 렌더링
            if self._bg_tile_pixmap:
                painter.save()
                painter.setClipRect(rect)
                tw = self._bg_tile_pixmap.width()
                th = self._bg_tile_pixmap.height()
                col = 0
                while col * tw < rect.width() + tw:
                    row = 0
                    while row * th < rect.height() + th:
                        painter.drawPixmap(
                            rect.x() + col * tw,
                            rect.y() + row * th,
                            self._bg_tile_pixmap,
                        )
                        row += 1
                    col += 1
                painter.restore()

            if self._base_visible:
                painter.drawPixmap(rect, self._pixmap)
            # 기본 이미지 숨김 시 타일 패턴만 표시 (별도 렌더링 불필요)

            if self._brush_overlay:
                painter.setOpacity(0.5)
                painter.drawPixmap(rect, self._brush_overlay)
                painter.setOpacity(1.0)

            if self._color_brush_overlay:
                painter.setOpacity(0.75)
                painter.drawPixmap(rect, self._color_brush_overlay)
                painter.setOpacity(1.0)

            # 오버레이 이미지 렌더링
            for i, ov in enumerate(self._overlays):
                if not ov.get('visible', True):
                    continue
                ov_rect = self._overlay_widget_rect(i)
                # Scale pixmap to display size if different from original
                disp_w = ov.get('disp_w', ov['pil'].width)
                disp_h = ov.get('disp_h', ov['pil'].height)
                if disp_w != ov['pil'].width or disp_h != ov['pil'].height:
                    scaled_pm = ov['pixmap'].scaled(
                        int(disp_w * self._scale),
                        int(disp_h * self._scale),
                        Qt.AspectRatioMode.IgnoreAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                    painter.drawPixmap(ov_rect, scaled_pm)
                else:
                    painter.drawPixmap(ov_rect, ov['pixmap'])
                # 선택된 오버레이 테두리 및 리사이즈 핸들
                if i == self._active_overlay:
                    painter.setPen(QPen(QColor(89, 180, 250), 2, Qt.PenStyle.DashLine))
                    painter.setBrush(Qt.BrushStyle.NoBrush)
                    painter.drawRect(ov_rect)
                    # 코너 리사이즈 핸들
                    handles = self._get_corner_handles(i)
                    painter.setPen(QPen(QColor(89, 180, 250), 2))
                    painter.setBrush(QBrush(QColor(30, 30, 50)))
                    for h_rect in handles:
                        painter.drawRect(h_rect)

            # 기본 이미지 선택 시 테두리 표시
            if self._base_selected:
                br = rect.adjusted(-2, -2, 2, 2)
                painter.setPen(QPen(QColor(89, 180, 250), 2, Qt.PenStyle.DashLine))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRect(br)
                # 크기 표시 레이블
                if self._pil_image:
                    iw, ih = self._pil_image.size
                    painter.setPen(QColor(0x89, 0xb4, 0xfa))
                    f = painter.font()
                    f.setBold(True)
                    f.setPointSize(8)
                    painter.setFont(f)
                    lbl = f"기본 이미지  {iw} × {ih} px"
                    painter.fillRect(
                        br.x(), br.y() - 18, len(lbl) * 6 + 10, 16,
                        QColor(0x1e, 0x3a, 0x5f, 200),
                    )
                    painter.drawText(br.x() + 5, br.y() - 5, lbl)

        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        self._paint_overlays(painter)
        self._paint_minimap(painter)
        painter.end()

    def _paint_minimap(self, painter: QPainter):
        """우상단에 원본 이미지 미리보기를 그린다."""
        if self._orig_pixmap is None:
            return
        mr = self._minimap_rect()
        if mr.isEmpty():
            return

        HEADER_H = 18   # "원본" 레이블 높이

        # 배경
        painter.setOpacity(0.90)
        painter.fillRect(mr, QColor(0x12, 0x12, 0x1e))
        painter.setOpacity(1.0)
        # 테두리
        painter.setPen(QPen(QColor(0x89, 0xb4, 0xfa), 1))
        painter.drawRect(mr)

        # "원본" 헤더 바
        header_r = QRect(mr.x() + 1, mr.y() + 1, mr.width() - 2, HEADER_H)
        painter.fillRect(header_r, QColor(0x1e, 0x3a, 0x5f))
        painter.setPen(QColor(0x89, 0xb4, 0xfa))
        f = painter.font()
        f.setBold(True)
        f.setPointSize(8)
        painter.setFont(f)
        painter.drawText(header_r, Qt.AlignmentFlag.AlignCenter, "원본")

        # 이미지 영역
        img_area = QRect(mr.x() + 1, mr.y() + HEADER_H + 1,
                         mr.width() - 2, mr.height() - HEADER_H - 2)
        pm = self._orig_pixmap.scaled(
            img_area.width(), img_area.height(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        px = img_area.x() + (img_area.width() - pm.width()) // 2
        py = img_area.y() + (img_area.height() - pm.height()) // 2
        painter.drawPixmap(px, py, pm)

        # 리사이즈 핸들 (우하단 삼각형) — 호버 시에만 표시
        if self._minimap_hovered:
            hs = 10
            rx, ry = mr.right(), mr.bottom()
            pts = QPolygon([
                QPoint(rx - hs, ry),
                QPoint(rx, ry),
                QPoint(rx, ry - hs),
            ])
            painter.setBrush(QBrush(QColor(0x89, 0xb4, 0xfa)))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawPolygon(pts)

    def _paint_overlays(self, painter: QPainter):
        # ── 드래그 선택 (크롭=파랑, GrabCut=주황) ─────────────────────
        if self._selection_rect and self._mode in (self.MODE_CROP, self.MODE_GRABCUT):
            if self._mode == self.MODE_CROP:
                fill, border, label = QColor(89, 180, 250, 45), QColor(89, 180, 250, 220), "✂ 크롭 영역"
            else:
                fill, border, label = QColor(250, 160, 50, 45), QColor(250, 160, 50, 220), "📦 GrabCut 영역"
            painter.fillRect(self._selection_rect, fill)
            painter.setPen(QPen(border, 2))
            painter.drawRect(self._selection_rect)
            f = painter.font(); f.setBold(True); f.setPointSize(9); painter.setFont(f)
            painter.setPen(border)
            painter.drawText(self._selection_rect.x() + 5, self._selection_rect.y() - 6, label)

        # ── 텍스트 박스 드래그 미리보기 (초록 점선) ──────────────────────
        if self._text_rect and self._mode == self.MODE_TEXT:
            tr = self._text_rect
            painter.fillRect(tr, QColor(100, 215, 100, 30))
            painter.setPen(QPen(QColor(100, 215, 100, 220), 2, Qt.PenStyle.DashLine))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(tr)
            f = painter.font(); f.setBold(True); f.setPointSize(9); painter.setFont(f)
            painter.setPen(QColor(100, 215, 100, 220))
            painter.drawText(tr.x() + 5, tr.y() - 6, "T 텍스트 영역")
            painter.setPen(QColor(100, 215, 100, 180))
            f2 = painter.font(); f2.setBold(False); f2.setPointSize(8); painter.setFont(f2)
            painter.drawText(tr.x() + 4, tr.bottom() - 5, "드래그 후 손 떼면 다이얼로그 열림")

        # ── 크기 지정 크롭 미리보기 (노란 박스) ─────────────────────────
        if self._mode == self.MODE_CROP_SIZE and self._crop_preview_rect and self._pixmap:
            r = self._crop_preview_rect
            tl = self._image_to_widget(r.x(), r.y())
            br = self._image_to_widget(r.x() + r.width(), r.y() + r.height())
            wr = QRect(tl, br)
            img_r = self.get_image_rect()

            # 외곽 어두운 오버레이 (4개 직사각형)
            dark = QColor(0, 0, 0, 130)
            painter.fillRect(QRect(img_r.x(), img_r.y(), img_r.width(), max(0, wr.y() - img_r.y())), dark)
            painter.fillRect(QRect(img_r.x(), wr.bottom(), img_r.width(), max(0, img_r.bottom() - wr.bottom())), dark)
            painter.fillRect(QRect(img_r.x(), wr.y(), max(0, wr.x() - img_r.x()), wr.height()), dark)
            painter.fillRect(QRect(wr.right(), wr.y(), max(0, img_r.right() - wr.right()), wr.height()), dark)

            # 선택 테두리
            painter.setPen(QPen(QColor(255, 220, 50), 2, Qt.PenStyle.SolidLine))
            painter.drawRect(wr)
            # 모서리 핸들
            hs = 6
            for cx, cy in [(wr.x(), wr.y()), (wr.right(), wr.y()),
                           (wr.x(), wr.bottom()), (wr.right(), wr.bottom())]:
                painter.fillRect(QRect(cx - hs, cy - hs, hs * 2, hs * 2), QColor(255, 220, 50))
            # 정보 텍스트
            painter.setPen(QColor(255, 220, 50))
            f = painter.font(); f.setBold(True); f.setPointSize(9); painter.setFont(f)
            info = f"{r.width()} × {r.height()} px  |  위치: ({r.x()}, {r.y()})"
            painter.drawText(wr.x() + 4, wr.y() + 16, info)
            painter.setPen(QColor(255, 220, 50, 160))
            f2 = painter.font(); f2.setBold(False); f2.setPointSize(8); painter.setFont(f2)
            painter.drawText(wr.x() + 4, wr.bottom() - 5, "드래그로 위치 조정  |  더블클릭 또는 Enter로 크롭 적용")

        # ── 다각형 선택 ─────────────────────────────────────────────────
        if self._mode == self.MODE_POLYGON and self._poly_image_pts:
            widget_pts = [self._image_to_widget(x, y) for x, y in self._poly_image_pts]
            n = len(widget_pts)
            green = QColor(80, 220, 100)

            if n >= 3:
                painter.setBrush(QBrush(QColor(80, 220, 100, 40)))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawPolygon(QPolygon(widget_pts))

            painter.setPen(QPen(green, 2))
            for i in range(n - 1):
                painter.drawLine(widget_pts[i], widget_pts[i + 1])

            if self._cursor_pos and widget_pts:
                painter.setPen(QPen(green, 1, Qt.PenStyle.DashLine))
                painter.drawLine(widget_pts[-1], self._cursor_pos)
                if n >= 2:
                    painter.setPen(QPen(QColor(80, 220, 100, 100), 1, Qt.PenStyle.DotLine))
                    painter.drawLine(self._cursor_pos, widget_pts[0])

            painter.setPen(Qt.PenStyle.NoPen)
            for i, pt in enumerate(widget_pts):
                if i == 0 and n >= 3:
                    painter.setBrush(QBrush(QColor(230, 80, 80)))
                    painter.drawEllipse(pt, 7, 7)
                else:
                    painter.setBrush(QBrush(green))
                    painter.drawEllipse(pt, 4, 4)

            if n == 1:
                painter.setPen(QColor(200, 200, 200))
                painter.drawText(widget_pts[0].x() + 10, widget_pts[0].y() - 6,
                                 "클릭으로 꼭짓점 추가  |  더블클릭으로 완성")

        # ── 인페인팅 영역 미리보기 (청록색) ─────────────────────────────
        if self._inpaint_rect and self._mode == self.MODE_INPAINT:
            fill   = QColor(50, 220, 180, 55)
            border = QColor(50, 220, 180, 230)
            painter.fillRect(self._inpaint_rect, fill)
            pen = QPen(border, 2, Qt.PenStyle.DashLine)
            pen.setDashPattern([8, 4])
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(self._inpaint_rect)
            painter.setPen(border)
            f = painter.font(); f.setBold(True); f.setPointSize(9); painter.setFont(f)
            painter.drawText(self._inpaint_rect.x() + 5, self._inpaint_rect.y() - 6,
                             "✨ AI 채우기 영역")

        # ── 도형 그리기 미리보기 ─────────────────────────────────────────
        if self._shape_rect and self._mode in (self.MODE_SHAPE_RECT, self.MODE_SHAPE_ELLIPSE):
            pen = QPen(QColor(200, 100, 250), 2, Qt.PenStyle.DashLine)
            pen.setDashPattern([6, 4])
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            if self._mode == self.MODE_SHAPE_RECT:
                painter.drawRect(self._shape_rect)
                label = "□ 사각형 점선"
            else:
                painter.drawEllipse(self._shape_rect)
                label = "○ 원/타원 점선"
            painter.setPen(QColor(200, 100, 250))
            f = painter.font()
            f.setBold(True)
            f.setPointSize(9)
            painter.setFont(f)
            painter.drawText(self._shape_rect.x() + 5, self._shape_rect.y() - 6, label)

    # ------------------------------------------------------------------ #
    #  이벤트
    # ------------------------------------------------------------------ #
    def leaveEvent(self, event):
        if self._minimap_hovered:
            self._minimap_hovered = False
            self.update()
        super().leaveEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._pil_image:
            self._refresh_pixmap()

    def wheelEvent(self, event):
        """마우스 휠 줌"""
        if self._pixmap is None:
            return
        delta = event.angleDelta().y()
        if delta == 0:
            return
        factor = 1.12 if delta > 0 else 1 / 1.12
        self._apply_zoom(factor, event.position().toPoint())
        event.accept()

    def mousePressEvent(self, event):
        pos = event.position().toPoint()

        # 미니맵 리사이즈 핸들 검사
        mr = self._minimap_rect()
        if not mr.isEmpty():
            hs = 10
            resize_zone = QRect(mr.right() - hs, mr.bottom() - hs, hs, hs)
            if resize_zone.contains(pos):
                self._minimap_resize_start = (pos, self._minimap_w)
                self.setCursor(QCursor(Qt.CursorShape.SizeFDiagCursor))
                return

        # 가운데 버튼: 패닝 시작
        if event.button() == Qt.MouseButton.MiddleButton:
            self._pan_start = pos
            self._pan_start_offset = QPoint(self._pan_offset)
            self.setCursor(QCursor(Qt.CursorShape.ClosedHandCursor))
            return

        if event.button() != Qt.MouseButton.LeftButton:
            return

        # MODE_NONE: 오버레이 선택 / 드래그 / 패닝
        if self._mode == self.MODE_NONE:
            hit = self._hit_overlay(pos) if self._overlays else -1

            if hit >= 0:
                # 코너 리사이즈 핸들 우선 검사
                corner = self._hit_corner_handle(pos, hit)
                if corner >= 0:
                    self._active_overlay = hit
                    self._base_selected = False
                    self._ov_resize_corner = corner
                    ov = self._overlays[hit]
                    self._ov_resize_start = (
                        pos,
                        ov['x'], ov['y'],
                        ov.get('disp_w', ov['pil'].width),
                        ov.get('disp_h', ov['pil'].height),
                    )
                    resize_cursors = [
                        Qt.CursorShape.SizeFDiagCursor,
                        Qt.CursorShape.SizeBDiagCursor,
                        Qt.CursorShape.SizeBDiagCursor,
                        Qt.CursorShape.SizeFDiagCursor,
                    ]
                    self.setCursor(QCursor(resize_cursors[corner]))
                    self.overlay_selected.emit(hit)
                    self.update()
                    return
                # 오버레이 드래그
                self._active_overlay = hit
                self._base_selected = False
                self._ov_drag_start = pos
                self._ov_drag_start_pos = (
                    self._overlays[hit]['x'], self._overlays[hit]['y']
                )
                self.setCursor(QCursor(Qt.CursorShape.ClosedHandCursor))
                self.overlay_selected.emit(hit)
                self.update()
                return
            else:
                # 빈 공간 클릭 → 선택 해제 + 캔버스 패닝
                self._active_overlay = -1
                self._base_selected = False
                self.overlay_selected.emit(-1)
                self.update()
                self._left_pan_start = pos
                self._left_pan_start_offset = QPoint(self._pan_offset)
                self.setCursor(QCursor(Qt.CursorShape.ClosedHandCursor))
                return

        # 다각형 모드
        if self._mode == self.MODE_POLYGON:
            img_pt = self._widget_to_image(pos)
            widget_pts = [self._image_to_widget(x, y) for x, y in self._poly_image_pts]
            if len(self._poly_image_pts) >= 3 and widget_pts and \
                    self._is_near(pos, widget_pts[0], 14):
                self._close_polygon()
            else:
                self._poly_image_pts.append((img_pt.x(), img_pt.y()))
                self.update()
            return

        # 크기 지정 크롭 미리보기 드래그
        if self._mode == self.MODE_CROP_SIZE and self._crop_preview_rect:
            img_pt = self._widget_to_image(pos)
            if self._crop_preview_rect.contains(QPoint(img_pt.x(), img_pt.y())):
                self._crop_drag_start = pos
                self._crop_drag_start_rect = QRect(self._crop_preview_rect)
                self.setCursor(QCursor(Qt.CursorShape.ClosedHandCursor))
            return

        # 스포이드 — 픽셀 색상 추출
        if self._mode == self.MODE_PIPETTE:
            if self._pil_image:
                img_pt = self._widget_to_image(pos)
                pixel = self._pil_image.convert("RGBA").getpixel(
                    (img_pt.x(), img_pt.y()))
                self.color_sampled.emit(*pixel)
            return

        # 채우기
        if self._mode == self.MODE_FILL:
            if self._pil_image:
                img_pt = self._widget_to_image(pos)
                self.fill_applied.emit(img_pt.x(), img_pt.y())
            return

        # 도형 그리기 모드
        if self._mode in (self.MODE_SHAPE_RECT, self.MODE_SHAPE_ELLIPSE):
            self._shape_drag_start = pos
            self._shape_rect = None
            return

        # 인페인팅 드래그 모드
        if self._mode == self.MODE_INPAINT:
            self._inpaint_drag_start = pos
            self._inpaint_rect = None
            return

        # 텍스트 삽입 모드 — 드래그로 텍스트 박스 영역 선택
        if self._mode == self.MODE_TEXT:
            if self._pil_image:
                self._text_drag_start = pos
                self._text_rect = None
            return

        self._drag_start = pos
        self._selection_rect = None

        if self._mode == self.MODE_BRUSH:
            self._drawing = True
            self._draw_brush(pos)
        elif self._mode == self.MODE_COLOR_BRUSH:
            if self._color_brush_mask is None:
                self._init_color_brush_mask()
            self._color_drawing = True
            self._draw_color_brush(pos)

    def mouseMoveEvent(self, event):
        pos = event.position().toPoint()

        # 미니맵 리사이즈
        if self._minimap_resize_start is not None:
            start_pos, start_w = self._minimap_resize_start
            dx = pos.x() - start_pos.x()
            self._minimap_w = max(60, min(start_w + dx, 320))
            self.update()
            return

        # 왼쪽 버튼 패닝
        if self._left_pan_start is not None:
            delta = pos - self._left_pan_start
            self._pan_offset = self._left_pan_start_offset + delta
            self.update()
            return

        # 오버레이 리사이즈
        if self._ov_resize_start is not None and self._ov_resize_corner >= 0:
            start_pos, ox, oy, orig_w, orig_h = self._ov_resize_start
            delta = pos - start_pos
            s = self._scale * self._zoom
            dx = int(delta.x() / s) if s > 0 else 0
            dy = int(delta.y() / s) if s > 0 else 0
            corner = self._ov_resize_corner
            MIN_SIZE = 20
            idx = self._active_overlay
            if 0 <= idx < len(self._overlays):
                ov = self._overlays[idx]
                if corner == 0:   # TL
                    new_w = max(MIN_SIZE, orig_w - dx)
                    new_h = max(MIN_SIZE, orig_h - dy)
                    ov['x'] = ox + orig_w - new_w
                    ov['y'] = oy + orig_h - new_h
                elif corner == 1:  # TR
                    new_w = max(MIN_SIZE, orig_w + dx)
                    new_h = max(MIN_SIZE, orig_h - dy)
                    ov['y'] = oy + orig_h - new_h
                elif corner == 2:  # BL
                    new_w = max(MIN_SIZE, orig_w - dx)
                    new_h = max(MIN_SIZE, orig_h + dy)
                    ov['x'] = ox + orig_w - new_w
                else:              # BR
                    new_w = max(MIN_SIZE, orig_w + dx)
                    new_h = max(MIN_SIZE, orig_h + dy)
                ov['disp_w'] = new_w
                ov['disp_h'] = new_h
                self.update()
            return

        # 오버레이 드래그 (기본 이미지 영역 밖으로도 자유롭게 이동)
        if self._ov_drag_start is not None and self._ov_drag_start_pos is not None:
            delta = pos - self._ov_drag_start
            s = self._scale * self._zoom
            dx = int(delta.x() / s) if s > 0 else 0
            dy = int(delta.y() / s) if s > 0 else 0
            idx = self._active_overlay
            if 0 <= idx < len(self._overlays):
                ov = self._overlays[idx]
                ov['x'] = self._ov_drag_start_pos[0] + dx
                ov['y'] = self._ov_drag_start_pos[1] + dy
                self.update()
            return

        # 패닝
        if self._pan_start is not None:
            delta = pos - self._pan_start
            self._pan_offset = self._pan_start_offset + delta
            self.update()
            return

        if self._mode == self.MODE_POLYGON:
            self._cursor_pos = pos
            self.update()
            return

        # 크기 지정 크롭 드래그
        if self._mode == self.MODE_CROP_SIZE and self._crop_drag_start is not None:
            delta = pos - self._crop_drag_start
            eff_scale = self._scale * self._zoom
            dx = int(delta.x() / eff_scale) if eff_scale > 0 else 0
            dy = int(delta.y() / eff_scale) if eff_scale > 0 else 0
            if self._pil_image and self._crop_drag_start_rect:
                iw, ih = self._pil_image.size
                cr = self._crop_drag_start_rect
                nx = max(0, min(cr.x() + dx, iw - cr.width()))
                ny = max(0, min(cr.y() + dy, ih - cr.height()))
                self._crop_preview_rect = QRect(nx, ny, cr.width(), cr.height())
                self.update()
            return

        if self._mode in (self.MODE_CROP, self.MODE_GRABCUT) and self._drag_start:
            self._selection_rect = QRect(self._drag_start, pos).normalized()
            self.update()
        elif self._mode == self.MODE_BRUSH and self._drawing:
            self._draw_brush(pos)
        elif self._mode == self.MODE_COLOR_BRUSH and self._color_drawing:
            self._draw_color_brush(pos)
        elif self._mode in (self.MODE_SHAPE_RECT, self.MODE_SHAPE_ELLIPSE) and self._shape_drag_start:
            self._shape_rect = QRect(self._shape_drag_start, pos).normalized()
            self.update()
        elif self._mode == self.MODE_INPAINT and self._inpaint_drag_start:
            self._inpaint_rect = QRect(self._inpaint_drag_start, pos).normalized()
            self.update()
        elif self._mode == self.MODE_TEXT and self._text_drag_start:
            self._text_rect = QRect(self._text_drag_start, pos).normalized()
            self.update()

        # 호버 상태 업데이트 (미니맵 + 오버레이 커서)
        self._update_hover_state(pos)

    def mouseReleaseEvent(self, event):
        pos = event.position().toPoint()

        # 미니맵 리사이즈 종료
        if self._minimap_resize_start is not None:
            self._minimap_resize_start = None
            self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
            return

        # 왼쪽 버튼 패닝 종료
        if self._left_pan_start is not None and event.button() == Qt.MouseButton.LeftButton:
            self._left_pan_start = None
            self._left_pan_start_offset = None
            cursors = {
                self.MODE_BRUSH:         Qt.CursorShape.CrossCursor,
                self.MODE_CROP:          Qt.CursorShape.CrossCursor,
                self.MODE_GRABCUT:       Qt.CursorShape.CrossCursor,
                self.MODE_POLYGON:       Qt.CursorShape.CrossCursor,
                self.MODE_CROP_SIZE:     Qt.CursorShape.SizeAllCursor,
                self.MODE_PIPETTE:       Qt.CursorShape.CrossCursor,
                self.MODE_FILL:          Qt.CursorShape.CrossCursor,
                self.MODE_COLOR_BRUSH:   Qt.CursorShape.CrossCursor,
                self.MODE_SHAPE_RECT:    Qt.CursorShape.CrossCursor,
                self.MODE_SHAPE_ELLIPSE: Qt.CursorShape.CrossCursor,
                self.MODE_INPAINT:       Qt.CursorShape.CrossCursor,
            }
            self.setCursor(QCursor(cursors.get(self._mode, Qt.CursorShape.ArrowCursor)))

        # 오버레이 리사이즈 종료
        if self._ov_resize_start is not None:
            self._ov_resize_start = None
            self._ov_resize_corner = -1
            idx = self._active_overlay
            if 0 <= idx < len(self._overlays):
                ov = self._overlays[idx]
                self.overlay_moved.emit(idx, ov['x'], ov['y'])
            self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
            return

        # 오버레이 드래그 종료
        if self._ov_drag_start is not None:
            self._ov_drag_start = None
            idx = self._active_overlay
            if 0 <= idx < len(self._overlays):
                ov = self._overlays[idx]
                self.overlay_moved.emit(idx, ov['x'], ov['y'])
            self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
            return

        # 가운데 버튼 패닝 종료
        if event.button() == Qt.MouseButton.MiddleButton:
            self._pan_start = None
            # 모드에 맞는 커서로 복원
            self.set_mode(self._mode)
            return

        if event.button() != Qt.MouseButton.LeftButton:
            return

        # 크기 지정 크롭 드래그 종료
        if self._mode == self.MODE_CROP_SIZE:
            self._crop_drag_start = None
            self._crop_drag_start_rect = None
            self.setCursor(QCursor(Qt.CursorShape.SizeAllCursor))
            return

        if self._mode == self.MODE_CROP and self._drag_start:
            rect = QRect(self._drag_start, pos).normalized()
            self._selection_rect = None
            self.update()
            self._emit_rect_signal(rect, self.crop_selected)

        elif self._mode == self.MODE_GRABCUT and self._drag_start:
            rect = QRect(self._drag_start, pos).normalized()
            self._selection_rect = None
            self.update()
            self._emit_rect_signal(rect, self.grabcut_selected)

        elif self._mode == self.MODE_BRUSH:
            self._drawing = False
            if self._brush_mask is not None:
                self.brush_stroke_done.emit(self._brush_mask.copy())

        elif self._mode == self.MODE_COLOR_BRUSH:
            self._color_drawing = False
            if (self._color_brush_mask is not None
                    and (self._color_brush_mask == 255).any()):
                self.color_brush_done.emit(self._color_brush_mask.copy())
                # 스트로크 커밋 후 마스크/오버레이 초기화 (다음 스트로크 준비)
                self._color_brush_mask = None
                self._color_brush_overlay = None

        elif self._mode in (self.MODE_SHAPE_RECT, self.MODE_SHAPE_ELLIPSE):
            if self._shape_drag_start and self._shape_rect:
                rect = QRect(self._shape_drag_start, pos).normalized()
                self._shape_rect = None
                self.update()
                self._emit_shape_signal(rect)
            self._shape_drag_start = None

        elif self._mode == self.MODE_INPAINT:
            if self._inpaint_drag_start and self._inpaint_rect:
                rect = QRect(self._inpaint_drag_start, pos).normalized()
                self._inpaint_rect = None
                self.update()
                self._emit_inpaint_signal(rect)
            self._inpaint_drag_start = None

        elif self._mode == self.MODE_TEXT:
            if self._text_drag_start and self._text_rect:
                rect = QRect(self._text_drag_start, pos).normalized()
                self._text_rect = None
                self.update()
                if rect.width() > 5 and rect.height() > 5:
                    self._emit_text_rect_signal(rect)
            self._text_drag_start = None

        self._drag_start = None

    def mouseDoubleClickEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return

        # 다각형 더블클릭 완성
        if self._mode == self.MODE_POLYGON and len(self._poly_image_pts) >= 3:
            self._poly_image_pts.pop()
            self._close_polygon()
            return

        # 크기 지정 크롭 더블클릭 확정
        if self._mode == self.MODE_CROP_SIZE and self._crop_preview_rect:
            r = self._crop_preview_rect
            self._crop_preview_rect = None
            self.update()
            self.crop_size_committed.emit(r.x(), r.y(), r.width(), r.height())

    def commit_crop_size(self):
        """Enter 키로 크기 지정 크롭 확정"""
        if self._mode == self.MODE_CROP_SIZE and self._crop_preview_rect:
            r = self._crop_preview_rect
            self._crop_preview_rect = None
            self.update()
            self.crop_size_committed.emit(r.x(), r.y(), r.width(), r.height())

    # ------------------------------------------------------------------ #
    #  내부 유틸
    # ------------------------------------------------------------------ #
    def _update_hover_state(self, pos: QPoint):
        """미니맵 호버 및 MODE_NONE 커서 업데이트"""
        mr = self._minimap_rect()
        prev_hovered = self._minimap_hovered
        self._minimap_hovered = not mr.isEmpty() and mr.contains(pos)
        if prev_hovered != self._minimap_hovered:
            self.update()

        # 커서는 드래그 없는 MODE_NONE 일 때만 변경
        if (self._ov_drag_start is not None or self._ov_resize_start is not None
                or self._left_pan_start is not None or self._pan_start is not None):
            return

        if self._minimap_hovered:
            hs = 10
            resize_zone = QRect(mr.right() - hs, mr.bottom() - hs, hs, hs)
            self.setCursor(QCursor(
                Qt.CursorShape.SizeFDiagCursor if resize_zone.contains(pos)
                else Qt.CursorShape.ArrowCursor
            ))
            return

        if self._mode != self.MODE_NONE:
            return

        hit = self._hit_overlay(pos)
        if hit >= 0:
            corner = self._hit_corner_handle(pos, hit)
            if corner >= 0:
                resize_cursors = [
                    Qt.CursorShape.SizeFDiagCursor,
                    Qt.CursorShape.SizeBDiagCursor,
                    Qt.CursorShape.SizeBDiagCursor,
                    Qt.CursorShape.SizeFDiagCursor,
                ]
                self.setCursor(QCursor(resize_cursors[corner]))
            else:
                self.setCursor(QCursor(Qt.CursorShape.OpenHandCursor))
        else:
            self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))

    def _overlay_widget_rect(self, index: int) -> QRect:
        """오버레이의 위젯 좌표 사각형"""
        ov = self._overlays[index]
        img_rect = self.get_image_rect()
        s = self._scale * self._zoom
        x = int(img_rect.x() + ov['x'] * s)
        y = int(img_rect.y() + ov['y'] * s)
        w = int(ov.get('disp_w', ov['pil'].width) * s)
        h = int(ov.get('disp_h', ov['pil'].height) * s)
        return QRect(x, y, w, h)

    def _get_corner_handles(self, index: int) -> list:
        """Active overlay 의 4 코너 핸들 사각형 (위젯 좌표)"""
        r = self._overlay_widget_rect(index)
        hs = 5
        return [
            QRect(r.left() - hs, r.top() - hs, hs * 2, hs * 2),     # 0: TL
            QRect(r.right() - hs, r.top() - hs, hs * 2, hs * 2),    # 1: TR
            QRect(r.left() - hs, r.bottom() - hs, hs * 2, hs * 2),  # 2: BL
            QRect(r.right() - hs, r.bottom() - hs, hs * 2, hs * 2), # 3: BR
        ]

    def _hit_corner_handle(self, pos: QPoint, index: int) -> int:
        for i, r in enumerate(self._get_corner_handles(index)):
            if r.contains(pos):
                return i
        return -1

    def _minimap_rect(self) -> QRect:
        """원본 미리보기 사각형 (위젯 우상단 고정)"""
        src = self._orig_pixmap or self._pixmap
        if src is None:
            return QRect()
        HEADER_H = 18
        aspect = src.height() / max(src.width(), 1)
        mh = max(60, int(self._minimap_w * aspect) + HEADER_H)
        margin = 8
        x = self.width() - self._minimap_w - margin
        y = margin
        return QRect(x, y, self._minimap_w, mh)

    def _hit_overlay(self, pos: QPoint) -> int:
        """pos에 있는 최상위 오버레이 인덱스 반환, 없으면 -1"""
        for i in range(len(self._overlays) - 1, -1, -1):
            if not self._overlays[i].get('visible', True):
                continue
            if self._overlay_widget_rect(i).contains(pos):
                return i
        return -1

    # ── 드래그 앤 드롭 ────────────────────────────────────────────────── #
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            from PyQt6.QtCore import QUrl
            for url in event.mimeData().urls():
                if self._is_img(url.toLocalFile()):
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dropEvent(self, event):
        pos = event.position().toPoint()
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if self._is_img(path):
                self.file_dropped.emit(path, pos)
                break
        event.acceptProposedAction()

    @staticmethod
    def _is_img(path: str) -> bool:
        import os
        return os.path.splitext(path)[1].lower() in {
            '.png', '.jpg', '.jpeg', '.bmp', '.webp', '.tiff', '.tif', '.gif'
        }

    def _is_near(self, a: QPoint, b: QPoint, threshold: int) -> bool:
        dx, dy = a.x() - b.x(), a.y() - b.y()
        return dx * dx + dy * dy <= threshold * threshold

    def _close_polygon(self):
        if len(self._poly_image_pts) < 3:
            return
        points = list(self._poly_image_pts)
        self._poly_image_pts = []
        self._cursor_pos = None
        self.update()
        self.polygon_closed.emit(points)

    def _emit_rect_signal(self, widget_rect: QRect, signal):
        img_tl = self._widget_to_image(widget_rect.topLeft())
        img_br = self._widget_to_image(widget_rect.bottomRight())
        x, y = img_tl.x(), img_tl.y()
        w = img_br.x() - x
        h = img_br.y() - y
        if w > 0 and h > 0:
            signal.emit(x, y, w, h)

    def _emit_shape_signal(self, widget_rect: QRect):
        """위젯 좌표 rect → 이미지 좌표로 변환 후 shape_committed 발생"""
        if self._pil_image is None:
            return
        img_tl = self._widget_to_image(widget_rect.topLeft())
        img_br = self._widget_to_image(widget_rect.bottomRight())
        x, y = img_tl.x(), img_tl.y()
        w = max(1, img_br.x() - x)
        h = max(1, img_br.y() - y)
        self.shape_committed.emit(self._mode, x, y, w, h)

    def _emit_inpaint_signal(self, widget_rect: QRect):
        """위젯 좌표 rect → 이미지 좌표로 변환 후 inpaint_committed 발생"""
        if self._pil_image is None:
            return
        img_tl = self._widget_to_image(widget_rect.topLeft())
        img_br = self._widget_to_image(widget_rect.bottomRight())
        x, y = img_tl.x(), img_tl.y()
        w = max(1, img_br.x() - x)
        h = max(1, img_br.y() - y)
        self.inpaint_committed.emit(x, y, w, h)

    def _emit_text_rect_signal(self, widget_rect: QRect):
        """위젯 좌표 rect → 이미지 좌표로 변환 후 text_rect_selected 발생"""
        if self._pil_image is None:
            return
        img_tl = self._widget_to_image(widget_rect.topLeft())
        img_br = self._widget_to_image(widget_rect.bottomRight())
        x, y = img_tl.x(), img_tl.y()
        w = max(1, img_br.x() - x)
        h = max(1, img_br.y() - y)
        self.text_rect_selected.emit(x, y, w, h)

    def _draw_brush(self, widget_pos: QPoint):
        if self._pil_image is None or self._brush_mask is None:
            return
        img_pt = self._widget_to_image(widget_pos)
        ix, iy = img_pt.x(), img_pt.y()

        h, w = self._brush_mask.shape
        half = self._brush_size // 2
        y1, y2 = max(0, iy - half), min(h, iy + half)
        x1, x2 = max(0, ix - half), min(w, ix + half)
        self._brush_mask[y1:y2, x1:x2] = 255

        if self._brush_overlay is None:
            self._brush_overlay = QPixmap(self._pixmap.size())
            self._brush_overlay.fill(Qt.GlobalColor.transparent)

        painter = QPainter(self._brush_overlay)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(220, 50, 50, 180))
        scaled_half = int(half * self._scale)
        sx = int(ix * self._scale) - scaled_half
        sy = int(iy * self._scale) - scaled_half
        painter.drawEllipse(sx, sy, scaled_half * 2, scaled_half * 2)
        painter.end()

        self.update()

    def _init_color_brush_mask(self):
        if self._pil_image is None:
            return
        w, h = self._pil_image.size
        self._color_brush_mask = np.zeros((h, w), dtype=np.uint8)

    def _draw_color_brush(self, widget_pos: QPoint):
        """색상 브러시 스트로크 — 마스크 업데이트 및 미리보기 렌더링"""
        if self._pil_image is None or self._color_brush_mask is None or self._pixmap is None:
            return
        img_pt = self._widget_to_image(widget_pos)
        ix, iy = img_pt.x(), img_pt.y()

        h, w = self._color_brush_mask.shape
        half = self._brush_size // 2
        y1, y2 = max(0, iy - half), min(h, iy + half)
        x1, x2 = max(0, ix - half), min(w, ix + half)
        self._color_brush_mask[y1:y2, x1:x2] = 255

        r, g, b, a = self._tool_color
        if self._color_brush_overlay is None:
            self._color_brush_overlay = QPixmap(self._pixmap.size())
            self._color_brush_overlay.fill(Qt.GlobalColor.transparent)

        painter = QPainter(self._color_brush_overlay)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(r, g, b, min(a, 200)))
        scaled_half = int(half * self._scale)
        sx = int(ix * self._scale) - scaled_half
        sy = int(iy * self._scale) - scaled_half
        painter.drawEllipse(sx, sy, scaled_half * 2, scaled_half * 2)
        painter.end()

        self.update()

