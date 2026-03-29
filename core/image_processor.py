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
