# Image Editor Pro — 기능 명세서 (function-spec.md)

Claude Code가 각 모듈·함수의 역할을 빠르게 파악할 수 있도록 작성된 참조 문서입니다.

---

## core/image_processor.py — `ImageProcessor`

이미지 연산의 핵심. PIL/OpenCV/rembg 연산과 Undo/Redo 히스토리를 관리합니다.

| 메서드 | 역할 |
|--------|------|
| `load(path)` | 파일에서 이미지 로드 → RGBA 변환, `_original` 저장 |
| `new_blank(w, h, bg_color)` | 빈 투명 캔버스 생성 |
| `load_pil(pil_img)` | PIL 이미지 직접 로드 (파일 경로 없이) |
| `save(path, fmt)` | PNG / JPG / PDF 저장 |
| `undo()` / `redo()` | 히스토리 스택 조작 (최대 30개) |
| `reset_to_original()` | 최초 로드 이미지로 복원 |
| `remove_background_auto()` | rembg AI 자동 배경 제거 |
| `remove_background_grabcut(rect)` | OpenCV GrabCut 배경 제거 |
| `apply_brush_mask(mask_array)` | numpy 마스크 영역 투명 처리 |
| `fill_color(x, y, fill_rgba, tolerance)` | 플러드 필 채우기 |
| `apply_color_brush(mask, fill_rgba)` | 색상 브러시 마스크 적용 |
| `merge_overlay(overlay_pil, x, y)` | 오버레이 알파 합성 |
| `crop_by_rect(x, y, w, h)` | 좌표 기반 크롭 |
| `crop_by_polygon(points)` | 다각형 영역 크롭 |
| `crop_by_size(width, height, anchor)` | 크기 지정 크롭 (중앙 기준) |
| `resize(width, height, keep_ratio)` | 리사이즈 |
| `apply_filter(filter_name, **kwargs)` | 필터 적용 (grayscale/blur/sharpen/brightness/contrast/sepia) |
| `draw_dotted_shape(shape, x, y, w, h, color, width)` | 점선 도형 합성 |
| `inpaint_region(x, y, w, h, radius)` | OpenCV 인페인팅 (빈 영역 채우기) |
| `inpaint_transparent(radius)` | 투명 영역 인페인팅 |
| `get_size()` | 현재 이미지 크기 반환 |

---

## ui/canvas.py — `ImageCanvas(QLabel)`

캔버스 위젯. 줌·패닝·오버레이·6가지 이상 편집 모드를 담당합니다.

### 편집 모드 상수

| 상수 | 값 | 동작 |
|------|-----|------|
| `MODE_NONE` | `"none"` | 이동·선택 (오버레이 드래그, 빈 공간 패닝) |
| `MODE_SELECT` | `"select"` | 선택/편집 — 텍스트 클릭 시 인라인 에디터 열기, 일반 오버레이는 드래그 |
| `MODE_CROP` | `"crop"` | 드래그 크롭 |
| `MODE_GRABCUT` | `"grabcut"` | GrabCut 선택 |
| `MODE_BRUSH` | `"brush"` | 브러시 마스크 드로잉 |
| `MODE_POLYGON` | `"polygon"` | 다각형 꼭짓점 클릭 |
| `MODE_CROP_SIZE` | `"crop_size"` | 크기 지정 크롭 미리보기 |
| `MODE_PIPETTE` | `"pipette"` | 스포이드 (색 추출) |
| `MODE_FILL` | `"fill"` | 채우기 (플러드 필) |
| `MODE_COLOR_BRUSH` | `"color_brush"` | 색상 브러시 |
| `MODE_SHAPE_RECT` | `"shape_rect"` | 점선 사각형 그리기 |
| `MODE_SHAPE_ELLIPSE` | `"shape_ellipse"` | 점선 원/타원 그리기 |
| `MODE_INPAINT` | `"inpaint"` | AI 인페인팅 영역 드래그 |
| `MODE_TEXT` | `"text"` | 텍스트 삽입 (드래그로 박스 지정, 기존 텍스트 클릭 시 재편집) |

### 주요 시그널

| 시그널 | 인수 | 설명 |
|--------|------|------|
| `zoom_changed` | `float` | 줌 배율 변경 |
| `crop_selected` | `int, int, int, int` | 크롭 영역 확정 (x, y, w, h) |
| `grabcut_selected` | `int, int, int, int` | GrabCut 영역 확정 |
| `brush_stroke_done` | `object` | 브러시 마스크 배열 |
| `polygon_closed` | `list` | 다각형 꼭짓점 목록 |
| `crop_size_committed` | `int, int, int, int` | 크기 지정 크롭 확정 |
| `color_sampled` | `int, int, int, int` | 스포이드 색상 추출 (r, g, b, a) |
| `fill_applied` | `int, int` | 채우기 클릭 위치 |
| `color_brush_done` | `object` | 색상 브러시 마스크 |
| `shape_committed` | `str, int, int, int, int` | 도형 확정 (type, x, y, w, h) |
| `inpaint_committed` | `int, int, int, int` | AI 인페인팅 영역 확정 |
| `text_committed` | `dict, int, int, int, int` | 새 텍스트 삽입 확정 (settings, ix, iy, iw, ih) |
| `text_edit_committed` | `dict, int, int, int, int` | 기존 텍스트 오버레이 수정 확정 (settings, overlay_idx, ix, iy) |
| `text_overlay_resized` | `int, int` | 텍스트 오버레이 리사이즈 완료 → 재렌더링 요청 (idx, new_disp_w) |
| `overlay_selected` | `int` | 오버레이 선택 변경 (-1 = 없음) |
| `overlay_moved` | `int, int, int` | 오버레이 이동 (idx, x, y) |
| `overlays_changed` | — | 오버레이 목록 변경 |

