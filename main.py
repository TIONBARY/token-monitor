# -*- coding: utf-8 -*-
import json
import time
import threading
import tkinter as tk
from datetime import datetime, timezone
from pathlib import Path

import requests

CLAUDE_PROJECTS_DIR = Path.home() / ".claude" / "projects"
CREDENTIALS_FILE    = Path.home() / ".claude" / ".credentials.json"
CONFIG_FILE         = Path(__file__).parent / "config.json"

PRICING = {
    "input": 3.0, "output": 15.0,
    "cache_creation": 3.75, "cache_read": 0.30,
}

BG       = "#1e1e2e"
BG_HOVER = "#2a2a3e"
FG       = "#cdd6f4"
ACCENT   = "#89b4fa"
GREEN    = "#a6e3a1"
YELLOW   = "#f9e2af"
RED      = "#f38ba8"
SURFACE  = "#313244"
MUTED    = "#6c7086"

# ── 다국어 ─────────────────────────────────────────────────────────

STRINGS = {
    "ko": {
        "session":        "세션",
        "weekly":         "주간",
        "detail_menu":    "상세 보기",
        "lang_menu":      "언어 설정",
        "quit_menu":      "종료",
        "realtime":       "실시간 사용량  (claude.ai 연동)",
        "5h_label":       "5h 세션:",
        "7d_label":       "주간(7d):",
        "token_detail":   "토큰 상세",
        "today":          "📅 오늘",
        "cur_file":       "💬 현재 세션",
        "input":          "입력",
        "output":         "출력",
        "cache_creation": "캐시생성",
        "cache_read":     "캐시읽기",
        "cost":           "비용",
        "updated":        "갱신:",
        "reset_soon":     "곧 리셋",
        "after_reset":    "후 리셋",
        "lang_title":     "언어 선택",
        "save":           "저장",
        "cancel":         "취소",
    },
    "en": {
        "session":        "Session",
        "weekly":         "Weekly",
        "detail_menu":    "Details",
        "lang_menu":      "Language",
        "quit_menu":      "Quit",
        "realtime":       "Live Usage  (claude.ai)",
        "5h_label":       "5h Session:",
        "7d_label":       "Weekly(7d):",
        "token_detail":   "Token Details",
        "today":          "📅 Today",
        "cur_file":       "💬 Cur Session",
        "input":          "Input",
        "output":         "Output",
        "cache_creation": "Cache Write",
        "cache_read":     "Cache Read",
        "cost":           "Cost",
        "updated":        "Updated:",
        "reset_soon":     "Resets soon",
        "after_reset":    " to reset",
        "lang_title":     "Language",
        "save":           "Save",
        "cancel":         "Cancel",
    },
}

_lang = "ko"

def t(key: str) -> str:
    return STRINGS.get(_lang, STRINGS["ko"]).get(key, key)


# ── 설정 ───────────────────────────────────────────────────────────

def load_config() -> dict:
    defaults = {"lang": "ko"}
    if CONFIG_FILE.exists():
        try:
            defaults.update(json.loads(CONFIG_FILE.read_text(encoding="utf-8")))
        except Exception:
            pass
    return defaults

def save_config(cfg: dict):
    CONFIG_FILE.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")


# ── 유틸 ───────────────────────────────────────────────────────────

