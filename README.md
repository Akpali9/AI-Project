# Mien: face-controlled actions

Two versions of the same idea. Both run face analysis locally; video is never uploaded.

| Folder | What it controls | Run it |
|---|---|---|
| `web/` | Itself: notepad, scrolling the page, messages, speech, chime, webhooks | `cd web && python -m http.server 8000`, open http://localhost:8000 |
| `desktop/` | Your whole computer: keys, scroll, clicks, typing, links, screenshots, commands | see below |

## Desktop setup
```
pip install -r requirements.txt
cd desktop
python mien_desktop.py
```
Python 3.9 to 3.12. The face model downloads on first run. Hold a relaxed face for 2 seconds while it calibrates.
Window keys: `c` recalibrate, `p` pause, `q` quit.
macOS: allow camera and Accessibility access for your terminal. Linux: needs an X11 session (Wayland blocks key and mouse control).
Safety: pyautogui's fail-safe is on, so slam the mouse into a screen corner to stop everything.

## rules.json
Each rule: `gesture`, `action`, optional `param`, `threshold` (0 to 1, default 0.6), `hold_ms` (default 300),
`cooldown_ms` (default 800), `repeat` + `repeat_ms` (fire repeatedly while held), `on` (false disables).

Gestures: smile, mouth_open, brows, blink, wink_l, wink_r, pucker, turn_l, turn_r, look_up, look_down
Actions: scroll_up, scroll_down, key (param like "ctrl+tab", "left", "playpause", "volumeup"), type_text,
click, right_click, open_url, screenshot, command (param is a shell command), toggle_pause

Tip: raise `hold_ms` for blink-type gestures so normal blinking never triggers anything.