### 주요 공개 메서드

| 메서드 | 역할 |
|--------|------|
| `set_image(pil_img)` | 기본 이미지 설정 |
| `set_original_image(pil_img)` | 우상단 미니맵용 원본 설정 |
| `set_mode(mode)` | 편집 모드 전환 (커서 업데이트 포함) |
| `add_overlay(pil_img, name, drop_widget_pos)` | 오버레이 추가 |
| `remove_overlay(index)` | 오버레이 삭제 |
| `move_overlay(index, x, y)` | 오버레이 위치 설정 (이미지 좌표) |
| `update_overlay_image(index, new_pil)` | 오버레이 PIL/픽스맵 갱신 (disp_w/h 초기화) |
| `select_overlay(index)` | 오버레이 선택 |
| `get_overlays()` | 오버레이 목록 반환 |
| `fit_overlay_to_canvas(index)` | 오버레이를 캔버스 전체 크기로 확대 |
| `reset_overlay_size(index)` | 오버레이 원본 크기로 초기화 |
| `zoom_in()` / `zoom_out()` / `reset_zoom()` | 줌 조작 |
| `commit_crop_size()` | 크기 지정 크롭 확정 (Enter 단축키용) |
| `cancel_polygon()` | 다각형 모드 취소 |

### 오버레이 딕셔너리 키

```python
{
    'pil':          Image.Image,   # 원본 PIL 이미지
    'pixmap':       QPixmap,       # 원본 크기 QPixmap
    'x':            int,           # 이미지 좌표 X (음수 허용)
    'y':            int,           # 이미지 좌표 Y
    'visible':      bool,
    'name':         str,
    'disp_w':       int,           # 표시 너비 (image px 단위, 리사이즈 반영)
    'disp_h':       int,           # 표시 높이
    'text_settings': dict | None,  # 텍스트 오버레이만 존재 (재편집·리사이즈 재렌더링용)
}
```

`text_settings` 구조 (`dict`):
```python
{
    'font': str, 'size': int, 'bold': bool, 'italic': bool,
    'underline': bool, 'color': tuple[int,int,int,int],
    'align': str,   # "left" | "center" | "right"
    'text': str,    # 원본 텍스트 (재편집 시 초기 내용)
    'box_w': int,   # 래핑 너비 (image px), 마지막으로 사용한 텍스트 박스 너비
}
```

---

## ui/main_window.py — `MainWindow(QMainWindow)`

모든 컴포넌트를 통합하는 메인 윈도우.

### 주요 내부 메서드

| 메서드 | 역할 |
|--------|------|
| `_setup_shortcuts()` | 전역 단축키 등록 (V/E/T/G/B/C/P/A/Ctrl+Z 등) |
| `_set_tool_mode(mode)` | 툴바·퀵패널·캔버스 모드 동기화 |
| `_on_mode_changed(mode)` | 캔버스 모드 전환 + 상태바 메시지 |
| `_on_open()` | 파일 열기 |
| `_on_save()` | 내보내기 다이얼로그 |
| `_load_file(path)` | 이미지 로드 → 캔버스/미니맵/레이어 패널 갱신 |
| `_on_grabcut_auto_apply(x, y, w, h)` | GrabCut 처리 |
| `_on_polygon_cut(pts)` | 다각형 크롭 처리 |
| `_on_crop_drag(x, y, w, h)` | 드래그 크롭 처리 |
| `_on_shape_committed(shape, x, y, w, h)` | 도형 합성 |
| `_on_inpaint_committed(x, y, w, h)` | AI 인페인팅 |
| `_on_text_committed(settings, ix, iy, iw, ih)` | 새 텍스트 오버레이 추가 |
| `_on_text_edit_committed(settings, overlay_idx, ix, iy, iw, ih)` | 기존 텍스트 오버레이 수정 |
| `_on_text_overlay_resized(overlay_idx, new_disp_w)` | 텍스트 오버레이 너비 변경 시 재렌더링 |
| `_render_text_to_pil(settings, box_w)` | 텍스트 서식 → PIL RGBA 이미지 렌더링 |
| `_on_remove_bg_auto()` | AI 배경 제거 (BgRemoveWorker QThread 사용) |
| `_on_delete_overlay(idx)` | 오버레이 삭제 (확인 팝업, idx=-1이면 기본 이미지) |
| `_do_refresh_layer_panel()` | 레이어 패널 갱신 (50ms 디바운스 타이머로 호출) |

