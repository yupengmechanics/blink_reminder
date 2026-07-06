# Blink Reminder

A lightweight, always-on-top eye-care reminder for Windows. It periodically shows a small, semi-transparent, click-through banner reminding you to blink, follow the 20-20-20 rule, and take hourly stretch breaks — without ever stealing focus from your work or game.

Built with the Python standard library only (tkinter + ctypes). No third-party dependencies.

## Why

Screen use suppresses blink rate and blink completeness, a major contributor to digital eye strain and dry eye. This tool nudges you to blink fully and to periodically relax eye focus at distance (the 20-20-20 rule: every 20 minutes, look at something 20 feet / 6 meters away for 20 seconds).

Note: this is a wellness aid, not a medical treatment. Persistent dry-eye symptoms warrant an eye exam.

## Features

- **Blink reminders** on a configurable interval, with rotating messages to reduce habituation
- **20-20-20 reminders** every 20 minutes; the banner stays up 20 seconds and doubles as the timer
- **Optional hourly stretch/posture reminder**
- **Click-through overlay**: uses Windows layered-window styles (`WS_EX_TRANSPARENT`), so it never captures mouse or keyboard input — safe while typing or gaming
- **Idle detection** via `GetLastInputInfo`: reminders are skipped when you are away from the computer
- **Pause / Resume** and **Snooze** controls in a small always-on-top control window
- **Smooth fade-in/fade-out** animation
- **Configurable position**: seven anchor presets (corners, top/bottom center, center) plus pixel-level offsets, with screen-edge clamping
- **DPI aware**: correct placement under Windows display scaling (125%/150%)
- **Optional beep** as an audio cue (useful for exclusive-fullscreen games, where overlays cannot render)
- **Session statistics** (reminder count, session duration)

## Requirements

- Windows 10/11
- Python 3.8+ (tkinter is included in the standard python.org and conda installers)

## Quick start

```
python blink_reminder.py
```

For no console window, use `pythonw.exe` instead:

```
pythonw blink_reminder.py
```

Quit via the **Quit** button on the small control window in the bottom-right corner.

### Run at startup

Press `Win+R`, enter `shell:startup`, and place a shortcut there with target:

```
"C:\path\to\pythonw.exe" "C:\path\to\blink_reminder.py"
```

## Configuration

All settings are plain constants at the top of `blink_reminder.py`:

| Setting | Default | Meaning |
|---|---|---|
| `BLINK_INTERVAL` | 60 | Seconds between blink reminders |
| `BLINK_SHOW_TIME` | 8 | Seconds the blink banner stays visible |
| `RULE_202020_INTERVAL` | 1200 | Seconds between 20-20-20 reminders |
| `RULE_202020_SHOW_TIME` | 20 | Display time; acts as the look-away timer |
| `STRETCH_ENABLED` | True | Hourly stretch reminder on/off |
| `IDLE_THRESHOLD` | 120 | Skip reminders if idle longer than this (s) |
| `SNOOZE_MINUTES` | 10 | Snooze duration |
| `PLAY_BEEP` | True | Short beep with each reminder |
| `OVERLAY_ALPHA` | 0.88 | Banner opacity (0–1) |
| `OVERLAY_ANCHOR` | "top-center" | One of: top-left, top-center, top-right, center, bottom-left, bottom-center, bottom-right |
| `OVERLAY_OFFSET_X/Y` | 0 / 40 | Pixel offset from the anchor |

Placement tip for gamers: `top-center` overlaps many games' objective HUDs; `top-right` with `OVERLAY_OFFSET_Y = 60` usually lands in dead space.

A note on `BLINK_INTERVAL`: short intervals (60 s) are useful as initial training, but expect habituation. A sustainable protocol is to start short and deliberately lengthen the interval (e.g., to 180 s) once complete blinking becomes habitual.

## Building a standalone .exe (optional)

Using a clean conda environment (recommended — building from a heavy environment bloats the executable):

```
conda create -n blinkapp python=3.11 -y
conda activate blinkapp
conda install -c conda-forge pyinstaller -y
pyinstaller --onefile --noconsole --name BlinkReminder blink_reminder.py
```

The executable appears in `dist\BlinkReminder.exe` and runs on machines without Python.

Known caveats of `--onefile` builds:

- Antivirus false positives are common; add an exclusion, use `--onedir`, or build with Nuitka if it bothers you
- 1–3 s startup delay (self-extraction to a temp directory)
- ~10–15 MB size (bundled Python runtime)

## Limitations

- **Exclusive-fullscreen games**: overlays cannot render over games in exclusive fullscreen mode, which bypasses the Windows compositor. Use borderless-windowed mode (negligible performance cost on Windows 10/11), or rely on the beep.
- **Multi-monitor**: anchors are relative to the primary display only; the banner does not follow the active window to a secondary monitor.
- **Windows only**: the click-through and idle-detection mechanisms use the Win32 API directly.

## License

MIT — see [LICENSE](LICENSE).
