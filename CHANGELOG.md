# Changelog

All notable changes to DesktopClock are documented here.

## v1.0 — 2026-10-16

First stable release.

### The card

- 380 × 72 px rounded card at the top centre of the screen, 12 px from the edge.
- 16 px corner radius, 1 px `#E8EAED` border, vertical `#FFFFFF` → `#F8F9FB` gradient,
  soft two-layer shadow.
- Rounded corners and shadow area are genuinely transparent (Win32 layered-window
  colour key), so it reads as a floating card.
- Two columns split 55 / 45 by a 1 px divider at 60 % of the card height:
  - left: `HH:MM:SS` (28 px bold Segoe UI) over the weekday (12 px),
  - right: an 8 px status dot plus status text (15 px) over a countdown (11 px).
- 2 px progress bar along the bottom, visible only while a lesson is running.

### Behaviour

- Always on top via `wm_attributes("-topmost")` with a `SetWindowPos(HWND_TOPMOST)`
  fallback; re-verified every 5 s.
- Hides automatically during PPT slideshows, fullscreen video, Seewo lecture mode and
  the lock screen (`SHQueryUserNotificationState` plus a foreground-window geometry
  check). Returns within 1.5 s.
- Drag with the left mouse button, clamped to the screen. The position is deliberately
  not persisted.
- Single instance enforced by a named kernel mutex (`Local\DeskClock.SingleInstance.v1`).
  Later launches exit silently; the lock is released by the kernel however the process
  ends, so there is no stale-lock failure mode.
- `schedule.json` is polled every 10 s and reloaded only when its mtime changes.
- A missing or broken schedule degrades to showing the time only — no dialog, no crash.
- Right-click → 退出.

### Schedule

- Four-step status priority: subject slot → named slot → next class within 30 min →
  `课间休息`.
- Two independent countdown modules joined by `·`, each of which can degrade to a single
  module when the right column is too narrow.

### Tooling

- `convert.py` turns an `.xlsx` timetable into `schedule.json` deterministically. It
  resolves the workbook from `argv[1]`, then a `课程表.xlsx` beside it, then any single
  `.xlsx` in the folder, then a file dialog.
- `开机自启.pyw` toggles autostart by creating or deleting one shortcut in the user's
  Startup folder. It never touches the registry, and ships with `--install`, `--remove`
  and `--status` for scripting.
- Three one-file PyInstaller executables (`桌面时钟.exe`, `转换课表.exe`,
  `开机自启.exe`) so the folder runs on a machine without Python.
- Bilingual documentation (English / Chinese, each in Markdown and plain text).

### Design notes

- Never writes a file, never opens a socket, never installs a hook. The only persistent
  state is the Startup shortcut, and only when you explicitly enable it.
- Draws to a single `tk.Canvas`; the only Win32 calls are for topmost enforcement,
  the colour key, the fullscreen query, drag clamping and the instance mutex.

## Pre-release history

| Build | Change |
| --- | --- |
| `v1.0-preview2` | Removed the translucency experiment, added the single-instance guard. |
| `v1.0-preview1` | Two-column card with status dot; fullscreen auto-hide; draggable. |
| `beta-stable` | Three-line card, two countdown modules, progress bar, HarmonyOS Sans SC. |
| initial | Single-window clock, `schedule.json`, topmost polling, right-click quit. |
