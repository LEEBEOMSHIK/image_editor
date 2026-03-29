# 🖼 Image Editor Pro

Python 기반 데스크탑 이미지 편집기 — PyQt6 + OpenCV + rembg

---

## 📁 프로젝트 구조

```
image_editor/
├── main.py                  # 진입점
├── requirements.txt         # 의존 패키지
├── image_editor.spec        # PyInstaller 빌드 설정
├── core/
│   ├── __init__.py
│   └── image_processor.py   # 이미지 처리 핵심 로직
└── ui/
    ├── __init__.py
    ├── main_window.py        # 메인 윈도우
    ├── canvas.py             # 이미지 캔버스 (마우스 인터랙션)
    ├── toolbar.py            # 왼쪽 도구 패널
    ├── status_bar.py         # 하단 상태바
    └── export_dialog.py      # 내보내기 다이얼로그
```

---

## ⚙️ 설치 방법

### 1. Python 환경 준비 (Python 3.10 ~ 3.11 권장)

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

### 2. 패키지 설치

```bash
pip install -r requirements.txt
```

> ⚠️ `rembg` 최초 실행 시 AI 모델(u2net, ~170MB)을 자동 다운로드합니다.  
> 인터넷 연결이 필요하며, 다운로드 후에는 오프라인에서도 사용 가능합니다.

---

## ▶️ 실행

```bash
python main.py
```

---

## 🛠 주요 기능

| 기능 | 설명 |
|------|------|
| **자동 배경 제거** | rembg AI 모델로 원클릭 배경 제거 |
| **GrabCut 배경 제거** | 드래그로 영역 선택 후 OpenCV GrabCut 알고리즘 적용 |
| **브러시 마스킹** | 마우스로 직접 칠해서 배경 제거 |
| **드래그 크롭** | 마우스 드래그로 영역 선택 후 크롭 |
| **크기 지정 크롭** | 너비/높이 숫자 입력 후 중앙 기준 크롭 |
| **필터** | 흑백, 블러, 선명, 밝기, 대비, 세피아 |
| **Undo/Redo** | 최대 30단계 실행 취소/재실행 |
| **내보내기** | PNG / JPG / PDF 형식 선택 저장 |

---

## 📦 .exe 파일 빌드 방법 (Windows)

### 방법 1: spec 파일 사용 (권장)

```bash
pyinstaller image_editor.spec
```

### 방법 2: 명령어 직접 실행

```bash
pyinstaller \
  --noconfirm \
  --windowed \
  --name "ImageEditorPro" \
  --add-data "venv/Lib/site-packages/rembg;rembg" \
  --hidden-import rembg \
  --hidden-import rembg.sessions \
  --hidden-import onnxruntime \
  main.py
```

> 📌 Windows 경로 구분자는 `;` (macOS/Linux는 `:`)

빌드 완료 후 `dist/ImageEditorPro/` 폴더 전체를 배포하면 됩니다.  
`dist/ImageEditorPro/ImageEditorPro.exe`를 실행하세요.

### ⚠️ 빌드 시 주의사항

1. **rembg 모델 포함**: 빌드 전에 `python main.py`를 한 번 실행해 모델을 먼저 다운로드하세요.  
   모델은 보통 `C:\Users\<사용자>\.u2net\` 에 저장됩니다.  
   이 파일도 `--add-data`로 포함하거나 배포 시 함께 제공하세요.

2. **onnxruntime**: GPU 버전이 필요하면 `onnxruntime-gpu`로 교체하세요.

3. **UPX 압축**: 빌드 크기를 줄이려면 [UPX](https://github.com/upx/upx/releases)를 설치 후 PATH에 추가하세요.

---

## 🔧 새 기능 추가 방법 (확장 가이드)

### 새 필터 추가
`core/image_processor.py`의 `apply_filter()` 메서드에 분기 추가:

```python
elif filter_name == "my_filter":
    # Pillow / OpenCV 처리
    self._current = ...
```

그 다음 `ui/toolbar.py`의 `combo_filter`에 항목 추가:
```python
self.combo_filter.addItems([..., "my_filter"])
```

### 새 도구 추가
1. `ui/toolbar.py`에 버튼과 시그널 추가
2. `ui/main_window.py`에 슬롯(핸들러) 구현
3. 필요 시 `ui/canvas.py`에 새 모드 추가

---

## 📋 requirements.txt

```
PyQt6>=6.6.0
Pillow>=10.0.0
opencv-python>=4.8.0
numpy>=1.24.0
rembg>=2.0.50
onnxruntime>=1.16.0
pyinstaller>=6.0.0
```