def fmt_remaining(ts_str: str) -> str:
    if not ts_str:
        return ""
    try:
        dt = datetime.fromisoformat(ts_str)
        remaining = dt - datetime.now(timezone.utc)
        total_secs = remaining.total_seconds()
        if total_secs <= 0:
            return t("reset_soon")
        total_mins = int(total_secs // 60)
        hours = total_mins // 60
        mins  = total_mins % 60
        if _lang == "ko":
            return f"{hours}:{mins:02d}{t('after_reset')}"
        else:
            return f"{hours}:{mins:02d}{t('after_reset')}"
    except Exception:
        return ""


# ── Claude.ai Usage API ─────────────────────────────────────────────

class ClaudeUsageAPI:
    USAGE_URL   = "https://claude.ai/api/oauth/usage"
    PROFILE_URL = "https://claude.ai/api/oauth/profile"

    def __init__(self):
        self.five_hour_pct: float = 0.0
        self.seven_day_pct: float = 0.0
        self.resets_at_5h:  str   = ""
        self.resets_at_7d:  str   = ""
        self.plan:          str   = "Pro"
        self.error:         str   = ""
        self.lock = threading.Lock()
        self._running = False

    def start(self):
        self._running = True
        threading.Thread(target=self._loop, daemon=True).start()

    def stop(self):
        self._running = False

    def get(self):
        with self.lock:
            return {
                "five_hour_pct": self.five_hour_pct,
                "seven_day_pct": self.seven_day_pct,
                "resets_at_5h":  self.resets_at_5h,
                "resets_at_7d":  self.resets_at_7d,
                "plan":          self.plan,
                "error":         self.error,
            }

    def _load_token(self) -> str | None:
        try:
            data = json.loads(CREDENTIALS_FILE.read_text(encoding="utf-8"))
            return data["claudeAiOauth"]["accessToken"]
        except Exception:
            return None

    def _headers(self, token: str) -> dict:
        return {
            "Authorization": f"Bearer {token}",
            "User-Agent": "claude-cli/1.0",
            "Accept": "application/json",
            "anthropic-client-platform": "claude_cli",
        }

    def _fetch(self):
        token = self._load_token()
        if not token:
            with self.lock:
                self.error = "credentials 파일을 읽을 수 없음"
            return
        hdrs = self._headers(token)
        try:
            r = requests.get(self.USAGE_URL, headers=hdrs, timeout=10)
            if r.status_code == 200:
                data = r.json()
                fh = data.get("five_hour") or {}
                sd = data.get("seven_day")  or {}
                with self.lock:
                    self.five_hour_pct = float(fh.get("utilization") or 0)
                    self.seven_day_pct = float(sd.get("utilization") or 0)
                    self.resets_at_5h  = fh.get("resets_at", "")
                    self.resets_at_7d  = sd.get("resets_at", "")
                    self.error = ""
            else:
                with self.lock:
                    self.error = f"API {r.status_code}"
        except requests.RequestException as e:
            with self.lock:
                self.error = f"Network error: {e}"
        try:
            r = requests.get(self.PROFILE_URL, headers=hdrs, timeout=10)
            if r.status_code == 200:
                acc = r.json().get("account", {})
                plan = "Max" if acc.get("has_claude_max") else "Pro" if acc.get("has_claude_pro") else "Free"
                with self.lock:
                    self.plan = plan
        except Exception:
            pass

    def _loop(self):
        self._fetch()
        while self._running:
            time.sleep(60)
            self._fetch()


# ── 토큰 통계 ──────────────────────────────────────────────────────

class TokenStats:
    def __init__(self):
        self.input_tokens = 0
        self.output_tokens = 0
        self.cache_creation_tokens = 0
        self.cache_read_tokens = 0

    def add_usage(self, usage: dict):
        self.input_tokens          += usage.get("input_tokens", 0)
        self.output_tokens         += usage.get("output_tokens", 0)
        self.cache_creation_tokens += usage.get("cache_creation_input_tokens", 0)
        self.cache_read_tokens     += usage.get("cache_read_input_tokens", 0)

    def calc_cost(self) -> float:
        return (
            self.input_tokens          * PRICING["input"]          / 1_000_000
            + self.output_tokens       * PRICING["output"]         / 1_000_000
            + self.cache_creation_tokens * PRICING["cache_creation"] / 1_000_000
            + self.cache_read_tokens   * PRICING["cache_read"]     / 1_000_000
        )

    @property
    def total_tokens(self):
        return self.input_tokens + self.output_tokens


class ClaudeTokenMonitor:
    def __init__(self):
        self.today   = TokenStats()
        self.session = TokenStats()
        self.lock = threading.Lock()
        self._running = False
        self._cur_file: Path | None = None
        self._last_mtime: float = 0

    def start(self):
        self._running = True
        threading.Thread(target=self._loop, daemon=True).start()

    def stop(self):
        self._running = False

    def get_stats(self):
        with self.lock:
            return self.today, self.session

    def _all_jsonl(self) -> list[Path]:
        files = []
        if CLAUDE_PROJECTS_DIR.exists():
            for proj in CLAUDE_PROJECTS_DIR.iterdir():
                if proj.is_dir():
                    files.extend(proj.glob("*.jsonl"))
        return files

    def _latest(self) -> Path | None:
        files = self._all_jsonl()
        return max(files, key=lambda f: f.stat().st_mtime) if files else None

    def _scan(self):
        from datetime import date
        today_prefix = date.today().isoformat()
        td = TokenStats()
        for f in self._all_jsonl():
            try:
                with open(f, "r", encoding="utf-8") as fh:
                    for raw in fh:
                        raw = raw.strip()
                        if not raw:
                            continue
                        try:
                            row = json.loads(raw)
                            if not row.get("timestamp", "").startswith(today_prefix):
                                continue
                            msg = row.get("message") or {}
                            usage = msg.get("usage") if isinstance(msg, dict) else None
                            if usage and isinstance(usage, dict):
                                td.add_usage(usage)
                        except (json.JSONDecodeError, AttributeError):
                            pass
            except (PermissionError, FileNotFoundError):
                pass

        latest = self._latest()
        cur = TokenStats()
        if latest:
            try:
                with open(latest, "r", encoding="utf-8") as fh:
                    for raw in fh:
                        raw = raw.strip()
                        if not raw:
                            continue
                        try:
                            row = json.loads(raw)
                            msg = row.get("message") or {}
                            usage = msg.get("usage") if isinstance(msg, dict) else None
                            if usage and isinstance(usage, dict):
                                cur.add_usage(usage)
                        except (json.JSONDecodeError, AttributeError):
                            pass
            except (PermissionError, FileNotFoundError):
                pass

        with self.lock:
            self.today   = td
            self.session = cur
            self._cur_file   = latest
            self._last_mtime = latest.stat().st_mtime if latest else 0

    def _loop(self):
        self._scan()
        while self._running:
            time.sleep(5)
            latest = self._latest()
            mtime  = latest.stat().st_mtime if latest else 0
            if latest != self._cur_file or mtime != self._last_mtime:
                self._scan()


# ── 상세 팝업 ──────────────────────────────────────────────────────

class DetailPopup:
    def __init__(self, parent, api: ClaudeUsageAPI, monitor: ClaudeTokenMonitor):
        self._parent  = parent
        self._api     = api
        self._monitor = monitor
        self._win: tk.Toplevel | None = None

    def toggle(self, near_x=0, near_y=0):
        if self._win and self._win.winfo_exists():
            self._win.destroy()
            self._win = None
            return
        self._open(near_x, near_y)

    def close(self):
        if self._win and self._win.winfo_exists():
            self._win.destroy()
            self._win = None

    def reopen(self, near_x=0, near_y=0):
        self.close()
        self._open(near_x, near_y)

    def _open(self, near_x, near_y):
        win = tk.Toplevel(self._parent)
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        win.configure(bg=BG)
        self._win = win

        border = tk.Frame(win, bg=ACCENT, padx=1, pady=1)
        border.pack()
        outer = tk.Frame(border, bg=BG, padx=16, pady=12)
        outer.pack()

        # 헤더
        hdr = tk.Frame(outer, bg=BG)
        hdr.pack(fill="x")
        self._title_lbl = tk.Label(hdr, text="Claude Token Monitor",
                                    bg=BG, fg=ACCENT, font=("Segoe UI", 12, "bold"))
        self._title_lbl.pack(side="left")
        tk.Label(hdr, text="✕", bg=BG, fg=MUTED,
                 font=("Segoe UI", 12), cursor="hand2").pack(side="right")
        hdr.winfo_children()[-1].bind("<Button-1>", lambda e: self.close())

        tk.Frame(outer, bg=SURFACE, height=1).pack(fill="x", pady=(8, 0))

        # 사용량 % 섹션
        pct_outer = tk.Frame(outer, bg=BG)
        pct_outer.pack(fill="x", pady=(10, 0))
        self._realtime_lbl = tk.Label(pct_outer, text=t("realtime"),
                                       bg=BG, fg=ACCENT, font=("Segoe UI", 10, "bold"))
        self._realtime_lbl.pack(anchor="w", pady=(0, 6))

        row1 = tk.Frame(pct_outer, bg=BG)
        row1.pack(fill="x", pady=2)
        self._lbl_5h_title = tk.Label(row1, text=t("5h_label"), bg=BG, fg=FG,
                                       font=("Segoe UI", 10), width=10, anchor="w")
        self._lbl_5h_title.pack(side="left")
        self._bar5h = tk.Canvas(row1, width=146, height=14,
                                 bg=SURFACE, highlightthickness=0)
        self._bar5h.pack(side="left", padx=(6, 2))
        self._lbl5h = tk.Label(row1, text="0.0%", bg=BG, fg=GREEN,
                                font=("Consolas", 10, "bold"))
        self._lbl5h.pack(side="left")
        self._reset5h = tk.Label(row1, text="", bg=BG, fg=MUTED, font=("Segoe UI", 8))
        self._reset5h.pack(side="right", padx=(12, 0))

        row2 = tk.Frame(pct_outer, bg=BG)
        row2.pack(fill="x", pady=2)
        self._lbl_7d_title = tk.Label(row2, text=t("7d_label"), bg=BG, fg=FG,
                                       font=("Segoe UI", 10), width=10, anchor="w")
        self._lbl_7d_title.pack(side="left")
        self._bar7d = tk.Canvas(row2, width=146, height=14,
                                 bg=SURFACE, highlightthickness=0)
        self._bar7d.pack(side="left", padx=(6, 2))
        self._lbl7d = tk.Label(row2, text="0.0%", bg=BG, fg=ACCENT,
                                font=("Consolas", 10, "bold"))
        self._lbl7d.pack(side="left")
        self._reset7d = tk.Label(row2, text="", bg=BG, fg=MUTED, font=("Segoe UI", 8))
        self._reset7d.pack(side="right", padx=(12, 0))

        tk.Frame(outer, bg=SURFACE, height=1).pack(fill="x", pady=(10, 0))

        self._token_title_lbl = tk.Label(outer, text=t("token_detail"), bg=BG, fg=FG,
                                          font=("Segoe UI", 10, "bold"))
        self._token_title_lbl.pack(anchor="w", pady=(8, 4))

        cols = tk.Frame(outer, bg=BG)
        cols.pack(fill="x")
        self._today_lbl   = self._token_section(cols, t("today"),    GREEN,  "left")
        tk.Frame(cols, bg=SURFACE, width=1).pack(side="left", fill="y", padx=12)
        self._session_lbl = self._token_section(cols, t("cur_file"), YELLOW, "left")

        tk.Frame(outer, bg=SURFACE, height=1).pack(fill="x", pady=(8, 4))
        self._time_lbl = tk.Label(outer, text="", bg=BG, fg=MUTED, font=("Segoe UI", 8))
        self._time_lbl.pack(anchor="e")

        self._refresh()

        win.update_idletasks()
        w, h = win.winfo_width(), win.winfo_height()
        sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
        x = min(near_x, sw - w - 10)
        y = near_y - h - 5
        if y < 0:
            y = near_y + 30
        win.geometry(f"+{x}+{y}")

    def _token_section(self, parent, title, color, side) -> dict:
        frame = tk.Frame(parent, bg=BG)
        frame.pack(side=side, anchor="n")
        tk.Label(frame, text=title, bg=BG, fg=color,
                 font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(0, 4))
        labels = {}
        for key in ["input", "output", "cache_creation", "cache_read", "cost"]:
            row = tk.Frame(frame, bg=BG)
            row.pack(fill="x")
            tk.Label(row, text=f"{t(key)}:", bg=BG, fg=FG,
                     font=("Segoe UI", 9), width=9, anchor="w").pack(side="left")
            val = tk.Label(row, text="0", bg=BG, fg=color, font=("Consolas", 9, "bold"))
            val.pack(side="right")
            labels[key] = val
        return labels

    def _draw_bar(self, canvas, pct: float, color: str):
        canvas.delete("all")
        W = 146
        filled = max(1, int(W * pct / 100)) if pct > 0 else 0
        canvas.create_rectangle(0, 0, filled, 14, fill=color, outline="")

    def _fill_tokens(self, labels, stats: TokenStats):
        labels["input"].config(text=f"{stats.input_tokens:,}")
        labels["output"].config(text=f"{stats.output_tokens:,}")
        labels["cache_creation"].config(text=f"{stats.cache_creation_tokens:,}")
        labels["cache_read"].config(text=f"{stats.cache_read_tokens:,}")
        labels["cost"].config(text=f"${stats.calc_cost():.4f}")

    def _refresh(self):
        if not self._win or not self._win.winfo_exists():
            return

        usage = self._api.get()
        today, session = self._monitor.get_stats()

        fh_pct = usage["five_hour_pct"]
        sd_pct = usage["seven_day_pct"]
        plan   = usage["plan"]
        err    = usage["error"]

        self._title_lbl.config(text=f"Claude Token Monitor  —  {plan}")
        self._realtime_lbl.config(text=t("realtime"))
        self._lbl_5h_title.config(text=t("5h_label"))
        self._lbl_7d_title.config(text=t("7d_label"))
        self._token_title_lbl.config(text=t("token_detail"))

        def bar_color(pct):
            return RED if pct >= 90 else YELLOW if pct >= 70 else GREEN

        self._draw_bar(self._bar5h, fh_pct, bar_color(fh_pct))
        self._lbl5h.config(text=f"{fh_pct:.1f}%", fg=bar_color(fh_pct))
        self._reset5h.config(text=fmt_remaining(usage["resets_at_5h"]))

        self._draw_bar(self._bar7d, sd_pct, bar_color(sd_pct))
        self._lbl7d.config(text=f"{sd_pct:.1f}%", fg=bar_color(sd_pct))
        self._reset7d.config(text=fmt_remaining(usage["resets_at_7d"]))

        self._fill_tokens(self._today_lbl,   today)
        self._fill_tokens(self._session_lbl, session)

        status = f"{t('updated')} {datetime.now().strftime('%H:%M:%S')}"
        if err:
            status += f"  ⚠ {err}"
        self._time_lbl.config(text=status)

        self._win.after(5000, self._refresh)


# ── 언어 선택 다이얼로그 ────────────────────────────────────────────

class LangDialog:
    def __init__(self, parent, on_change):
        self._on_change = on_change
        win = tk.Toplevel(parent)
        win.title(t("lang_title"))
        win.attributes("-topmost", True)
        win.resizable(False, False)
        win.configure(bg=BG)

        outer = tk.Frame(win, bg=BG, padx=24, pady=16)
        outer.pack()

        tk.Label(outer, text=t("lang_title"), bg=BG, fg=ACCENT,
                 font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(0, 12))

        self._var = tk.StringVar(value=_lang)
        for code, label in [("ko", "한국어"), ("en", "English")]:
            tk.Radiobutton(outer, text=label, variable=self._var, value=code,
                           bg=BG, fg=FG, selectcolor=SURFACE,
                           activebackground=BG, activeforeground=FG,
                           font=("Segoe UI", 11)).pack(anchor="w", pady=2)

        btn_frame = tk.Frame(outer, bg=BG)
        btn_frame.pack(fill="x", pady=(14, 0))
        tk.Button(btn_frame, text=t("cancel"), command=win.destroy,
                  bg=SURFACE, fg=FG, relief="flat", padx=14,
                  font=("Segoe UI", 10), cursor="hand2").pack(side="right", padx=(6, 0))
        tk.Button(btn_frame, text=t("save"),
                  command=lambda: self._save(win),
                  bg=ACCENT, fg=BG, relief="flat", padx=14,
                  font=("Segoe UI", 10, "bold"), cursor="hand2").pack(side="right")

        win.update_idletasks()
        sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
        w, h = win.winfo_width(), win.winfo_height()
        win.geometry(f"+{(sw - w) // 2}+{(sh - h) // 2}")

    def _save(self, win):
        global _lang
        new_lang = self._var.get()
        if new_lang != _lang:
            _lang = new_lang
            cfg = load_config()
            cfg["lang"] = _lang
            save_config(cfg)
            self._on_change()
        win.destroy()


# ── 플로팅 바 ───────────────────────────────────────────────────────

class FloatingBar:
    def __init__(self, api: ClaudeUsageAPI, monitor: ClaudeTokenMonitor):
        self._api     = api
        self._monitor = monitor

        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 0.92)
        self.root.configure(bg=BG)

        self._drag_x = self._drag_y = 0
        self._pinned = True
        self._menu_open = False
        self._bar_frame: tk.Frame | None = None

        self._build_ui()
        self._place_default()
        self._detail = DetailPopup(self.root, api, monitor)
        self._keep_on_top()
        self._refresh()

    def _build_ui(self):
        if self._bar_frame:
            self._bar_frame.destroy()

        bar = tk.Frame(self.root, bg=BG, padx=8, pady=5)
        bar.pack()
        self._bar_frame = bar

        tk.Label(bar, text="🤖", bg=BG, fg=ACCENT,
                 font=("Segoe UI", 9)).pack(side="left")

        # 세션
        self._lbl_s_pct = tk.Label(bar, text=f"{t('session')} --%", bg=BG, fg=GREEN,
                                    font=("Consolas", 9, "bold"), padx=4)
        self._lbl_s_pct.pack(side="left")
        self._float_bar_s = tk.Canvas(bar, width=60, height=10,
                                       bg=BG, highlightthickness=0)
        self._float_bar_s.pack(side="left", padx=(0, 4))

        tk.Label(bar, text=" | ", bg=BG, fg=SURFACE,
                 font=("Segoe UI", 9)).pack(side="left")

        # 주간
        self._lbl_w_pct = tk.Label(bar, text=f"{t('weekly')} --%", bg=BG, fg=ACCENT,
                                    font=("Consolas", 9, "bold"), padx=4)
        self._lbl_w_pct.pack(side="left")
        self._float_bar_w = tk.Canvas(bar, width=60, height=10,
                                       bg=BG, highlightthickness=0)
        self._float_bar_w.pack(side="left", padx=(0, 4))

        tk.Label(bar, text=" | ", bg=BG, fg=SURFACE,
                 font=("Segoe UI", 9)).pack(side="left")

        # 비용
        self._lbl_cost = tk.Label(bar, text="$0.0000", bg=BG, fg=MUTED,
                                   font=("Consolas", 9), padx=4)
        self._lbl_cost.pack(side="left")

        # 핀 버튼
        self._pin_btn = tk.Label(bar, text="📌", bg=BG, fg=ACCENT,
                                  font=("Segoe UI", 8), padx=4, cursor="hand2")
        self._pin_btn.pack(side="left")
        self._pin_btn.bind("<Button-1>", self._toggle_pin)

        draggable = [bar] + [w for w in bar.winfo_children() if w is not self._pin_btn]
        for w in draggable:
            w.bind("<ButtonPress-1>",   self._drag_start)
            w.bind("<B1-Motion>",       self._drag_move)
            w.bind("<Double-Button-1>", self._on_double_click)
            w.bind("<Button-3>",        self._on_right_click)

        bar.bind("<Enter>", lambda e: [self.root.configure(bg=BG_HOVER), bar.configure(bg=BG_HOVER)])
        bar.bind("<Leave>", lambda e: [self.root.configure(bg=BG),       bar.configure(bg=BG)])

    def _place_default(self):
        self.root.update_idletasks()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        w  = self.root.winfo_width()
        h  = self.root.winfo_height()
        self.root.geometry(f"+{sw - w - 20}+{sh - h - 48}")

    def _toggle_pin(self, _=None):
        self._pinned = not self._pinned
        self._pin_btn.config(text="📌" if self._pinned else "📍",
                             fg=ACCENT if self._pinned else MUTED)

    def _keep_on_top(self):
        if self._pinned and not self._menu_open:
            self.root.attributes("-topmost", True)
            self.root.lift()
        self.root.after(1000, self._keep_on_top)

    def _drag_start(self, e):
        self._drag_x, self._drag_y = e.x, e.y

    def _drag_move(self, e):
        x = self.root.winfo_x() + e.x - self._drag_x
        y = self.root.winfo_y() + e.y - self._drag_y
        self.root.geometry(f"+{x}+{y}")

    def _on_double_click(self, _=None):
        self._detail.toggle(self.root.winfo_x(), self.root.winfo_y())

    def _on_right_click(self, e):
        self._menu_open = True
        menu = tk.Menu(self.root, tearoff=0, bg=SURFACE, fg=FG,
                       activebackground=ACCENT, activeforeground=BG,
                       font=("Segoe UI", 10))
        menu.add_command(label=t("detail_menu"), command=self._on_double_click)
        menu.add_command(label=t("lang_menu"),   command=self._open_lang)
        menu.add_separator()
        menu.add_command(label=t("quit_menu"),   command=self.root.quit)
        menu.tk_popup(e.x_root, e.y_root)

        # 메뉴가 닫히면 플래그 해제
        def _wait_close():
            try:
                if menu.winfo_ismapped():
                    self.root.after(50, _wait_close)
                else:
                    self._menu_open = False
            except Exception:
                self._menu_open = False
        self.root.after(50, _wait_close)

    def _open_lang(self):
        def on_change():
            # 언어 변경 시 바 재빌드 + 팝업 닫기
            self._build_ui()
            self._detail.close()
        LangDialog(self.root, on_change)

    @staticmethod
    def _draw_float_bar(canvas, pct: float, color: str, W=60, H=10):
        canvas.delete("all")
        canvas.create_rectangle(0, 0, W - 1, H - 1, outline=color, fill="")
        filled = int((W - 2) * pct / 100)
        if filled > 0:
            canvas.create_rectangle(1, 1, filled + 1, H - 2, fill=color, outline="")

    def _refresh(self):
        usage = self._api.get()
        today, _ = self._monitor.get_stats()

        fh_pct = usage["five_hour_pct"]
        sd_pct = usage["seven_day_pct"]

        def color(pct):
            return RED if pct >= 90 else YELLOW if pct >= 70 else GREEN

        s_col = color(fh_pct)
        w_col = color(sd_pct) if sd_pct else ACCENT

        self._lbl_s_pct.config(text=f"{t('session')} {fh_pct:4.1f}%", fg=s_col)
        self._draw_float_bar(self._float_bar_s, fh_pct, s_col)
        self._lbl_w_pct.config(text=f"{t('weekly')} {sd_pct:4.1f}%", fg=w_col)
        self._draw_float_bar(self._float_bar_w, sd_pct, w_col)
        self._lbl_cost.config(text=f"${today.calc_cost():.4f}")

        self.root.after(5000, self._refresh)

    def run(self):
        self.root.mainloop()


# ── 진입점 ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    cfg = load_config()
    _lang = cfg.get("lang", "ko")

    api     = ClaudeUsageAPI()
    monitor = ClaudeTokenMonitor()

    api.start()
    monitor.start()

    bar = FloatingBar(api, monitor)
    bar.run()
