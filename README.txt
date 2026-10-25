==============================================================================
 DesktopClock v1.0
 An always-on-top classroom clock for Windows 10/11 whiteboards
------------------------------------------------------------------------------
 He Ziyi (何梓逸)  -  https://github.com/hzy32767/DesktopClock
 MIT License
==============================================================================

 A small card at the top of the screen that shows:
     - the time and the weekday
     - the current period and subject
     - how long until the next class / the end of this class
     - a thin progress bar while a lesson is running

 It stays on top of every window, hides itself during a slideshow or a
 fullscreen video, and you can drag it anywhere with the mouse.

 Written in the Python standard library only. No installer, no registry,
 no network, no console window, and it never writes a single file.

 Full documentation: README.md  (English)  /  README.zh-CN.md  (Chinese)


------------------------------------------------------------------------------
 WHAT IS IN THIS FOLDER
------------------------------------------------------------------------------

   桌面时钟.exe     The clock. Double-click this.        (no Python needed)
   转换课表.exe     Converts an .xlsx timetable.         (no Python needed)
   开机自启.exe     Turns autostart on / off.            (no Python needed)

   clock.pyw        The clock, as source.                (needs Python)
   convert.py       The converter, as source.            (needs Python + openpyxl)
   开机自启.pyw      The autostart panel, as source.      (needs Python)
   转换课表.bat      Wrapper that runs convert.py.        (needs Python)

   schedule.json    The timetable. The clock only reads this.
   时钟.ico          Application icon.


------------------------------------------------------------------------------
 QUICK START
------------------------------------------------------------------------------

   No Python needed:

      1. Double-click  桌面时钟.exe
      2. That's it. The card appears at the top centre of the screen.

   To move it:  hold the left mouse button and drag.
   To close it: right-click the card -> 退出


------------------------------------------------------------------------------
 WHAT THE RIGHT SIDE MEANS
------------------------------------------------------------------------------

   The dot:

      green    in class right now (it gently pulses)
      orange   the next class starts within 30 minutes
      grey     break / nothing coming up

   The first line, in priority order:

      1. inside a slot that has a subject   ->  第3节 语文
      2. inside a slot without a subject    ->  课间 / 午饭 / 眼保健操
      3. no match, next class within 30 min ->  下节：体育
      4. no match at all                    ->  课间休息

   The second line (countdown):

      距上课25分 · 距下课18分     in class, more classes later
      距下课18分                  in class, last class of the day
      距上课8分                   between classes
      今天没课了                  done for today
      (blank)                     schedule.json is missing or broken

   The thin green bar at the bottom only appears while you are actually
   in a lesson, and fills up as the lesson goes on.


------------------------------------------------------------------------------
 CHANGING THE TIMETABLE
------------------------------------------------------------------------------

   Without Python:

      1. Prepare the new timetable as an .xlsx file. Row 1 is a header:
         empty cell, then MON / TUE / WED / THR / FRI, then 时间.
         From row 2 on, each row is one time slot:
         period name, five subjects, then a time range like 8:00-8:40.

      2. Either drop it into this folder named 课程表.xlsx (it is picked up
         automatically), or double-click 转换课表.exe and choose the file.

      3. schedule.json is rewritten next to the executable. A clock that is
         already running reloads it within 10 seconds - no restart needed.

   With Python:

      python convert.py path\to\timetable.xlsx


------------------------------------------------------------------------------
 AUTOSTART
------------------------------------------------------------------------------

   Double-click 开机自启.exe and press the button.

   The program does NOT touch the registry. It only creates or deletes one
   shortcut here:

      %APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\桌面时钟.lnk

   Command line:

      开机自启.exe --install     turn on
      开机自启.exe --remove      turn off
      开机自启.exe --status      exit code 0 = on, 1 = off

   If you move this folder somewhere else, run --install again so the
   shortcut points at the new location.


------------------------------------------------------------------------------
 IF THE CLOCK DISAPPEARS
------------------------------------------------------------------------------

   Check whether a slideshow or a fullscreen video is running. The clock
   hides itself on purpose in fullscreen and comes back within 1.5 seconds
   of leaving it. Otherwise it re-asserts "always on top" every 5 seconds.

   To stop the hiding behaviour, set AUTO_HIDE_ON_FULLSCREEN = False near
   the top of clock.pyw (source version only, or rebuild the .exe).


------------------------------------------------------------------------------
 TWEAKING IT
------------------------------------------------------------------------------

   Everything adjustable is in one block at the top of clock.pyw, with
   comments. Size, colours, fonts, refresh intervals, the 30-minute
   "class soon" window, and so on.

   Changing clock.pyw only affects the source version. To change the
   shipped .exe, edit the source and rebuild with PyInstaller.

   Build commands are in README.md, section "Building the executables".


------------------------------------------------------------------------------
 ABOUT ANTIVIRUS WARNINGS
------------------------------------------------------------------------------

   The source version (clock.pyw) has nothing to flag.

   The .exe is built with PyInstaller in one-file mode, which is a
   self-extracting archive: at launch it unpacks Python and Tk into %TEMP%
   and runs from there. Some antivirus products flag that pattern. If yours
   does, either whitelist the folder, or use the source version, or build
   a --onedir variant yourself.


------------------------------------------------------------------------------
 UNINSTALL
------------------------------------------------------------------------------

   1. Right-click the card -> 退出
   2. Run 开机自启.exe and turn autostart off (or --remove)
   3. Delete this folder


------------------------------------------------------------------------------
 LICENSE
------------------------------------------------------------------------------

   MIT. See the LICENSE file.

   Requires Windows 10/11. The on-screen text is Chinese; the font it uses,
   Microsoft YaHei UI, ships with every Windows 10/11 build.
==============================================================================
