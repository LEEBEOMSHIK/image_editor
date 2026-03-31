"""
core/image_processor.py
이미지 처리 핵심 로직 (Pillow, OpenCV, rembg 활용)
"""
import copy
import numpy as np
from PIL import Image, ImageFilter, ImageEnhance
import cv2

# rembg/onnxruntime은 반드시 Qt보다 먼저 import되어야 합니다 (main.py 참조)
# DLL 충돌을 피하기 위해 모듈 로드 시점에 미리 import합니다.
try:
    from rembg import remove as _rembg_remove
    _REMBG_AVAILABLE = True
except (ImportError, SystemExit):
    _rembg_remove = None
    _REMBG_AVAILABLE = False


class ImageProcessor:
    """
    이미지 처리 클래스.
    모든 편집 작업과 Undo/Redo 히스토리를 관리합니다.
    """

    MAX_HISTORY = 30

    def __init__(self):
        self._original: Image.Image | None = None  # 최초 원본
        self._current: Image.Image | None = None   # 현재 편집 상태
        self._history: list[Image.Image] = []      # Undo 스택
        self._redo_stack: list[Image.Image] = []   # Redo 스택

    # ------------------------------------------------------------------ #
    #  프로퍼티
    # ------------------------------------------------------------------ #
    @property
    def has_image(self) -> bool:
        return self._current is not None

    @property
    def current_image(self) -> Image.Image | None:
        return self._current

    @property
    def original_image(self) -> Image.Image | None:
        return self._original

    # ------------------------------------------------------------------ #
    #  히스토리 관리
    # ------------------------------------------------------------------ #
    def _push_history(self):
        """현재 상태를 Undo 스택에 저장"""
        if self._current is not None:
            self._history.append(self._current.copy())
            if len(self._history) > self.MAX_HISTORY:
                self._history.pop(0)
            self._redo_stack.clear()

    def can_undo(self) -> bool:
        return len(self._history) > 0

    def can_redo(self) -> bool:
        return len(self._redo_stack) > 0

    def undo(self) -> bool:
        if not self.can_undo():
            return False
        self._redo_stack.append(self._current.copy())
        self._current = self._history.pop()
        return True

    def redo(self) -> bool:
        if not self.can_redo():
            return False
        self._history.append(self._current.copy())
        self._current = self._redo_stack.pop()
        return True

    # ------------------------------------------------------------------ #
    #  파일 I/O
    # ------------------------------------------------------------------ #
    def load(self, path: str) -> Image.Image:
        img = Image.open(path)
        if img.mode not in ("RGB", "RGBA"):
            img = img.convert("RGBA")
        self._original = img.copy()
        self._current = img.copy()
        self._history.clear()
        self._redo_stack.clear()
        return self._current

    def new_blank(self, width: int, height: int,
                  bg_color: tuple = (255, 255, 255, 255)) -> Image.Image:
        """지정 크기의 새 빈 RGBA 이미지를 생성합니다."""
        self._original = Image.new("RGBA", (width, height), bg_color)
        self._current = self._original.copy()
        self._history.clear()
        self._redo_stack.clear()
        return self._current

    def load_pil(self, pil_img: Image.Image) -> Image.Image:
        """PIL 이미지를 직접 로드합니다 (파일 경로 없이)."""
        img = pil_img.convert("RGBA") if pil_img.mode != "RGBA" else pil_img.copy()
        self._original = img.copy()
        self._current = img.copy()
        self._history.clear()
        self._redo_stack.clear()
        return self._current

    def save(self, path: str, fmt: str = "PNG"):
        if self._current is None:
            raise ValueError("저장할 이미지가 없습니다.")
        fmt = fmt.upper()
        img = self._current.copy()

        if fmt == "JPG" or fmt == "JPEG":
            if img.mode == "RGBA":
                bg = Image.new("RGB", img.size, (255, 255, 255))
                bg.paste(img, mask=img.split()[3])
                img = bg
            else:
                img = img.convert("RGB")
            img.save(path, format="JPEG", quality=95)
        elif fmt == "PDF":
            if img.mode == "RGBA":
                bg = Image.new("RGB", img.size, (255, 255, 255))
                bg.paste(img, mask=img.split()[3])
                img = bg
            else:
                img = img.convert("RGB")
            img.save(path, format="PDF")
        else:  # PNG
            img.save(path, format="PNG")

    def reset_to_original(self):
        """원본으로 초기화"""
        if self._original is not None:
            self._push_history()
            self._current = self._original.copy()

    # ------------------------------------------------------------------ #
    #  배경 제거
    # ------------------------------------------------------------------ #
    def remove_background_auto(self) -> Image.Image:
        """rembg를 이용한 자동 배경 제거"""
        if self._current is None:
            raise ValueError("이미지를 먼저 불러오세요.")
        if not _REMBG_AVAILABLE:
            raise ImportError(
                "rembg 라이브러리를 불러올 수 없습니다.\n"
                "터미널에서 다음 명령을 실행하세요:\n"
                '  pip install "rembg[cpu]"'
            )
        self._push_history()
        result = _rembg_remove(self._current)
        self._current = result
        return self._current

    def remove_background_grabcut(
        self,
        rect: tuple[int, int, int, int],  # (x, y, w, h) in image coords
    ) -> Image.Image:
        """GrabCut 알고리즘으로 배경 제거"""
        if self._current is None:
            raise ValueError("이미지를 먼저 불러오세요.")
        self._push_history()

        cv_img = self._pil_to_cv(self._current)
        mask = np.zeros(cv_img.shape[:2], np.uint8)
        bg_model = np.zeros((1, 65), np.float64)
        fg_model = np.zeros((1, 65), np.float64)

        cv2.grabCut(cv_img, mask, rect, bg_model, fg_model, 5, cv2.GC_INIT_WITH_RECT)
        mask2 = np.where((mask == 2) | (mask == 0), 0, 1).astype("uint8")

        result_cv = cv_img * mask2[:, :, np.newaxis]
        alpha = (mask2 * 255).astype(np.uint8)

        rgba = cv2.cvtColor(result_cv, cv2.COLOR_BGR2RGBA)
        rgba[:, :, 3] = alpha

        self._current = Image.fromarray(rgba)
        return self._current

    def apply_brush_mask(self, mask_array: np.ndarray) -> Image.Image:
        """
        브러시로 그린 마스크를 적용해 배경 제거.
        mask_array: 0=유지, 255=제거 (이미지와 같은 크기, uint8)
        """
        if self._current is None:
            raise ValueError("이미지를 먼저 불러오세요.")
        self._push_history()

        img = self._current.convert("RGBA")
        arr = np.array(img)
        # 마스크가 255인 픽셀의 알파를 0으로
        remove_mask = mask_array == 255
        arr[remove_mask, 3] = 0
        self._current = Image.fromarray(arr)
        return self._current

    def fill_color(self, x: int, y: int,
                   fill_rgba: tuple, tolerance: int = 32) -> Image.Image:
        """플러드 필 — 클릭 위치부터 유사한 색 영역을 fill_rgba 색으로 채운다."""
        if self._current is None:
            raise ValueError("이미지를 먼저 불러오세요.")
        self._push_history()
        from PIL import ImageDraw
        img = self._current.convert("RGBA")
        x = max(0, min(x, img.width - 1))
        y = max(0, min(y, img.height - 1))
        r, g, b, a = (fill_rgba + (255,))[:4]
        ImageDraw.floodfill(img, (x, y), (r, g, b, a), thresh=tolerance)
        self._current = img
        return self._current

    def apply_color_brush(self, mask: np.ndarray,
                          fill_rgba: tuple) -> Image.Image:
        """브러시로 칠한 영역(mask==255)에 fill_rgba 색상을 적용한다."""
        if self._current is None:
            raise ValueError("이미지를 먼저 불러오세요.")
        self._push_history()
        img = self._current.convert("RGBA")
        arr = np.array(img)
        r, g, b, a = (fill_rgba + (255,))[:4]
        hit = mask == 255
        arr[hit, 0] = r
        arr[hit, 1] = g
        arr[hit, 2] = b
        arr[hit, 3] = a
        self._current = Image.fromarray(arr, "RGBA")
        return self._current

    def merge_overlay(self, overlay_pil: Image.Image, x: int, y: int) -> Image.Image:
        """오버레이 이미지를 현재 이미지에 알파 합성"""
        if self._current is None:
            raise ValueError("기본 이미지가 없습니다.")
        self._push_history()
        base = self._current.convert("RGBA")
        ov = overlay_pil.convert("RGBA")
        base.paste(ov, (x, y), ov)
        self._current = base
        return self._current

    def crop_by_polygon(self, points: list[tuple[int, int]]) -> Image.Image:
        """다각형 영역만 남기고 나머지 투명 처리"""
        from PIL import ImageDraw, ImageChops
        if self._current is None:
            raise ValueError("이미지를 먼저 불러오세요.")
        if len(points) < 3:
            raise ValueError("꼭짓점이 3개 이상 필요합니다.")
        self._push_history()
        img = self._current.convert("RGBA")
        mask = Image.new("L", img.size, 0)
        ImageDraw.Draw(mask).polygon(points, fill=255)
        r, g, b, a = img.split()
        new_a = ImageChops.multiply(a, mask)
        self._current = Image.merge("RGBA", (r, g, b, new_a))
        return self._current

    # ------------------------------------------------------------------ #
    #  크롭
    # ------------------------------------------------------------------ #
    def crop_by_rect(self, x: int, y: int, w: int, h: int) -> Image.Image:
        """좌표 기반 크롭"""
        if self._current is None:
            raise ValueError("이미지를 먼저 불러오세요.")
        self._push_history()
        self._current = self._current.crop((x, y, x + w, y + h))
        return self._current

    def crop_by_size(self, width: int, height: int, anchor: str = "center") -> Image.Image:
        """너비/높이 입력 기반 크롭 (중앙 기준)"""
        if self._current is None:
            raise ValueError("이미지를 먼저 불러오세요.")
        iw, ih = self._current.size
        if anchor == "center":
            x = max(0, (iw - width) // 2)
            y = max(0, (ih - height) // 2)
        else:
            x, y = 0, 0
        w = min(width, iw - x)
        h = min(height, ih - y)
        return self.crop_by_rect(x, y, w, h)

    # ------------------------------------------------------------------ #
    #  리사이즈
    # ------------------------------------------------------------------ #
    def resize(self, width: int, height: int, keep_ratio: bool = True) -> Image.Image:
        if self._current is None:
            raise ValueError("이미지를 먼저 불러오세요.")
        self._push_history()
        if keep_ratio:
            self._current.thumbnail((width, height), Image.LANCZOS)
        else:
            self._current = self._current.resize((width, height), Image.LANCZOS)
        return self._current

    # ------------------------------------------------------------------ #
    #  필터 (확장 가능한 구조)
    # ------------------------------------------------------------------ #
    def apply_filter(self, filter_name: str, **kwargs) -> Image.Image:
        """
        필터 적용. filter_name으로 확장 가능.
        지원: grayscale, blur, sharpen, brightness, contrast, sepia
        """
        if self._current is None:
            raise ValueError("이미지를 먼저 불러오세요.")
        self._push_history()

        img = self._current.copy()

        if filter_name == "grayscale":
            converted = img.convert("L").convert("RGBA")
            if img.mode == "RGBA":
                converted.putalpha(img.split()[3])
            self._current = converted

        elif filter_name == "blur":
            radius = kwargs.get("radius", 2)
            self._current = img.filter(ImageFilter.GaussianBlur(radius=radius))

        elif filter_name == "sharpen":
            self._current = img.filter(ImageFilter.SHARPEN)

        elif filter_name == "brightness":
            factor = kwargs.get("factor", 1.2)
            self._current = ImageEnhance.Brightness(img).enhance(factor)

        elif filter_name == "contrast":
            factor = kwargs.get("factor", 1.2)
            self._current = ImageEnhance.Contrast(img).enhance(factor)

        elif filter_name == "sepia":
            gray = img.convert("L")
            r = gray.point(lambda p: min(255, p * 1.1))
            g = gray.point(lambda p: min(255, p * 0.9))
            b = gray.point(lambda p: min(255, p * 0.7))
            sepia = Image.merge("RGB", (r, g, b)).convert("RGBA")
            if img.mode == "RGBA":
                sepia.putalpha(img.split()[3])
            self._current = sepia

        else:
            raise ValueError(f"알 수 없는 필터: {filter_name}")

        return self._current

    # ------------------------------------------------------------------ #
    #  도형 그리기
    # ------------------------------------------------------------------ #
    def draw_dotted_shape(self, shape: str, x: int, y: int, w: int, h: int,
                          color: tuple = (255, 0, 0, 255),
                          line_width: int = 2, dash_len: int = 12) -> Image.Image:
        """
        점선 도형을 현재 이미지에 그린다.
        shape: 'rect' (사각형) 또는 'ellipse' (원/타원)
        color: (r, g, b) 또는 (r, g, b, a)
        """
        import math
        from PIL import ImageDraw
        if self._current is None:
            raise ValueError("이미지를 먼저 불러오세요.")
        self._push_history()
        img = self._current.convert("RGBA")
        draw = ImageDraw.Draw(img)
        c = tuple((list(color) + [255])[:4])

        if shape == 'rect':
            x1, y1, x2, y2 = x, y, x + w, y + h
            # 상변·하변 (수평 점선)
            for fy in (y1, y2):
                cx = x1
                on = True
                while cx < x2:
                    ex = min(cx + dash_len, x2)
                    if on:
                        draw.line([(cx, fy), (ex, fy)], fill=c, width=line_width)
                    cx = ex
                    on = not on
            # 좌변·우변 (수직 점선)
            for fx in (x1, x2):
                cy = y1
                on = True
                while cy < y2:
                    ey = min(cy + dash_len, y2)
                    if on:
                        draw.line([(fx, cy), (fx, ey)], fill=c, width=line_width)
                    cy = ey
                    on = not on

        elif shape == 'ellipse':
            cx_f = x + w / 2
            cy_f = y + h / 2
            rx = w / 2
            ry = h / 2
            # 둘레 근사 (Ramanujan 공식)
            perimeter = math.pi * (3 * (rx + ry) -
                                   math.sqrt((3 * rx + ry) * (rx + 3 * ry)))
            steps = max(120, int(perimeter * 1.5))
            pts = [(cx_f + rx * math.cos(2 * math.pi * i / steps),
                    cy_f + ry * math.sin(2 * math.pi * i / steps))
                   for i in range(steps + 1)]
            seg_len = 0.0
            on = True
            for i in range(1, len(pts)):
                p0, p1 = pts[i - 1], pts[i]
                dist = math.dist(p0, p1)
                if on:
                    draw.line([p0, p1], fill=c, width=line_width)
                seg_len += dist
                if seg_len >= dash_len:
                    on = not on
                    seg_len = 0.0

        self._current = img
        return self._current

    # ------------------------------------------------------------------ #
    #  AI 인페인팅 (빈 영역 채우기)
    # ------------------------------------------------------------------ #
    def inpaint_region(self, x: int, y: int, w: int, h: int,
                       radius: int = 5) -> Image.Image:
        """지정한 직사각형 영역의 투명 픽셀만 OpenCV Telea 인페인팅으로 채운다."""
        if self._current is None:
            raise ValueError("이미지를 먼저 불러오세요.")
        img_rgba = self._current.convert("RGBA")
        arr = np.array(img_rgba)
        ih, iw = arr.shape[:2]
        x1, y1 = max(0, x), max(0, y)
        x2, y2 = min(iw, x + w), min(ih, y + h)
        if x2 <= x1 or y2 <= y1:
            return self._current
        region = arr[y1:y2, x1:x2]
        mask_region = np.where(region[:, :, 3] < 128, 255, 0).astype(np.uint8)
        if mask_region.max() == 0:
            return self._current  # 해당 영역에 투명 픽셀 없음
        self._push_history()
        bgr_region = cv2.cvtColor(region[:, :, :3], cv2.COLOR_RGB2BGR)
        inpainted = cv2.inpaint(bgr_region, mask_region, radius, cv2.INPAINT_TELEA)
        result_rgb = cv2.cvtColor(inpainted, cv2.COLOR_BGR2RGB)
        result_arr = arr.copy()
        transparent = mask_region > 0
        result_arr[y1:y2, x1:x2][transparent, :3] = result_rgb[transparent]
        result_arr[y1:y2, x1:x2][transparent, 3] = 255
        self._current = Image.fromarray(result_arr, "RGBA")
        return self._current

    def inpaint_transparent(self, radius: int = 5) -> Image.Image:
        """
        투명(알파=0) 픽셀을 OpenCV Telea 인페인팅으로 주변 색을 채운다.
        반투명 픽셀(0 < alpha < 255)도 마스크에 포함하여 자연스럽게 블렌딩한다.
        """
        if self._current is None:
            raise ValueError("이미지를 먼저 불러오세요.")

        img_rgba = self._current.convert("RGBA")
        arr = np.array(img_rgba)
        alpha = arr[:, :, 3]

        # 알파가 128 미만인 픽셀을 인페인팅 대상으로
        mask = np.where(alpha < 128, 255, 0).astype(np.uint8)
        if mask.max() == 0:
            return self._current  # 투명 픽셀 없음 — 변경 없음

        self._push_history()

        bgr = cv2.cvtColor(arr[:, :, :3], cv2.COLOR_RGB2BGR)
        inpainted = cv2.inpaint(bgr, mask, radius, cv2.INPAINT_TELEA)
        result_rgb = cv2.cvtColor(inpainted, cv2.COLOR_BGR2RGB)

        result_arr = arr.copy()
        # 인페인팅된 색상을 투명 영역에 채우고 알파=255로 복원
        transparent = mask > 0
        result_arr[transparent, :3] = result_rgb[transparent]
        result_arr[transparent, 3] = 255

        self._current = Image.fromarray(result_arr, "RGBA")
        return self._current

    # ------------------------------------------------------------------ #
    #  내부 유틸
    # ------------------------------------------------------------------ #
    @staticmethod
    def _pil_to_cv(img: Image.Image) -> np.ndarray:
        img_rgb = img.convert("RGB")
        return cv2.cvtColor(np.array(img_rgb), cv2.COLOR_RGB2BGR)

    def get_size(self) -> tuple[int, int]:
        if self._current:
            return self._current.size
        return (0, 0)
