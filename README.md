# DesktopClock v1.0

**An always-on-top classroom clock for Windows 10/11 whiteboards.** It shows the current period, the subject, and a live countdown — then gets out of the way the moment you start a slideshow.

English · [简体中文](README.zh-CN.md) · [Plain-text version](README.txt)

`Windows 10/11` · `Python 3.8+` · `MIT` · [github.com/hzy32767/DesktopClock](https://github.com/hzy32767/DesktopClock)

![DesktopClock](docs/screenshot.png)

Built for a Seewo (希沃) interactive whiteboard in a Chinese classroom, but it runs on any Windows 10/11 machine. Pure Python standard library — no console window, no installer, no registry, no network.

---

## Contents

- [Features](#features)
- [Quick start](#quick-start)
- [The card at a glance](#the-card-at-a-glance)
- [How the right column is decided](#how-the-right-column-is-decided)
- [Schedule format](#schedule-format)
- [Updating the schedule](#updating-the-schedule)
- [Autostart](#autostart)
- [Configuration](#configuration)
- [Building the executables](#building-the-executables)
- [About antivirus warnings](#about-antivirus-warnings)
- [FAQ](#faq)
- [License](#license)

---

## Features

| | |
| --- | --- |
| **Always on top** | `wm_attributes("-topmost", True)` plus a `SetWindowPos(HWND_TOPMOST)` fallback, re-verified every 5 seconds. |
| **Hides during fullscreen** | PPT slideshow, fullscreen video, Seewo lecture mode, lock screen — the clock disappears and comes back within 1.5 s. |
| **Draggable** | Hold the left mouse button and drop it anywhere. Clamped to the screen so it can never be lost off-screen. |
| **Single instance** | A named kernel mutex. Double-click it ten times and you still get exactly one clock. |
| **Live schedule reload** | Edit `schedule.json`; the clock picks it up within 10 s, no restart. |
| **Writes nothing** | No files, no registry, no settings, no temp files, no network sockets, no keyboard hooks. |
| **Fails quiet** | A missing or broken `schedule.json` just shows the time. No dialog, no crash. |

The card is a 380 × 72 px rounded rectangle with a 1 px border, a vertical gradient and a soft shadow. The rounded corners and the shadow area are **genuinely transparent** (Win32 layered-window colour key), so it reads as a floating card rather than a rectangular window.

---

## Quick start

### Option A — run it (no Python needed)

1. Double-click **`桌面时钟.exe`**.
2. Done. The card appears at the top centre of the screen.

To close it: right-click the card → **退出**.

### Option B — from source

Requires Python 3.8+ with `tkinter` (included in the official Windows installer).

```bat
git clone https://github.com/hzy32767/DesktopClock.git
cd DesktopClock
pythonw clock.pyw
```

`.pyw` is launched by `pythonw.exe`, so no console window flashes up.

### Requirements

- Windows 10 or 11, 64-bit.
- The on-screen text is Chinese (it is a clock for Chinese classrooms). `Microsoft YaHei UI` ships with every Windows 10/11 build, so no language pack is required. If you want English weekday names, edit the `DATE_NAMES` tuple near the top of `clock.pyw`.

### Files

| File | What it is | Needs Python? |
| --- | --- | --- |
| `桌面时钟.exe` | The clock. Double-click this one. | **No** |
| `转换课表.exe` | Converts an `.xlsx` timetable into `schedule.json`. | **No** |
| `开机自启.exe` | Small panel to turn autostart on/off. | **No** |
| `clock.pyw` | The clock, from source. | Yes |
| `convert.py` | The converter, from source. Needs `openpyxl`. | Yes |
| `开机自启.pyw` | The autostart panel, from source. | Yes |
| `转换课表.bat` | Convenience wrapper that runs `convert.py`. | Yes |
| `schedule.json` | The timetable. The clock only ever reads this. | — |
| `时钟.ico` | Application icon. | — |

`convert.py` / `转换课表.exe` are the only things that need `openpyxl`, and only while converting.

---

## The card at a glance

```
┌──────────────────────────────────────────────┐
│                                              │
│   16:48:29        │  ● 第3节 语文            │
│   星期五           │    距上课 25 分 · 距下课 18 分 │
│  ▬▬▬▬▬▬▬▬▬▬                                  │
└──────────────────────────────────────────────┘
```

| Left column (55 %) | Right column (45 %) |
| --- | --- |
| `HH:MM:SS`, 28 px bold, Segoe UI | Status dot + status text, 15 px |
| Weekday, 12 px, Microsoft YaHei UI | Countdown, 11 px |

A 1 px divider sits between the columns at 60 % of the card height.

### The status dot

| Colour | Meaning |
| --- | --- |
| 🟢 `#34C759` | In class right now — it gently "breathes" (colour cycles every 800 ms) |
| 🟠 `#FF9500` | The next class starts within 30 minutes |
| ⚪ `#8E8E93` | Break / no class coming up |

### The bottom progress bar

A 2 px bar that fills from the left in proportion to how much of the current period has elapsed. It is **only visible while you are actually in a class** — during breaks, lunch, or after school it disappears entirely.

---

## How the right column is decided

The two lines are computed independently.

**Status line**, in strict priority order:

1. Now falls inside a time slot **that has a subject** → `第3节 语文` (the slot name `第三节` is normalised to `第3节`).
2. Now falls inside a slot **without** a subject → the slot name, e.g. `课间`, `午饭`, `眼保健操`.
3. Nothing matches, but the next class starts within 30 min → `下节：体育`.
4. Nothing matches → `课间休息`.

**Countdown line** — two independent modules, joined by a `·`:

| Situation | Shown |
| --- | --- |
| In class, and a later class exists | `距上课 25 分 · 距下课 18 分` |
| In class, last class of the day | `距下课 18 分` (centred) |
| Not in class, next class known | `距上课 8 分` (centred) |
| No class left today | `今天没课了` |
| `schedule.json` missing/broken | *(line left blank — only the time is shown)* |

Minutes are rounded **up**, so `距下课` never shows `0 分钟`. If two modules do not fit in the 144 px right column, the line degrades in steps — `分钟` shortens to `分`, then the spacing tightens, and as a last resort only the more relevant module is kept (the "until class ends" one while in class, otherwise the "until next class" one).

---

## Schedule format

`schedule.json` is the only input. Structure:

```json
{
  "version": "1.0",
  "source": "课程表.xlsx",
  "days": {
    "MON": [
      {"name": "第一节", "start": "08:00", "end": "08:40", "subject": "体育"},
      {"name": "课间",   "start": "08:40", "end": "08:55", "subject": ""}
    ],
    "TUE": [],
    "WED": [],
    "THR": [],
    "FRI": []
  }
}
```

Rules:

- Keys are `MON` `TUE` `WED` `THR` `FRI` (plus `SAT` / `SUN` if you want weekends).
- Times are `HH:MM`, zero-padded.
- An empty `subject` means "no lesson in this slot", not "delete this slot". Keep breaks, lunch and eye-exercise slots — the clock uses them to know what is happening.
- Slots are matched by simply checking `start <= now < end`.

---

## Updating the schedule

### Without Python

1. Save the new timetable as `.xlsx` with this layout:

   | Row 1 | *(blank)* | `MON` | `TUE` | `WED` | `THR` | `FRI` | `时间` |
   | --- | --- | --- | --- | --- | --- | --- | --- |
   | Row 2+ | period name, e.g. `第一节` | subject | subject | subject | subject | subject | `8:00-8:40` |

2. Put the file in the same folder (name it `课程表.xlsx` and it is picked up automatically), or double-click **`转换课表.exe`** and choose it.
3. `schedule.json` is rewritten next to the executable. The running clock reloads it within 10 s.

### With Python

```bat
python convert.py path\to\timetable.xlsx
```

Conversion is deterministic — converting the same workbook twice produces a byte-identical `schedule.json`.

### Editing JSON by hand

Perfectly fine. Two things to watch out for:

- Keep the times zero-padded (`08:00`, not `8:00`).
- Keep every slot, even the ones with an empty `subject`.

---

## Autostart

Double-click **`开机自启.exe`** and press the button. That is all.

The program does **not** touch the registry. It only creates or deletes one shortcut in the current user's Startup folder:

```
%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\桌面时钟.lnk
```

There is also a command-line interface:

```bat
开机自启.exe --install    :: turn on
开机自启.exe --remove     :: turn off
开机自启.exe --status     :: exit code 0 = on, 1 = off
```

> If you move the folder, re-run `--install` once so the shortcut points at the new path.

The clock itself does not create a desktop shortcut — do that yourself if you want one (*right-click `桌面时钟.exe` → Send to → Desktop (create shortcut)*). Do not rename or move the program folder afterwards, or the shortcut will break.

---

## Configuration

Everything tunable lives in one block at the top of `clock.pyw`, with Chinese comments. Highlights:

| Constant | Default | Meaning |
| --- | --- | --- |
| `WIDTH` / `HEIGHT` | `380` / `72` | Card size in pixels |
| `TOP_MARGIN` | `12` | Distance from the top of the screen |
| `CORNER_RADIUS` | `16` | Corner radius |
| `WINDOW_ALPHA` | `1.0` | Whole-card opacity. `1.0` = solid. Lowering it also fades the text |
| `CHROMA_KEY` | `#FF00FE` | Colour that becomes transparent — this is what makes the corners round |
| `BG_TOP` / `BG_BOTTOM` | `#FFFFFF` / `#F8F9FB` | Card gradient |
| `BORDER_COLOR` | `#E8EAED` | 1 px border |
| `FG_COLOR` / `MUTED_COLOR` | `#1A1D21` / `#6B7280` | Primary / secondary text |
| `DOT_CLASS_COLOR` | `#34C759` | Dot while in class |
| `DOT_SOON_COLOR` | `#FF9500` | Dot when a class is close |
| `DOT_REST_COLOR` | `#8E8E93` | Dot when resting |
| `BAR_COLOR` / `BAR_HEIGHT` | `#34C759` / `2` | Progress bar |
| `TIME_FONT_PX` | `-28` | Negative = pixels, positive = points |
| `DATE_FONT_PX` / `STATUS_FONT_PX` / `COUNTDOWN_FONT_PX` | `-12` / `-15` / `-11` | Other font sizes |
| `TIME_FONT_FAMILY` | `Segoe UI` | Numerals |
| `TEXT_FONT_FAMILY` | `Microsoft YaHei UI` | Chinese text |
| `DATE_NAMES` | `("星期一", …)` | Weekday labels — edit for another language |
| `TICK_MS` | `1000` | Clock refresh interval |
| `TOPMOST_POLL_MS` | `5000` | How often "am I still on top?" is checked |
| `SCHEDULE_POLL_MS` | `10000` | How often `schedule.json` is checked for changes |
| `NEXT_CLASS_WINDOW_MIN` | `30` | "Class soon" window, also drives the orange dot |
| `NEXT_CLASS_DURING_BREAK` | `False` | Set `True` to prefer `下节：X` over the break name |
| `AUTO_HIDE_ON_FULLSCREEN` | `True` | Hide during slideshows |
| `HIDE_POLL_MS` | `1500` | Fullscreen check interval |
| `DRAGGABLE` / `DRAG_CURSOR` | `True` / `fleur` | Drag support |
| `SINGLE_INSTANCE` / `INSTANCE_MUTEX_NAME` | `True` / `Local\DeskClock.SingleInstance.v1` | One-instance guard |

Editing `clock.pyw` only affects the source version. To change the shipped `.exe`, edit the source and rebuild.

---

## Building the executables

```bat
python -m venv _buildvenv
_buildvenv\Scripts\python.exe -m pip install pyinstaller openpyxl

_buildvenv\Scripts\pyinstaller.exe --noconfirm --clean --onefile --noconsole ^
    --icon 时钟.ico --name DeskClock clock.pyw

_buildvenv\Scripts\pyinstaller.exe --noconfirm --clean --onefile --console ^
    --icon 时钟.ico --name ConvertSchedule convert.py

_buildvenv\Scripts\pyinstaller.exe --noconfirm --clean --onefile --noconsole ^
    --icon 时钟.ico --name Autostart 开机自启.pyw
```

Rename the three output files to `桌面时钟.exe`, `转换课表.exe`, `开机自启.exe` and drop them next to `schedule.json`.

> **Gotcha:** PyInstaller mishandles a non-ASCII `--icon` path. Copy `时钟.ico` to an ASCII name first (e.g. `icon.ico`) and pass that instead.

The `.exe` reads `schedule.json` from **its own folder** (not from the extraction temp dir), so you can swap the timetable without rebuilding.

---

## About antivirus warnings

The source version has nothing to flag: standard library only, no network, no registry writes, no hooks, no self-extraction.

The packaged `.exe` is a different story. PyInstaller's one-file mode is a **self-extracting archive** — at launch it unpacks Python and Tk into `%TEMP%` and runs from there. That pattern is exactly what 火绒 / 360 / Defender heuristics look for, so false positives are common with *any* PyInstaller-built program, not just this one.

If it gets blocked:

1. Add the folder to your antivirus exclusion list, or
2. Use the source version (`clock.pyw`) — nothing to flag, but Python must be installed, or
3. Build a `--onedir` variant yourself, which does not self-extract and is much less likely to be flagged.

This project never connects to the network, never reads other processes' memory, and never writes anything outside its own folder.

---

## FAQ

**The clock vanished.**
Check whether a slideshow or fullscreen video is running — that is intentional, and it returns within 1.5 s of exiting fullscreen. Otherwise it re-asserts `topmost` every 5 s, so it should climb back above anything that covers it.

**Why do I see two `桌面时钟.exe` processes?**
PyInstaller one-file mode: a parent that unpacks and waits, plus the actual child. One clock = two processes. Confirm with the number of cards on screen, which is always one.

**Can I open several clocks?**
No, by design. A named kernel mutex gates startup; later launches exit silently. The mutex is a kernel object, so it is released automatically however the process dies — there is no "stale lock" that stops it from starting.

**I dragged it somewhere and now it is back in the middle.**
Position is deliberately not persisted — that is what keeps the program from writing a single file. To hard-code a start position, change `self.pos_x` / `self.pos_y` in `_place_window()`.

**No icon in the taskbar.**
Correct — it is an `overrideredirect` window, so it never appears there. To tell whether it runs, look at the top of the screen or at the process list.

**Will it work if I copy the folder to another PC?**
Yes. The folder is self-contained and needs no Python. After moving it, re-create any desktop shortcut and re-run `开机自启.exe --install`.

**The timetable has overlapping slots.**
The sample timetable does (an eye-exercise slot 14:45–15:50 that overlaps period 7 at 14:50–15:30). The clock does not "fix" your data: when several slots match, the one **with a subject** wins, so `第7节 语文` is shown correctly. Fix the source spreadsheet if you want it clean.

---

## License

[MIT](LICENSE) © 2026 He Ziyi (何梓逸) · [@hzy32767](https://github.com/hzy32767)

Built for a classroom in China. Issues and pull requests are welcome at
[github.com/hzy32767/DesktopClock](https://github.com/hzy32767/DesktopClock).

