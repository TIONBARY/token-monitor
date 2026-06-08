# Claude Token Monitor

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

🇺🇸 English | 🇰🇷 [한국어](README.ko.md)

A real-time floating bar that shows your Claude Code token usage at a glance.

## Screenshot

```
🤖 Session 36.0% [██████░░░░]  |  Weekly  4.0% [█░░░░░░░░░]  |  $0.0098  📌
```

## Features

- **Live usage %** — synced directly with your claude.ai account, reflecting your real usage
- **5-hour session usage** — current session usage and time remaining until reset
- **Weekly usage** — cumulative usage for the week and time remaining until reset
- **Color-coded gauge bars** — yellow at 70%+, red at 90%+
- **Today's token breakdown** — input/output/cache token counts and estimated cost
- **Always-on-top** — toggle with the pin button (📌)
- **Drag to move** — freely reposition anywhere on screen
- **Multilingual** — switch between Korean and English

## Requirements

- Windows 10/11
- **Claude Code must be installed and logged in**
  - Authenticates using `~/.claude/.credentials.json`, which is created automatically when you log in to Claude Code

## Installation & Usage

### Pre-built release (exe) — recommended

1. Download `ClaudeTokenMonitor.exe` from the [Releases](https://github.com/TIONBARY/token-monitor/releases/latest) page
2. Run it

No Python or extra installation needed — just run the exe.
If Windows Defender shows a warning, click **More info → Run anyway**.

### Run from source

```bash
pip install -r requirements.txt
python main.py
```

## How to use

| Action | Effect |
|--------|--------|
| Double-click | Open/close the detail popup |
| Right-click | Menu (Details / Language / Quit) |
| Drag | Move the bar |
| Click 📌 | Toggle always-on-top |

### Language setting

Right-click → Language lets you switch between Korean and English. The setting is saved to `config.json` and persists across restarts.

## How it works

It reads the OAuth token (`~/.claude/.credentials.json`) created when you log in to Claude Code, and calls the `claude.ai/api/oauth/usage` API. Since it shares Claude Code's login session, no separate sign-in is required.

- API usage: refreshes every 1 minute
- Token details (JSONL): refreshes every 5 seconds
- Reset countdown: refreshes every 5 seconds

## Platform support

| OS | Status |
|----|--------|
| Windows 10/11 | ✅ Supported |
| macOS | ❓ Untested — contributions welcome! |
| Linux | ❓ Untested — contributions welcome! |

If you're interested in porting to macOS / Linux, please start a discussion on [Issues](https://github.com/TIONBARY/token-monitor/issues).

## ⚠️ Disclaimer

This program uses an **unofficial, internal Anthropic API** (`claude.ai/api/oauth/usage`).

- It is not a publicly documented API, so **Anthropic may change or block it at any time**
- This may be a form of API access not explicitly covered by Anthropic's Terms of Service
- The author is not responsible for any issues arising from its use

## Build

```bash
pip install pyinstaller
pyinstaller --onefile --windowed --name "ClaudeTokenMonitor" main.py
# Produces dist/ClaudeTokenMonitor.exe
```