### 단축키 목록

| 키 | 모드/액션 |
|----|---------|
| `V` | none (이동/선택) |
| `E` | select (선택/편집) |
| `T` | text (텍스트 삽입) |
| `G` | grabcut |
| `B` | brush |
| `C` | crop |
| `P` | polygon |
| `A` | AI 배경 제거 |
| `Escape` | none (취소) |
| `Enter / Return` | 다각형 완성 / 크기 크롭 확정 |
| `Ctrl+Z` / `Ctrl+Y` | Undo / Redo |
| `Ctrl+= / Ctrl++` | 줌 확대 |
| `Ctrl+-` | 줌 축소 |
| `Ctrl+0` | 줌 맞춤 |

---

## ui/toolbar.py — `Toolbar(QScrollArea)`

좌측 고정 도구 패널 (210px). 모드 버튼, 브러시 크기, 색상, 필터 등을 담습니다.

| 시그널 | 인수 | 설명 |
|--------|------|------|
| `sig_mode_changed` | `str` | 모드 버튼 클릭 |
| `sig_action` | `str` | "undo" / "redo" / "reset" 등 액션 |
| `sig_crop_size` | `int, int` | 크기 지정 크롭 (w, h) |
| `sig_color_changed` | `tuple` | 도구 색상 변경 |
| `sig_help` | — | 도움말 열기 요청 |

### 공개 메서드

| 메서드 | 역할 |
|--------|------|
| `set_mode(mode)` | 모드 버튼 시각 동기화 |

---

## ui/layer_panel.py — `LayerPanel(QWidget)`

우측 오버레이 레이어 목록 패널 (168px).

### 인덱스 규칙
- `0 ~ N-1`: 오버레이 레이어 (높은 인덱스 = 상단 표시)
- `-1`: 기본 이미지 행

| 시그널 | 인수 | 설명 |
|--------|------|------|
| `sig_select` | `int` | 행 선택 |
| `sig_delete` | `int` | 삭제 요청 |
| `sig_toggle_vis` | `int, bool` | 가시성 토글 |
| `sig_merge_down` | `int` | 오버레이 → 기본 이미지 병합 |

| 메서드 | 역할 |
|--------|------|
| `refresh(overlays, active_idx, base_visible, base_selected)` | 전체 목록 재구성 |

---

## ui/inline_text_editor.py — `InlineTextEditor(QWidget)`

캔버스 위에 직접 올라오는 인라인 텍스트 에디터.

| 시그널 | 인수 | 설명 |
|--------|------|------|
| `sig_committed` | `dict` | 삽입 확정 (`get_settings()` 결과) |
| `sig_cancelled` | — | 취소 |

| 메서드 | 역할 |
|--------|------|
| `show_at_rect(widget_rect, prev_settings, initial_text)` | 드래그 영역 위치에 에디터 배치 · 표시. 서식 바는 부모(캔버스) 전체 너비. `initial_text` 지정 시 기존 텍스트로 초기화 |
| `get_settings()` | 현재 서식 + 텍스트 내용 dict 반환 |
| `commit()` | 외부 트리거 확정 (캔버스 바깥 클릭 시 호출) |

---

## ui/quick_tool_panel.py — `QuickToolPanel(QWidget)`

드래그 가능한 캔버스 오버레이 퀵 도구 패널.

| 시그널 | 인수 | 설명 |
|--------|------|------|
| `sig_mode_changed` | `str` | 모드 전환 요청 |
| `sig_action` | `str` | "undo" / "redo" / "remove_bg" / "zoom_in" / "zoom_out" / "zoom_fit" |
| `sig_closed` | — | 패널 닫기 |

| 메서드 | 역할 |
|--------|------|
| `set_mode(mode)` | 모드 버튼 시각 동기화 |

---

## ui/status_bar.py — `StatusBar(QFrame)`

하단 상태바.

| 메서드 | 역할 |
|--------|------|
| `set_message(msg)` | 중앙 메시지 표시 |
| `set_zoom(zoom)` | 줌 % 표시 |
| `set_size(w, h)` | 이미지 크기 표시 |

---

## ui/export_dialog.py — `ExportDialog(QDialog)`

PNG / JPG / PDF 내보내기 형식 선택 다이얼로그.

| 메서드 | 역할 |
|--------|------|
| `get_format()` | 선택된 포맷 문자열 반환 ("PNG" / "JPG" / "PDF") |

---

## ui/new_document_dialog.py — `NewDocumentDialog(QDialog)`

새 문서 크기 지정 다이얼로그.

| 메서드 | 역할 |
|--------|------|
| `get_size()` | `(width, height)` 반환 |

---

## main.py

앱 진입점. **rembg → PyQt6 순서 import 필수** (DLL 충돌 방지).

```python
from core.image_processor import ImageProcessor  # rembg 포함
from PyQt6.QtWidgets import QApplication         # Qt는 나중에
```
