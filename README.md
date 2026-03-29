# 🖼 Image Editor Pro

Python 기반 데스크탑 이미지 편집기 — PyQt6 + OpenCV + rembg (AI 배경 제거)

---

## 📁 프로젝트 구조

```
image_editor/
├── main.py                    # 진입점 (rembg → Qt 순서 import 필수)
├── requirements.txt           # 의존 패키지
├── image_editor.spec          # PyInstaller Windows 빌드 설정
├── image_editor_mac.spec      # PyInstaller macOS 빌드 설정
├── build_mac.sh               # macOS .pkg 빌드 스크립트
├── images/
│   └── main.png               # 앱 아이콘 (512×512 RGBA)
├── core/
│   ├── __init__.py
│   └── image_processor.py     # 이미지 처리 핵심 로직 (PIL, OpenCV, rembg)
└── ui/
    ├── __init__.py
    ├── main_window.py          # 메인 윈도우 (시그널 연결 / 레이아웃)
    ├── canvas.py               # 이미지 캔버스 (줌·패닝·모드·오버레이)
    ├── toolbar.py              # 왼쪽 도구 패널 (스크롤 가능)
    ├── layer_panel.py          # 레이어 패널 (오버레이 목록)
    ├── status_bar.py           # 하단 상태바 (줌 %, 이미지 크기)
    └── export_dialog.py        # 내보내기 형식 선택 다이얼로그
```

---

## ⚙️ 설치 방법

### Python 3.10 ~ 3.11 권장

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate

pip install -r requirements.txt
```

> ⚠️ `rembg` 최초 실행 시 AI 모델 (u2net, 약 170 MB)을 자동 다운로드합니다.
> 인터넷 연결이 필요하며, 다운로드 후에는 오프라인에서도 사용 가능합니다.
> 모델 저장 위치: `C:\Users\<사용자>\.u2net\` (Windows), `~/.u2net/` (macOS/Linux)

---

## ▶️ 실행

```bash
python main.py
# 또는 이미지 파일 경로를 인수로 바로 열기
python main.py path/to/image.png
```

---

## 🛠 주요 기능

### 배경 제거

| 방법 | 설명 |
|------|------|
| **자동 (AI)** | rembg U2Net 모델로 원클릭 배경 제거 (단축키: `A`) |
| **GrabCut** | 드래그로 유지할 영역 선택 → 드래그 완료 시 자동 적용 (단축키: `G`) |
| **브러시 마스크** | 마우스로 지울 영역을 직접 칠한 뒤 "브러시 적용" 클릭 (단축키: `B`) |

### 크롭

| 방법 | 설명 |
|------|------|
| **드래그 선택** | 파란 박스로 영역 드래그 후 크롭 (단축키: `C`) |
| **다각형 선택** | 꼭짓점 클릭으로 다각형 생성 → 더블클릭/Enter로 적용 (단축키: `P`) |
| **크기 지정** | W·H 입력 후 노란 박스를 드래그로 위치 조정 → 더블클릭/Enter로 적용 |

### 레이어 / 오버레이

- 기본 이미지 위에 추가 이미지를 레이어로 올려 합성
- 레이어별 표시/숨김 토글, 삭제 (확인 팝업 포함)
- 기본 이미지 표시/숨김 및 삭제 지원
- 오버레이 이미지를 캔버스에서 자유롭게 드래그 이동 (기본 이미지 영역 밖도 가능)
- 코너 핸들로 오버레이 크기 자유 조절
- 모든 레이어를 기본 이미지에 병합

### 필터

흑백 · 블러 · 선명 · 밝기 · 대비 · 세피아

### 뷰 / 탐색

- 마우스 휠 줌, 가운데 버튼 드래그 패닝
- 이동/선택 모드에서 빈 공간 드래그로도 패닝 가능
- Ctrl+0 으로 화면 맞춤
- 우상단 원본 이미지 미리보기 (크기 조절 가능)

### 편집

- Undo / Redo — 최대 30단계
- 원본으로 복원

---

## ⌨️ 단축키

| 단축키 | 기능 |
|--------|------|
| `Ctrl+O` | 이미지 열기 |
| `Ctrl+E` | 내보내기 |
| `Ctrl+Z` | 실행 취소 |
| `Ctrl+Y` | 다시 실행 |
| `Ctrl+R` | 원본으로 복원 |
| `Ctrl+0` | 화면 맞춤 |
| `Ctrl+=` / `Ctrl++` | 확대 |
| `Ctrl+-` | 축소 |
| `V` / `Escape` | 이동·선택 모드 |
| `A` | AI 자동 배경 제거 |
| `G` | GrabCut 모드 |
| `B` | 브러시 마스크 모드 |
| `C` | 드래그 크롭 모드 |
| `P` | 다각형 선택 모드 |
| `F1` | 사용 설명서 |

---

## 📦 배포 파일 빌드

### Windows (.exe)

```bash
pyinstaller image_editor.spec --noconfirm
```

빌드 결과물: `dist/ImageEditorPro/ImageEditorPro.exe`
`dist/ImageEditorPro/` 폴더 전체를 배포하면 됩니다.

### macOS (.app + .pkg)

```bash
bash build_mac.sh
```

빌드 결과물: `dist/ImageEditorPro.pkg`

### ⚠️ 빌드 전 주의사항

1. **rembg 모델 선 다운로드**: 배포 전 `python main.py` 를 한 번 실행해 모델 파일을 받아두세요.
2. **onnxruntime GPU 버전**: GPU 가속이 필요하면 `requirements.txt`에서 `onnxruntime-gpu` 로 교체하세요.
3. **UPX 압축**: 빌드 크기를 줄이려면 [UPX](https://github.com/upx/upx/releases) 를 설치해 PATH에 추가하세요.

---

## 🔧 기능 확장 가이드

### 새 필터 추가

`core/image_processor.py`의 `apply_filter()` 에 분기 추가:

```python
elif filter_name == "my_filter":
    self._push_history()
    # Pillow / OpenCV 처리
    self._current = processed_image
    return self._current
```

`ui/toolbar.py`의 `combo_filter.addItems(...)` 에 이름 추가:

```python
self.combo_filter.addItems([..., "my_filter"])
```

### 새 캔버스 모드 추가

1. `ui/canvas.py` 에 `MODE_XXX = "xxx"` 상수 및 관련 이벤트 처리 추가
2. `ui/toolbar.py` 에 ToolButton 과 시그널 추가
3. `ui/main_window.py` 에 시그널-슬롯 연결 및 핸들러 구현

---

## 📋 의존 패키지

```
PyQt6>=6.6.0
Pillow>=10.0.0
opencv-python>=4.8.0
numpy>=1.24.0
rembg[cpu]>=2.0.50
onnxruntime>=1.16.0
pyinstaller>=6.0.0
```

---

## 🎨 UI 디자인

Catppuccin Mocha 다크 테마 기반:

| 용도 | 색상 |
|------|------|
| 배경 | `#1e1e2e` |
| 패널/카드 | `#181825` / `#313244` |
| 테두리 | `#45475a` |
| 기본 텍스트 | `#cdd6f4` |
| 강조 (파랑) | `#89b4fa` |
| 성공 (초록) | `#a6e3a1` |
| 경고 (빨강) | `#f38ba8` |
| 하이라이트 | `#cba6f7` |
