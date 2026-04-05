# CLAUDE.md — Image Editor Pro 개발 가이드

이 파일은 Claude Code가 이 프로젝트를 이해하고 작업할 때 참조하는 지침입니다.

> **함수·시그널 상세 명세**: [`claude-config/function-spec.md`](claude-config/function-spec.md) 를 참조하세요.
> 각 모듈의 공개 메서드, 시그널 목록, 오버레이 딕셔너리 구조 등이 정리되어 있습니다.

---

## 프로젝트 개요

**Image Editor Pro** — PyQt6 기반 한국어 데스크탑 이미지 편집기.
AI 배경 제거, GrabCut, 브러시 마스크, 다각형 크롭, 레이어 합성 기능을 제공합니다.

- 언어: Python 3.10~3.11
- UI: PyQt6 (Catppuccin Mocha 다크 테마)
- 이미지 처리: Pillow, OpenCV, rembg, NumPy
- 빌드: PyInstaller (Windows .exe / macOS .app+.pkg)
- **UI 텍스트·주석·상태 메시지는 모두 한국어로 작성합니다.**

---

## 핵심 파일 역할

| 파일 | 역할 |
|------|------|
| `main.py` | 앱 진입점. **rembg → Qt 순서 import 필수** (DLL 충돌 방지) |
| `core/image_processor.py` | 모든 PIL/OpenCV/rembg 연산 + Undo/Redo 히스토리 스택 |
| `ui/canvas.py` | `ImageCanvas(QLabel)` — 줌·패닝·오버레이·6가지 편집 모드 |
| `ui/main_window.py` | `MainWindow` — 모든 컴포넌트 시그널 연결, `BgRemoveWorker(QThread)` |
| `ui/toolbar.py` | 왼쪽 도구 패널 (QScrollArea 내부, 210px 고정 너비) |
| `ui/layer_panel.py` | 오버레이 레이어 목록 (168px 고정 너비) |
| `ui/status_bar.py` | 하단 상태바 — 줌 %, 이미지 크기, 메시지 |
| `ui/export_dialog.py` | PNG/JPG/PDF 내보내기 형식 선택 |

---

## 절대 지켜야 할 규칙

### 1. Import 순서 (DLL 충돌)
`main.py` 에서 rembg/onnxruntime 은 반드시 PyQt6 보다 먼저 import 되어야 합니다.
이 순서를 바꾸면 Windows에서 onnxruntime_pybind11_state DLL 초기화 실패가 발생합니다.

```python
# main.py — 이 순서 유지 필수
from core.image_processor import ImageProcessor  # rembg 포함
from PyQt6.QtWidgets import QApplication         # Qt는 나중에
```

### 2. 레이어 패널 갱신 — 디바운스 타이머
`add_overlay()` 는 `overlays_changed` 와 `overlay_selected` 를 연속으로 emit 합니다.
두 시그널 모두 `_refresh_layer_panel` 에 연결되어 있으므로, 50ms 단발(one-shot) QTimer 로 디바운싱합니다.
타이머 없이 직접 호출하면 `deleteLater()` 된 위젯을 다시 접근하는 크래시가 발생합니다.

```python
# main_window.py
self._layer_refresh_timer = QTimer(self)
self._layer_refresh_timer.setSingleShot(True)
self._layer_refresh_timer.setInterval(50)
self._layer_refresh_timer.timeout.connect(self._do_refresh_layer_panel)

def _refresh_layer_panel(self, *_):
    self._layer_refresh_timer.start()   # 이미 실행 중이면 리셋(재시작)
```

### 3. 레이어 패널 시그널 람다 — 인수 없음
`_LayerRow.sig_select` 와 `sig_delete` 는 `pyqtSignal()` (인수 0개)입니다.
람다에 `_` 인수를 넣으면 `missing 1 required positional argument` 크래시가 발생합니다.

```python
# 올바름
row.sig_select.connect(lambda idx=ii: self.sig_select.emit(idx))
# 틀림 — 크래시
row.sig_select.connect(lambda _, idx=ii: self.sig_select.emit(idx))
```

### 4. UI 언어
모든 사용자에게 보이는 텍스트(버튼 레이블, 툴팁, 상태 메시지, 대화상자, 주석 등)는 **한국어**로 작성합니다.

