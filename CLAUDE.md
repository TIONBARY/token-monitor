# Claude Token Monitor — 프로젝트 컨텍스트

## 프로젝트 개요

Claude Code 사용자의 실시간 토큰 사용량을 Windows 플로팅 바로 표시하는 프로그램.
`claude.ai/api/oauth/usage` 내부 API를 통해 실제 사용량 %를 가져온다.

## 파일 구조

```
D:\dev\token-monitor\
├── main.py                  # 메인 소스
├── requirements.txt         # pystray, Pillow (현재 미사용, tkinter만 사용)
├── config.json              # 사용자 설정 (lang) — gitignore 대상
├── README.md
├── CLAUDE.md
└── dist/
    └── ClaudeTokenMonitor.exe  # 배포용 단일 실행파일 (gitignore 대상)
```

## 주요 클래스 및 함수

### `STRINGS` / `t(key)`
- `STRINGS`: `{"ko": {...}, "en": {...}}` 형태의 다국어 문자열 딕셔너리
- `t(key)`: 현재 `_lang` 값에 맞는 문자열 반환
- `_lang`: 전역 변수, `"ko"` 또는 `"en"`, `config.json`에 저장

### `fmt_remaining(ts_str)`
- ISO 타임스탬프 → `"N:MM후 리셋"` / `"N:MM to reset"` 형태 변환
- `datetime.now(timezone.utc)`와 비교해 남은 시간 계산
- `_lang` 전역 변수 참조해 언어에 맞게 반환

### `ClaudeUsageAPI`
- `~/.claude/.credentials.json`에서 OAuth accessToken 읽기 (1분마다 파일 재독)
- `GET https://claude.ai/api/oauth/usage` → `five_hour.utilization`, `seven_day.utilization` (%)
- `GET https://claude.ai/api/oauth/profile` → 플랜 정보 (Pro/Max/Free)
- threading.Lock으로 스레드 안전, 1분마다 갱신

### `ClaudeTokenMonitor`
- `~/.claude/projects/**/*.jsonl` 파일 파싱
- 오늘 토큰 수(today) + 현재 파일 세션 토큰 수(session) 집계
- 5초마다 파일 mtime 변경 감지 시 재스캔

### `LangDialog`
- 우클릭 → 언어 설정 시 열리는 다이얼로그
- 라디오버튼으로 한국어/English 선택
- 저장 시 `_lang` 전역 변수 갱신, `config.json` 저장, `FloatingBar._build_ui()` 재호출

### `DetailPopup`
- `FloatingBar` 더블클릭 시 열리는 상세 창
- `_refresh()`에서 `t()` 호출로 언어 변경 즉시 반영
- Canvas 프로그레스 바 (146px 너비)
- 5초마다 갱신, 리셋 카운트다운 실시간 표시
- `reopen()`: 언어 변경 시 팝업 닫기용

### `FloatingBar`
- `overrideredirect(True)` + `attributes("-topmost", True)` 플로팅 창
- `_pinned`: 핀 고정 상태, `_menu_open`: 우클릭 메뉴 열림 상태
- `_keep_on_top()`: 1초마다 실행, `_pinned and not _menu_open`일 때만 `lift()` 호출
  - 메뉴 열림 중 `lift()` 호출 시 메뉴가 가려지는 문제 방지
- `_on_right_click()`: 메뉴 열 때 `_menu_open=True`, 50ms 폴링으로 메뉴 닫힘 감지 후 `False`
- `_build_ui()`: 언어 변경 시 재호출해 바 텍스트 재생성
- Canvas 기반 게이지 바 (테두리 + 채움, 60px 너비)
- 기본 위치: 화면 우하단 (작업표시줄 바로 위)

## 인증 방식

```
~/.claude/.credentials.json
  └── claudeAiOauth.accessToken  →  Bearer 토큰으로 API 호출
```

Claude Code가 로그인 상태를 유지하는 한 자동으로 갱신됨.
accessToken 만료 시 Claude Code 재실행으로 자동 복구.

## API 엔드포인트

| URL | 용도 |
|-----|------|
| `https://claude.ai/api/oauth/usage` | 5h 세션 % / 7일 주간 % / 리셋 시각 |
| `https://claude.ai/api/oauth/profile` | 플랜 정보 (Pro/Max/Free) |

## 토큰 가격 (PRICING)

| 종류 | 가격 |
|------|------|
| 입력 | $3.00 / 1M |
| 출력 | $15.00 / 1M |
| 캐시 생성 | $3.75 / 1M |
| 캐시 읽기 | $0.30 / 1M |

## 빌드

```bash
$pydir = "C:\Users\kse\AppData\Local\Python\pythoncore-3.14-64\Scripts"
& "$pydir\pyinstaller.exe" --onefile --windowed --name "ClaudeTokenMonitor" --clean main.py
```

## 개발 시 주의사항

- `topmost=False`로 바꾸면 `overrideredirect` 창이 작업표시줄에 가려짐 → 핀 해제 시에도 topmost는 True 유지, `lift()` 여부만 조절
- 우클릭 메뉴 열릴 때 `lift()` 호출하면 메뉴가 플로팅 바에 가려짐 → `_menu_open` 플래그로 방지
- 언어 변경 시 `_build_ui()` 재호출로 바 위젯 재생성, 상세 팝업은 `close()` 후 사용자가 다시 열 때 반영
- tkinter는 메인 스레드에서만 실행, API/JSONL 갱신은 daemon 스레드에서 처리
- API는 1분마다, JSONL은 5초마다 갱신 주기가 다름