---

## 캔버스 구조 (`ui/canvas.py`)

### 좌표 체계

```
위젯 좌표 → get_image_rect() → 픽스맵(fit-to-window) 좌표 → 이미지 픽셀 좌표
```

- `_scale` : fit-to-window 배율 (픽스맵 생성 시 계산)
- `_zoom`  : 사용자 추가 줌 배율 (1.0 = fit, 0.1~10.0)
- `_pan_offset` : 패닝 오프셋 (QPoint)
- 이미지 좌표 변환: `_widget_to_image()` / `_image_to_widget()`

### 편집 모드

| 상수 | 값 | 동작 |
|------|-----|------|
| `MODE_NONE` | `"none"` | 이동·선택 (오버레이 드래그, 빈 공간 패닝) |
| `MODE_CROP` | `"crop"` | 드래그 크롭 선택 (파란 박스) |
| `MODE_GRABCUT` | `"grabcut"` | GrabCut 선택 (주황 박스, 완료 시 자동 적용) |
| `MODE_BRUSH` | `"brush"` | 브러시 마스크 드로잉 |
| `MODE_POLYGON` | `"polygon"` | 다각형 꼭짓점 클릭 |
| `MODE_CROP_SIZE` | `"crop_size"` | 크기 지정 크롭 미리보기 (노란 박스) |

모드 전환 시 항상 `set_mode(mode)` 를 사용합니다 (커서 업데이트 포함).
GrabCut·다각형 완료 후에는 `_set_tool_mode("none")` 으로 자동 복귀합니다.

### 오버레이 딕셔너리 구조

```python
{
    'pil':     Image.Image,   # 원본 PIL 이미지
    'pixmap':  QPixmap,       # 원본 크기 QPixmap
    'x':       int,           # 이미지 좌표 기준 X (음수 허용 — 기본 이미지 밖)
    'y':       int,           # 이미지 좌표 기준 Y (음수 허용)
    'visible': bool,          # 표시 여부
    'name':    str,           # 레이어 이름
    'disp_w':  int,           # 표시 너비 (원본과 다를 수 있음, 리사이즈)
    'disp_h':  int,           # 표시 높이
}
```

`disp_w` / `disp_h` 가 원본 크기와 다르면 `paintEvent` 에서 스케일된 픽스맵을 생성합니다.
오버레이 위치(`x`, `y`)는 기본 이미지 영역 밖의 음수 좌표도 허용합니다.

### 주요 상태 플래그

| 필드 | 설명 |
|------|------|
| `_active_overlay` | 선택된 오버레이 인덱스 (-1 = 없음) |
| `_base_selected` | 레이어 패널에서 기본 이미지 행을 선택했는지 여부 |
| `_base_visible` | 기본 이미지 표시 여부 |
| `_minimap_hovered` | 원본 미리보기 위에 마우스 올라와 있는지 여부 |
| `_minimap_w` | 원본 미리보기 너비 (60~320, 드래그로 조절) |

---

## ImageProcessor (`core/image_processor.py`)

### 히스토리 관리
모든 편집 메서드는 시작 시 `_push_history()` 를 호출해야 합니다.
현재 이미지를 `_history` 스택에 복사 저장 (최대 30개).
새 편집 시 `_redo_stack` 은 초기화됩니다.

### 주요 메서드

```python
load(path)                             # 이미지 로드 → RGBA 변환
save(path, fmt)                        # PNG/JPG/PDF 저장
remove_background_auto()               # rembg AI 배경 제거
remove_background_grabcut(rect)        # OpenCV GrabCut
apply_brush_mask(mask_array)           # 브러시 마스크 적용
crop_by_rect(x, y, w, h)
crop_by_polygon(points)
apply_filter(name)                     # grayscale/blur/sharpen/brightness/contrast/sepia
merge_overlay(overlay_pil, x, y)       # 알파 블렌딩으로 오버레이 합성
reset_to_original()                    # 원본 복원
```

---

## 레이어 패널 (`ui/layer_panel.py`)

### 인덱스 규칙
- 오버레이 인덱스 `0` ~ `N-1`: 오버레이 레이어
- 인덱스 `-1`: 기본 이미지 행
- `sig_delete(-1)` → `_on_delete_overlay(-1)` → 기본 이미지 전체 삭제 (확인 팝업)
- `sig_toggle_vis(-1, bool)` → `set_base_visible(bool)` → 기본 이미지 표시 토글

### 레이어 행 표시 순서
오버레이는 높은 인덱스(나중에 추가된 것)가 패널 상단에 표시됩니다 (`range(N-1, -1, -1)` 반복).
기본 이미지 행은 항상 맨 아래.

---

## 시그널 흐름 (주요 경로)

```
Toolbar 버튼 클릭
    → sig_mode_changed("grabcut")
    → MainWindow._on_mode_changed()
    → canvas.set_mode("grabcut")

캔버스 GrabCut 드래그 완료
    → canvas.grabcut_selected(x, y, w, h)
    → MainWindow._on_grabcut_auto_apply()
    → ImageProcessor.remove_background_grabcut()
    → canvas.set_image(result)
    → _set_tool_mode("none")          ← 작업 완료 후 자동 모드 초기화

오버레이 추가 (add_overlay)
    → overlays_changed.emit()         ← 레이어 패널 갱신 트리거
    → overlay_selected.emit(idx)      ← 동일
    → (50ms 디바운스 후) _do_refresh_layer_panel()

레이어 패널 삭제 버튼 클릭
    → LayerPanel.sig_delete(idx)
    → MainWindow._on_delete_overlay(idx)
    → QMessageBox 확인 팝업
    → canvas.remove_overlay(idx) 또는 전체 초기화 (idx == -1)
```

---

## 원본 미리보기 (우상단 고정)

- `canvas._orig_pixmap`: `_load_file` 에서 `set_original_image()` 로 설정
- `_paint_minimap()` 에서 `paintEvent` 마지막에 그림
- 크기 조절: 우하단 삼각형 핸들을 드래그 (60~320px)
- 삼각형 핸들은 미니맵 위에 마우스가 있을 때만(`_minimap_hovered`) 표시

---

## 빌드 / 배포

### Windows
```bash
pyinstaller image_editor.spec --noconfirm
# 결과: dist/ImageEditorPro/ImageEditorPro.exe
```

### macOS
```bash
bash build_mac.sh
# 결과: dist/ImageEditorPro.pkg
```

### 빌드 시 중요 사항
- `images/` 폴더는 spec 파일의 `datas` 에 포함되어 있어야 함
- rembg 패키지 전체를 `datas` 에 포함 (모델 파일 포함)
- Hidden imports: `rembg`, `rembg.sessions`, `onnxruntime`, PyQt6 플러그인

---

## 자주 발생하는 문제

| 증상 | 원인 | 해결 |
|------|------|------|
| 실행 즉시 DLL 오류 | rembg/Qt import 순서 뒤집힘 | `main.py` 에서 rembg 먼저 import |
| 레이어 클릭 시 `missing 1 required positional argument` | 람다에 `_` 인수 | `lambda idx=ii:` 로 수정 |
| 레이어 패널 크래시 (rapid signal) | 디바운스 없이 연속 갱신 | 50ms QTimer 사용 유지 |
| 오버레이 추가 후 레이어 패널 미갱신 | `_load_file` 에서 갱신 누락 | `_do_refresh_layer_panel()` 호출 확인 |
| GrabCut 후 계속 GrabCut 모드 | 작업 완료 후 모드 미초기화 | `_set_tool_mode("none")` 호출 확인 |

---

## 코딩 컨벤션

- **변수명**: `_snake_case` (private), `snake_case` (public)
- **시그널명**: `sig_xxx` 접두사
- **UI 텍스트**: 모두 한국어
- **주석**: 한국어 (영어 주석은 기존 것도 한국어로 교체 권장)
- **새 기능**: 기존 패턴(ToolButton/ActionButton/SectionLabel) 재사용
- **모드 추가**: `MODE_XXX` 상수 → `set_mode()` 커서 딕셔너리 → `_paint_overlays()` 렌더링 → Toolbar 버튼 → MainWindow 핸들러 순으로 추가
