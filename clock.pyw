# -*- coding: utf-8 -*-
"""
clock.pyw —— 教室白板用的桌面时钟（Windows 10/11）

双击运行即可（.pyw 由 pythonw.exe 承载，不会闪出控制台窗口）。
退出：在时钟上点右键 -> 退出。
移动：按住左键就能把卡片拖到屏幕任意位置（位置不保存，重启回到屏幕正上方居中）。
重复打开：双击多少次也只会有**一个**时钟，后来者自动退出（见下面「只允许跑一个」）。

界面是一张 380x72 的实心圆角卡片，挂在屏幕正上方居中、距顶 12px：

    ┌──────────────────────────────────────────┐
    │                         ● 课间休息        │
    │   06:24:36        │                       │
    │   星期三           │   距上课 96 分钟       │
    │  ▬▬▬▬▬▬▬▬                                 │
    └──────────────────────────────────────────┘

    左栏 55%：上行时间（28px Bold，Segoe UI）、下行星期（12px，Microsoft YaHei UI）
    右栏 45%：上行状态圆点 + 状态文字（15px）、下行倒计时（11px）
    中间一条 1px 竖线，高度是卡片的 60%
    底部 2px 进度条，只在「正上课」时按已过比例显示，两端跟着圆角走

卡片不透明：
    整张卡片是不透明的（WINDOW_ALPHA = 1.0），圆角外侧和阴影区靠色键抠成真透明，
    所以只有卡片那一块会挡住底下的内容，不会被它糊住别的窗口。

状态圆点：
    上课中  #34C759，每 800ms 换一档明度做呼吸
    即将上课 #FF9500（30 分钟内）
    休息    #8E8E93

只允许跑一个：
    启动时先 CreateMutexW 抢一个具名内核互斥体，抢不到说明已经有一个在跑了，
    这次就直接退出，不会再开第二个窗口。锁是内核对象，进程一结束就自动释放，
    不落文件、不写注册表，因此也不会出现"上次没关干净导致再也打不开"的情况。
    想恢复成可以多开，把 SINGLE_INSTANCE 改成 False。

全屏时自动隐藏：
    用希沃授课全屏、放 PPT 或全屏放视频的时候，时钟会自己藏起来，
    一退出又自己回来。判断只用两个系统查询（见下面「全屏时自动隐藏」一节），
    不联网、不读别的进程、不写注册表。

硬约束：本文件只使用标准库 tkinter / json / datetime / ctypes / os / math / sys。
        不写注册表、不装键盘钩子、不联网、不打包、不生成任何临时文件，
        所以没有会被杀软盯上的行为。
        功能逻辑（置顶、读 JSON、时间判定）与界面完全分离，改界面不用碰逻辑。
"""
import ctypes
import datetime
import json
import math
import os
import sys
import tkinter as tk
import tkinter.font as tkfont

# ============================== 窗口与卡片 ==============================
WIDTH = 380                  # 卡片宽度（像素）
HEIGHT = 72                  # 卡片高度（像素）
TOP_MARGIN = 12              # 卡片距屏幕上边缘的距离
CORNER_RADIUS = 16           # 圆角半径
WINDOW_ALPHA = 1.0           # 整窗不透明度。1.0 = 完全不透明，卡片是实心的
CHROMA_KEY = "#FF00FE"       # 色键：只把圆角外和阴影区抠成透明，卡片本身不透明

# 单实例：双击好几次也只会有第一个时钟，后来者发现自己不是第一个就直接退出。
# 用内核互斥体（mutex）实现 —— 进程一结束锁就自动没了，不落文件、不写注册表。
SINGLE_INSTANCE = True
INSTANCE_MUTEX_NAME = "Local\\DeskClock.SingleInstance.v1"

# 拖动：按住左键可以把卡片拖到屏幕任意位置。位置**不保存**，重启后回到正上方居中，
# 这样程序依然一个文件都不写（不落配置、不写注册表）。
DRAGGABLE = True
DRAG_CURSOR = "fleur"        # 鼠标移到卡片上时的光标，提示"这里能拖"

# ============================== 配色 ==============================
BG_TOP = "#FFFFFF"           # 卡片背景渐变的上端
BG_BOTTOM = "#F8F9FB"        # 卡片背景渐变的下端
BORDER_COLOR = "#E8EAED"     # 1px 描边
DIVIDER_COLOR = "#E5E5EA"    # 左右栏之间的 1px 竖线
FG_COLOR = "#1A1D21"         # 时间 / 状态文字
MUTED_COLOR = "#6B7280"      # 星期 / 倒计时

DOT_CLASS_COLOR = "#34C759"  # 上课中
DOT_SOON_COLOR = "#FF9500"   # 即将上课
DOT_REST_COLOR = "#8E8E93"   # 休息
# 呼吸动画：上课中时按这个列表循环换色（Canvas 没有透明度，用明度代替）
DOT_BREATH_COLORS = ("#34C759", "#5FD37D", "#8AE2A0", "#8AE2A0", "#5FD37D")

BAR_COLOR = "#34C759"        # 底部进度条
BAR_HEIGHT = 2               # 进度条高度
BAR_BOTTOM_INSET = 1         # 进度条离卡片底边留几像素（让 1px 描边压不住它）

# 阴影：Canvas 画不出半透明，用两层错开的浅灰圆角矩形冒充（越近越深）
SHADOW_ENABLED = True
SHADOW_OFFSETS = (4, 2)                  # 由远到近的垂直偏移
SHADOW_COLORS = ("#F2F4F7", "#E7EAEF")   # 由远到近的颜色
SHADOW_ROOM = 6                          # 卡片下面多留几像素给阴影，不留会被画布裁掉

# ============================== 字体 ==============================
# Tk 只有 normal / bold 两档字重，没有 Medium，状态文字用 normal
TIME_FONT_FAMILY = "Segoe UI"                 # 时间
TIME_FONT_FALLBACKS = ("Segoe UI Variable Display", "Bahnschrift",
                       "Microsoft YaHei UI", "微软雅黑")
TEXT_FONT_FAMILY = "Microsoft YaHei UI"       # 星期 / 状态 / 倒计时
TEXT_FONT_FALLBACKS = ("微软雅黑", "HarmonyOS Sans SC", "MiSans",
                       "Noto Sans SC", "SimHei", "黑体")
FONT_FAMILY_OVERRIDE = ""    # 两个都强制指定成同一个族时填这里，例如 "微软雅黑"

TIME_FONT_PX = -28           # 负数 = 按像素算，不是磅
DATE_FONT_PX = -12
STATUS_FONT_PX = -15
COUNTDOWN_FONT_PX = -11

# ============================== 两栏布局 ==============================
SIDE_PADDING = 16            # 左右栏离卡片边缘各留多少
LEFT_RATIO = 0.55            # 左栏占内容宽度的比例
DIVIDER_HEIGHT_RATIO = 0.60  # 中间竖线的高度占卡片高度的比例
COLUMN_GAP = 6               # 文字离中间竖线至少留多少

ROW_TOP_Y = 25               # 上行（时间 / 状态）的垂直中心
ROW_BOTTOM_Y = 56            # 下行（星期 / 倒计时）的垂直中心

DOT_DIAMETER = 8             # 状态圆点直径
DOT_GAP = 6                  # 圆点和状态文字之间的间距

# ============================== 时间与刷新 ==============================
TICK_MS = 1000               # 时间每秒刷新一次（状态、倒计时、进度条跟着一起重算）
DOT_BREATH_MS = 800          # 呼吸动画周期
TOPMOST_POLL_MS = 5000       # 置顶状态巡检周期
SCHEDULE_POLL_MS = 10000     # schedule.json 变更巡检周期
NEXT_CLASS_WINDOW_MIN = 30   # 「即将上课」的提前量（分钟），也决定圆点变橙色

# 显示优先级严格按需求给的顺序：区间有科目 -> 区间无科目则显示区间名
# -> 下节30分钟内 -> 课间休息。所以课间/午饭默认只显示区间名。
# 想让课间也优先提示「下节：XX」，把它改成 True 即可。
NEXT_CLASS_DURING_BREAK = False

# ============================== 全屏时自动隐藏 ==============================
# 用希沃授课全屏、放 PPT、全屏放视频的时候，把时钟收起来；这些界面一退出，
# 它又自己回来。全程只用两个系统查询，不联网、不读别的进程内存、不装钩子：
#   1) shell32.SHQueryUserNotificationState()：Windows 自己用来判断
#      「现在该不该弹通知」的接口。PPT 放映、全屏视频、锁屏、演示模式
#      都会让系统进入「忙」状态，正好是我们要藏起来的场合。
#   2) 前台窗口的矩形是不是盖住了整块显示器。这是给那些「看起来全屏、
#      但没让系统进入忙状态」的程序兜底（比如无边框最大化的播放器）。
#      最大化窗口只铺到工作区、不含任务栏，所以不会被误判成全屏。
AUTO_HIDE_ON_FULLSCREEN = True
HIDE_POLL_MS = 1500          # 多久查一次；1.5 秒，进出全屏基本是瞬间反应

# SHQueryUserNotificationState 的返回值
_QUNS_NOT_PRESENT = 1        # 锁屏 / 屏保
_QUNS_BUSY = 2               # 有全屏程序，或开了 Windows 演示模式
_QUNS_D3D_FULL_SCREEN = 3    # 独占全屏的 D3D 程序（全屏视频、游戏）
_QUNS_PRESENTATION_MODE = 4  # 系统「演示设置」已打开
# 命中这四个之一就隐藏（只有 5 = 正常使用 才显示）
_HIDE_ON_STATES = (_QUNS_NOT_PRESENT, _QUNS_BUSY,
                   _QUNS_D3D_FULL_SCREEN, _QUNS_PRESENTATION_MODE)
# =====================================================================

def _base_dir():
    """课表所在目录。

    直接双击 clock.pyw 运行时，就是脚本自己所在的文件夹；
    用 PyInstaller 打包成 exe 之后，是 exe 所在的文件夹（而不是解压出来的临时目录），
    这样 exe 旁边的 schedule.json 换掉了就能直接生效，不用重新打包。
    """
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


BASE_DIR = _base_dir()
SCHEDULE_PATH = os.path.join(BASE_DIR, "schedule.json")

# 周一..周日；课表只覆盖周一到周五，周末自然走「课间休息」
DAY_KEYS = ("MON", "TUE", "WED", "THR", "FRI", "SAT", "SUN")
DATE_NAMES = ("星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日")

# ------------------------------------------------------------ Win32 常量
_GWL_STYLE = -16
_GWL_EXSTYLE = -20
_WS_CAPTION = 0x00C00000      # 带标题栏（最大化窗口一定有，真全屏窗口一定没有）
_WS_EX_TOPMOST = 0x00000008
# 点了不激活。卡片是「半透明底衬 + 不透明文字」两个窗口叠出来的，
# 不关掉激活的话，点一下底衬就会被系统提到文字上面去，字就被压住了。
_WS_EX_NOACTIVATE = 0x08000000
_SWP_NOSIZE = 0x0001
_SWP_NOMOVE = 0x0002
_SWP_NOACTIVATE = 0x0010

_IS_WINDOWS = os.name == "nt"


class _RECT(ctypes.Structure):
    _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                ("right", ctypes.c_long), ("bottom", ctypes.c_long)]


class _MONITORINFO(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_ulong), ("rcMonitor", _RECT),
                ("rcWork", _RECT), ("dwFlags", ctypes.c_ulong)]


_MONITOR_DEFAULTTOPRIMARY = 1

if _IS_WINDOWS:
    _user32 = ctypes.windll.user32
    _shell32 = ctypes.windll.shell32

    # 64 位必须用 GetWindowLongPtrW，32 位才是 GetWindowLongW
    if ctypes.sizeof(ctypes.c_void_p) == 8:
        _get_window_long = _user32.GetWindowLongPtrW
        _get_window_long.restype = ctypes.c_void_p
        _set_window_long = _user32.SetWindowLongPtrW
        _set_window_long.restype = ctypes.c_void_p
    else:
        _get_window_long = _user32.GetWindowLongW
        _get_window_long.restype = ctypes.c_long
        _set_window_long = _user32.SetWindowLongW
        _set_window_long.restype = ctypes.c_long
    _get_window_long.argtypes = [ctypes.c_void_p, ctypes.c_int]
    _set_window_long.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p]

    _set_window_pos = _user32.SetWindowPos
    _set_window_pos.restype = ctypes.c_bool
    _set_window_pos.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int,
                                ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                ctypes.c_uint]
    # HWND_TOPMOST 就是 (HWND)-1，按指针宽度取全 1
    _HWND_TOPMOST = ctypes.c_void_p(-1 & ((1 << (ctypes.sizeof(ctypes.c_void_p) * 8)) - 1))

    # 判断全屏要用到的三个查询。句柄在 64 位下是 8 字节，
    # 不显式写 restype 会被 ctypes 当成 int 截断，比出来的矩形就全错了。
    _user32.GetForegroundWindow.restype = ctypes.c_void_p
    _user32.GetDesktopWindow.restype = ctypes.c_void_p
    _user32.GetShellWindow.restype = ctypes.c_void_p
    _user32.MonitorFromWindow.restype = ctypes.c_void_p
    _user32.MonitorFromWindow.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
    _user32.GetMonitorInfoW.argtypes = [ctypes.c_void_p,
                                        ctypes.POINTER(_MONITORINFO)]
    _user32.GetWindowRect.argtypes = [ctypes.c_void_p, ctypes.POINTER(_RECT)]

    _query_notification_state = _shell32.SHQueryUserNotificationState
    _query_notification_state.restype = ctypes.c_long
    _query_notification_state.argtypes = [ctypes.POINTER(ctypes.c_int)]
else:
    _user32 = None
    _shell32 = None
    _query_notification_state = None
    _set_window_long = None


def _set_noactivate(hwnd):
    """
    给窗口加上 WS_EX_NOACTIVATE：鼠标点上去不会激活它，
    系统也就不会顺手把它提到别的置顶窗口上面去。
    """
    if not (hwnd and _IS_WINDOWS and _set_window_long):
        return
    style = _get_window_long(ctypes.c_void_p(hwnd), _GWL_EXSTYLE) or 0
    if style & _WS_EX_NOACTIVATE:
        return
    _set_window_long(ctypes.c_void_p(hwnd), _GWL_EXSTYLE,
                     ctypes.c_void_p(int(style) | _WS_EX_NOACTIVATE))


def system_busy_state():
    """
    问系统「现在忙不忙」。返回 1..5，拿不到就返回 0（当成不忙）。
    5 = 正常；1/2/3/4 分别对应锁屏、有全屏程序或演示模式、
    独占全屏 D3D、系统演示模式。
    """
    if _query_notification_state is None:
        return 0
    state = ctypes.c_int(0)
    try:
        if _query_notification_state(ctypes.byref(state)) != 0:
            return 0
    except OSError:
        return 0
    return state.value


def foreground_is_fullscreen():
    """
    前台窗口是不是盖住了整块显示器。
    最大化窗口只铺到工作区（不含任务栏），所以不会被误判；
    PPT 放映、全屏视频这种真全屏才会四边都顶到显示器边缘。
    """
    if _user32 is None:
        return False
    hwnd = _user32.GetForegroundWindow()
    if not hwnd:
        return False
    # 桌面和任务栏本身不算「全屏程序」
    if hwnd in (_user32.GetDesktopWindow(), _user32.GetShellWindow()):
        return False
    # 带标题栏的窗口也不算：最大化窗口都带标题栏，这样能避开
    # 「任务栏设成自动隐藏时，最大化窗口的矩形正好铺满显示器」的误判。
    # 真全屏（PPT 放映、全屏视频）都是无边框的，不会在这里被漏掉，
    # 而且它们通常也会让 SHQueryUserNotificationState 返回「忙」。
    if (_get_window_long(ctypes.c_void_p(hwnd), _GWL_STYLE) or 0) & _WS_CAPTION:
        return False
    window = _RECT()
    if not _user32.GetWindowRect(ctypes.c_void_p(hwnd), ctypes.byref(window)):
        return False
    if window.right <= window.left or window.bottom <= window.top:
        return False
    monitor = _user32.MonitorFromWindow(ctypes.c_void_p(hwnd),
                                        _MONITOR_DEFAULTTOPRIMARY)
    if not monitor:
        return False
    info = _MONITORINFO()
    info.cbSize = ctypes.sizeof(_MONITORINFO)
    if not _user32.GetMonitorInfoW(ctypes.c_void_p(monitor), ctypes.byref(info)):
        return False
    screen = info.rcMonitor
    return (window.left <= screen.left and window.top <= screen.top
            and window.right >= screen.right
            and window.bottom >= screen.bottom)


def should_hide_now():
    """现在该不该把时钟藏起来（只在 Windows 上判断）"""
    if not AUTO_HIDE_ON_FULLSCREEN or _user32 is None:
        return False
    if system_busy_state() in _HIDE_ON_STATES:
        return True
    return foreground_is_fullscreen()


# ============================== 课表读取 ==============================
def load_schedule(path):
    """
    读 schedule.json。预期内的失败（文件不在、读不动、JSON 坏了、结构不对）
    一律返回 None —— 调用方只显示时间，绝不弹窗打扰上课。
    """
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        days = data["days"]
        if not isinstance(days, dict):
            return None
        return days
    except (OSError, ValueError, TypeError, KeyError):
        # OSError=文件不存在/没权限；ValueError=JSONDecodeError/编码错误
        return None


def read_mtime(path):
    """取文件修改时间；文件不在就返回 None"""
    try:
        return os.path.getmtime(path)
    except OSError:
        return None


# ============================== 时间与判定 ==============================
def to_minutes(text):
    """'08:40' -> 520；格式不对返回 None"""
    try:
        hour_text, minute_text = str(text).split(":")
        hour, minute = int(hour_text), int(minute_text)
    except (ValueError, TypeError):
        return None
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return None
    return hour * 60 + minute


_CN_DIGITS = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
              "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}


def _parse_period_number(body):
    """把「一」「十」「十一」「十二」这类中文数字转成 int"""
    if body.isdigit():
        return int(body)
    if body == "十":
        return 10
    if len(body) == 2:
        if body[0] == "十":
            return 10 + _CN_DIGITS.get(body[1], 0)
        if body[1] == "十":
            return _CN_DIGITS.get(body[0], 0) * 10
        return None
    if len(body) == 3 and body[1] == "十":
        return _CN_DIGITS.get(body[0], 0) * 10 + _CN_DIGITS.get(body[2], 0)
    if len(body) == 1:
        return _CN_DIGITS.get(body)
    return None


def period_prefix(name):
    """'第一节' -> '第1节'；不是「第X节」这种节次名就返回 None"""
    if len(name) < 3 or not name.startswith("第") or not name.endswith("节"):
        return None
    number = _parse_period_number(name[1:-1])
    if not number:
        return None
    return "第%d节" % number


def matching_entries(entries, now_minutes):
    """当前时刻落在哪些区间里（按 JSON 里的先后顺序）"""
    hits = []
    for index, entry in enumerate(entries):
        start = to_minutes(entry.get("start"))
        end = to_minutes(entry.get("end"))
        if start is None or end is None:
            continue
        if start <= now_minutes < end:
            hits.append((index, entry))
    return hits


def pick_entry(hits):
    """
    课表里的区间可能重叠（例如 14:45-15:50 的「眼保健操」既压住了
    14:50-15:30 的第七节，也压住了 15:30 开始的课间）。处理办法：
      1) 带科目的优先，免得正课被区间名盖掉；
      2) 都不带科目时取开始最晚的那个，也就是最贴近当前时刻的那一段。
    """
    if not hits:
        return None, None
    for index, entry in hits:
        if str(entry.get("subject") or "").strip():
            return index, entry
    best_index, best_entry = hits[0]
    best_start = to_minutes(best_entry.get("start")) or 0
    for index, entry in hits[1:]:
        start = to_minutes(entry.get("start")) or 0
        if start > best_start:
            best_index, best_entry, best_start = index, entry, start
    return best_index, best_entry


def next_subject(entries, now_minutes):
    """今天还没开始、且带科目的最近一节课 -> (开始分钟, 科目)；没有就 None"""
    best = None
    for entry in entries:
        subject = str(entry.get("subject") or "").strip()
        if not subject:
            continue
        start = to_minutes(entry.get("start"))
        if start is None or start <= now_minutes:
            continue
        if best is None or start < best[0]:
            best = (start, subject)
    return best


def describe(entries, now_minutes):
    """右栏上行的状态文字，完全由 schedule.json 的区间 + 当前时刻决定"""
    if not entries:
        return "课间休息"

    index, entry = pick_entry(matching_entries(entries, now_minutes))

    if entry is not None:
        subject = str(entry.get("subject") or "").strip()
        name = str(entry.get("name") or "").strip()

        if subject:
            # 有科目 -> 「第X节 科目」；午自习/课一/课二这种没有节次号的显示「名字 科目」
            prefix = period_prefix(name)
            if prefix:
                return "%s %s" % (prefix, subject)
            return ("%s %s" % (name, subject)).strip()

        if name:
            # 无科目 -> 显示区间名（课间 / 大课间 / 午饭 / 眼保健操 ...）
            if NEXT_CLASS_DURING_BREAK:
                upcoming = next_subject(entries, now_minutes)
                if upcoming and 0 < upcoming[0] - now_minutes <= NEXT_CLASS_WINDOW_MIN:
                    return "下节：%s" % upcoming[1]
            return name

    # 没落在任何区间里（或那个区间连名字都没有）
    upcoming = next_subject(entries, now_minutes)
    if upcoming and 0 < upcoming[0] - now_minutes <= NEXT_CLASS_WINDOW_MIN:
        return "下节：%s" % upcoming[1]
    return "课间休息"


def current_entry(entries, now_minutes):
    """当前正在上的那节课（带科目的才算），没有就返回 None"""
    index, entry = pick_entry(matching_entries(entries, now_minutes))
    if entry is None:
        return None
    if not str(entry.get("subject") or "").strip():
        return None
    return entry


def dot_state(entries, now_minutes):
    """状态圆点该用哪种颜色 -> 'class' / 'soon' / 'rest'"""
    if not entries:
        return "rest"
    if current_entry(entries, now_minutes) is not None:
        return "class"
    upcoming = next_subject(entries, now_minutes)
    if upcoming and 0 < upcoming[0] - now_minutes <= NEXT_CLASS_WINDOW_MIN:
        return "soon"
    return "rest"


# ------------------------------------------------------------ 倒计时
def _countdown_text(target_seconds, now_seconds, verb, unit="分钟"):
    """距某个时刻还有多久。不足一分钟说「马上」，其余按分钟向上取整。"""
    remaining = target_seconds - now_seconds
    if remaining <= 0:
        return "马上%s" % verb
    return "距%s %d %s" % (verb, (remaining + 59) // 60, unit)


def counters(entries, now):
    """
    两个各自独立的倒计时：

        距下课 —— 当前正在上的这节课还有多久结束；课间 / 午休时没有，返回 ""
        距上课 —— 今天还没开始、带科目的下一节课还有多久开始；今天没课了返回 ""

    上课的时候两个都有值；课间只有「距上课」，一天最后一节课只有「距下课」。
    now 传 datetime，因为要精确到秒，否则最后几十秒会一直显示「1 分钟」。
    """
    if not entries:
        return "", ""

    now_minutes = now.hour * 60 + now.minute
    now_seconds = now.hour * 3600 + now.minute * 60 + now.second

    to_class = ""
    to_break = ""

    # 正在上课 -> 「距下课」。next_subject 会跳过已经开始的课，
    # 所以下面拿到的必然是「下一节」，正好就是「距上课」想要的。
    entry = current_entry(entries, now_minutes)
    if entry is not None:
        end = to_minutes(entry.get("end"))
        if end is not None:
            to_break = _countdown_text(end * 60, now_seconds, "下课")

    upcoming = next_subject(entries, now_minutes)
    if upcoming is not None:
        to_class = _countdown_text(upcoming[0] * 60, now_seconds, "上课")

    return to_class, to_break


def segment_progress(entries, now):
    """
    底部进度条：当前所处时段已经过掉多少 -> 0.0~1.0。
    不在任何时段里就返回 None（进度条隐藏）。
    """
    if not entries:
        return None
    now_minutes = now.hour * 60 + now.minute
    now_seconds = now.hour * 3600 + now.minute * 60 + now.second

    index, entry = pick_entry(matching_entries(entries, now_minutes))
    if entry is None:
        return None
    start = to_minutes(entry.get("start"))
    end = to_minutes(entry.get("end"))
    if start is None or end is None or end <= start:
        return None
    elapsed = now_seconds - start * 60
    total = (end - start) * 60
    return min(1.0, max(0.0, float(elapsed) / total))


# ============================== 卡片绘制 ==============================
def _hex_to_rgb(text):
    """'#F5F5F7' -> (245, 245, 247)"""
    text = text.lstrip("#")
    return tuple(int(text[i:i + 2], 16) for i in (0, 2, 4))


def _lerp_color(top, bottom, ratio):
    """两个颜色之间按比例插值；Canvas 没有渐变，只能自己一行一行算"""
    ratio = min(1.0, max(0.0, ratio))
    first = _hex_to_rgb(top)
    second = _hex_to_rgb(bottom)
    return "#%02X%02X%02X" % tuple(
        int(round(first[i] + (second[i] - first[i]) * ratio)) for i in range(3))


def row_span(y):
    """
    圆角卡片第 y 行（自上而下 0 起）的水平范围 -> (left, right)，已经按圆角缩进。
    上下两头按行取「该行内最窄的位置」，这样逐行横线拼出来的形状与描边完全重合。
    """
    radius = CORNER_RADIUS
    last_row = HEIGHT - 1
    last_col = WIDTH - 1
    if y < radius:
        dy = radius - y
    elif y > last_row - radius:
        dy = y - (last_row - radius)
    else:
        dy = 0
    inner = radius * radius - dy * dy
    padding = radius - math.sqrt(inner) if inner > 0 else float(radius)
    return padding, last_col - padding


def rounded_rect_points(x0, y0, x1, y1, radius, steps=6):
    """圆角矩形的轮廓点（扁平列表）。Canvas 没有圆角矩形图元，只能自己算。"""
    points = []
    corners = (
        (x1 - radius, y0 + radius, -90.0, 0.0),     # 右上
        (x1 - radius, y1 - radius, 0.0, 90.0),      # 右下
        (x0 + radius, y1 - radius, 90.0, 180.0),    # 左下
        (x0 + radius, y0 + radius, 180.0, 270.0),   # 左上
    )
    for cx, cy, start, end in corners:
        for step in range(steps + 1):
            angle = math.radians(start + (end - start) * step / float(steps))
            points.append(cx + radius * math.cos(angle))
            points.append(cy + radius * math.sin(angle))
    return points


def divider_x():
    """中间那条竖线的横坐标"""
    content = WIDTH - 2 * SIDE_PADDING
    return SIDE_PADDING + int(round(content * LEFT_RATIO))


def draw_card(canvas):
    """
    整张卡片：阴影 + 渐变底 + 1px 描边 + 中间竖线。
    全部画在同一个画布上（卡片不透明，不需要再分层），整个运行期不变，只画一次。
    圆角外侧那些像素没人画，保持画布底色 = 色键，于是被抠成真透明。
    """
    # 1) 阴影：Canvas 画不了模糊，用两层错开的浅灰圆角矩形冒充。
    #    先画最远最浅的一层，再画近一点的深色层，卡片盖上去后只在下方露出一圈。
    if SHADOW_ENABLED:
        for offset, color in zip(SHADOW_OFFSETS, SHADOW_COLORS):
            canvas.create_polygon(
                rounded_rect_points(0, offset, WIDTH - 1, HEIGHT - 1 + offset,
                                    CORNER_RADIUS),
                fill=color, outline=color, width=1)

    # 2) 渐变底：Canvas 没有渐变，逐行画 1px 横线，每行按圆角缩进
    span = float(HEIGHT - 1) if HEIGHT > 1 else 1.0
    for y in range(HEIGHT):
        left, right = row_span(y)
        canvas.create_line(left, y + 0.5, right, y + 0.5, width=1,
                           fill=_lerp_color(BG_TOP, BG_BOTTOM, y / span))

    # 3) 1px 描边：一圈折线，每个圆角用 6 段折线逼近
    canvas.create_polygon(
        rounded_rect_points(0, 0, WIDTH - 1, HEIGHT - 1, CORNER_RADIUS),
        fill="", outline=BORDER_COLOR, width=1, joinstyle=tk.ROUND)

    # 4) 中间那条竖线，高度 60%，垂直居中
    half = int(HEIGHT * DIVIDER_HEIGHT_RATIO / 2.0)
    middle = HEIGHT // 2
    canvas.create_line(divider_x(), middle - half, divider_x(), middle + half,
                       fill=DIVIDER_COLOR, width=1)


def draw_progress_bar(canvas):
    """底部 2px 进度条。逐行创建图元，之后只改坐标；返回 (图元列表, 行号列表)"""
    top = HEIGHT - BAR_BOTTOM_INSET - BAR_HEIGHT
    rows = list(range(top, top + BAR_HEIGHT))
    items = []
    for y in rows:
        left, _right = row_span(y)
        items.append(canvas.create_line(left, y + 0.5, left, y + 0.5,
                                        width=1, fill=BAR_COLOR, state="hidden"))
    return items, rows


def resolve_family(preferred, fallbacks):
    """挑第一个系统里真的装了的字体族，都没有就交给 Tk 兜底，保证不会变方块"""
    if FONT_FAMILY_OVERRIDE:
        return FONT_FAMILY_OVERRIDE
    try:
        available = set(tkfont.families())
    except tk.TclError:
        return "TkDefaultFont"
    for name in (preferred,) + tuple(fallbacks):
        if name and name in available:
            return name
    return "TkDefaultFont"


def _compact_countdown(text, form):
    """
    把一句倒计时压窄。右栏只有 45% 宽（144px），两句「距X 65 分钟」并排要 175px，
    所以按「够不够放」逐级压缩：原样 -> 分钟缩成「分」-> 再去掉数字前的空格。
    """
    if form == "full":
        return text
    text = text.replace("分钟", "分")
    if form == "tight":
        text = text.replace(" ", "")
    return text


def countdown_line(to_class, to_break, font, limit):
    """
    右栏下行那一行倒计时。两个模块都有时先试着并排，放不下就逐级压窄，
    实在放不下才只留最相关的那个（上课时「距下课」更要紧，其余时候「距上课」更要紧）。
    """
    parts = [text for text in (to_class, to_break) if text]
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0]

    for form in ("full", "short", "tight"):
        text = " · ".join(_compact_countdown(part, form) for part in parts)
        if font.measure(text) <= limit:
            return text
    return to_break or to_class


def resolve_hwnd(root):
    """
    拿真正能交给 SetWindowPos 的顶层句柄。
    overrideredirect 窗口外面还套了一层 Tk 的 wrapper，wm frame 才是它；
    拿不到就退回 winfo_id()。
    """
    try:
        frame = root.frame()
    except tk.TclError:
        frame = ""
    try:
        hwnd = int(frame, 16) if isinstance(frame, str) and frame else int(frame)
    except (TypeError, ValueError):
        hwnd = 0
    if not hwnd:
        hwnd = root.winfo_id()
    return hwnd


# ============================== 时钟窗口 ==============================
class ClockWindow(object):
    """
    一个无边框、置顶的 Tk 窗口：
        - 卡片不透明，圆角外侧和阴影区由色键抠成真透明
        - 唯一需要留意的样式是 WS_EX_NOACTIVATE：点卡片不会把它激活，
          讲课时点一下也不会把希沃白板 / PPT 的焦点抢走
    """

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("课程表时钟")
        self.root.overrideredirect(True)          # 去掉标题栏和边框
        self.root.configure(bg=CHROMA_KEY)

        self.schedule = load_schedule(SCHEDULE_PATH)
        self.schedule_mtime = read_mtime(SCHEDULE_PATH)
        self.hwnd = None
        self.breath_phase = 0
        self.last_dot_state = "rest"
        self.last_countdown = ""

        self.time_family = resolve_family(TIME_FONT_FAMILY, TIME_FONT_FALLBACKS)
        self.text_family = resolve_family(TEXT_FONT_FAMILY, TEXT_FONT_FALLBACKS)

        # 画布比卡片高一点，好让阴影露出来；多出来的部分是色键，看不见的
        self.canvas_height = HEIGHT + (SHADOW_ROOM if SHADOW_ENABLED else 0)
        self.canvas = tk.Canvas(self.root, width=WIDTH, height=self.canvas_height,
                                bg=CHROMA_KEY, highlightthickness=0, bd=0)
        self.canvas.pack()
        draw_card(self.canvas)
        self.bar_items, self.bar_rows = draw_progress_bar(self.canvas)

        left_center = (SIDE_PADDING + divider_x()) // 2
        right_center = (divider_x() + WIDTH - SIDE_PADDING) // 2
        self.left_center = left_center
        self.right_center = right_center
        # 右栏文字能用的宽度：以右栏中心为基准，左右都不许压到中间竖线
        self.right_text_width = 2 * (right_center - divider_x() - COLUMN_GAP)

        self.time_font = tkfont.Font(family=self.time_family, size=TIME_FONT_PX,
                                     weight="bold")
        self.date_font = tkfont.Font(family=self.text_family, size=DATE_FONT_PX)
        self.status_font = tkfont.Font(family=self.text_family, size=STATUS_FONT_PX)
        self.countdown_font = tkfont.Font(family=self.text_family,
                                          size=COUNTDOWN_FONT_PX)

        # 左栏：时间 + 星期
        self.time_item = self.canvas.create_text(
            left_center, ROW_TOP_Y, text="--:--:--", fill=FG_COLOR,
            font=self.time_font)
        self.date_item = self.canvas.create_text(
            left_center, ROW_BOTTOM_Y, text="", fill=MUTED_COLOR,
            font=self.date_font)

        # 右栏：状态圆点 + 状态文字（当成一组，整体在右栏居中）
        self.dot_item = self.canvas.create_oval(
            0, 0, 0, 0, fill=DOT_REST_COLOR, outline="", state="hidden")
        self.status_item = self.canvas.create_text(
            right_center, ROW_TOP_Y, text="", fill=FG_COLOR, anchor="w",
            font=self.status_font)
        self.countdown_item = self.canvas.create_text(
            right_center, ROW_BOTTOM_Y, text="", fill=MUTED_COLOR,
            font=self.countdown_font, state="hidden")

        self.pos_x = 0
        self.pos_y = TOP_MARGIN
        self._drag_offset = None
        self._build_menu()
        self._place_window()
        self._apply_window_attributes()

        # wm frame 要等窗口真正建出来才有效
        self.root.update_idletasks()
        self.hwnd = resolve_hwnd(self.root)
        # 点卡片不激活，讲课时不会把白板 / PPT 的焦点抢走
        _set_noactivate(self.hwnd)
        self.apply_topmost()

        self._after_ids = {}
        self.is_hidden = False
        self.tick()
        self._schedule("breath", DOT_BREATH_MS, self.breathe)
        self._schedule("topmost", TOPMOST_POLL_MS, self.keep_topmost)
        self._schedule("schedule", SCHEDULE_POLL_MS, self.poll_schedule)
        self._schedule("fullscreen", HIDE_POLL_MS, self.poll_fullscreen)

    def _schedule(self, slot, delay_ms, callback):
        """
        按「槽位」登记 after 任务：同一个槽位重新登记就覆盖旧 id。
        这样周期任务的 id 不会越攒越多，退出时也只需撤销最后一批。
        """
        self._after_ids[slot] = self.root.after(delay_ms, callback)

    # ---------------------------------------------------------- 窗口外观
    def _place_window(self):
        """
        起始位置：屏幕正上方居中，卡片上边缘距屏幕 TOP_MARGIN 像素。
        之后可以用鼠标把卡片拖到任意位置 —— 但位置不保存，下次启动还是回到这里。
        """
        self.pos_x = max(0, (self.root.winfo_screenwidth() - WIDTH) // 2)
        self.pos_y = TOP_MARGIN
        self.root.geometry("%dx%d+%d+%d"
                           % (WIDTH, self.canvas_height, self.pos_x, self.pos_y))

    def _move_to(self, x, y):
        """
        拖动时用：只改位置不改尺寸。坐标夹在屏幕内，
        免得手一抖把卡片拖到看不见的地方找不回来。
        """
        limit_x = max(0, self.root.winfo_screenwidth() - WIDTH)
        limit_y = max(0, self.root.winfo_screenheight() - self.canvas_height)
        self.pos_x = min(limit_x, max(0, int(x)))
        self.pos_y = min(limit_y, max(0, int(y)))
        self.root.geometry("+%d+%d" % (self.pos_x, self.pos_y))

    # -------------------------------------------------------------- 拖动
    def _drag_begin(self, event):
        """记下鼠标点在卡片里的哪个位置，之后按位移平移，卡片不会跳一下"""
        self._drag_offset = (event.x_root - self.pos_x,
                             event.y_root - self.pos_y)

    def _drag_motion(self, event):
        if self._drag_offset is None:
            return
        self._move_to(event.x_root - self._drag_offset[0],
                      event.y_root - self._drag_offset[1])

    def _drag_end(self, _event=None):
        self._drag_offset = None

    def _apply_window_attributes(self):
        # 先设整窗不透明度，再设色键；这个顺序下两个属性可以共存（已实测）
        try:
            self.root.attributes("-alpha", WINDOW_ALPHA)
        except tk.TclError:
            pass
        try:
            # Windows 专有：把色键像素整块抠透明，圆角外侧和阴影区才是真透明
            self.root.attributes("-transparentcolor", CHROMA_KEY)
        except tk.TclError:
            # 老版本 Tk 没有这个属性：退化成直角卡片，不影响使用
            pass
        try:
            self.root.attributes("-topmost", True)
        except tk.TclError:
            pass

    # -------------------------------------------------------------- 置顶
    def apply_topmost(self):
        """两道保险：Tk 自己的 -topmost，加 SetWindowPos(HWND_TOPMOST) 兜底"""
        try:
            self.root.attributes("-topmost", True)
        except tk.TclError:
            pass
        if self.hwnd and _IS_WINDOWS:
            _set_window_pos(ctypes.c_void_p(self.hwnd), _HWND_TOPMOST, 0, 0, 0, 0,
                            _SWP_NOSIZE | _SWP_NOMOVE | _SWP_NOACTIVATE)

    def is_topmost(self):
        """直接问系统：窗口当前的扩展样式里还有没有 WS_EX_TOPMOST"""
        if self.hwnd and _IS_WINDOWS:
            extended_style = _get_window_long(ctypes.c_void_p(self.hwnd), _GWL_EXSTYLE) or 0
            return bool(extended_style & _WS_EX_TOPMOST)
        try:
            return bool(self.root.attributes("-topmost"))
        except tk.TclError:
            return False

    def keep_topmost(self):
        """每 5 秒巡检一次，置顶被别人抢走就立刻抢回来"""
        if not self.is_topmost():
            self.apply_topmost()
        self._schedule("topmost", TOPMOST_POLL_MS, self.keep_topmost)

    # ---------------------------------------------------------- 全屏时隐藏
    def set_hidden(self, hidden):
        """
        藏起来 / 放回去。withdraw 是把窗口真正取消映射，
        既不会显示，也不会挡住鼠标点击；deiconify 回来之后
        置顶和透明度要重新确认一次（重新映射会重置分层窗口属性）。
        """
        if hidden == self.is_hidden:
            return
        self.is_hidden = hidden
        try:
            if hidden:
                self.root.withdraw()
            else:
                self.root.deiconify()
                self.apply_topmost()
                self._apply_window_attributes()
                # 重新映射之后位置也确认一次，免得回到默认位置
                self._move_to(self.pos_x, self.pos_y)
        except tk.TclError:
            pass

    def poll_fullscreen(self):
        """每 1.5 秒看一眼：PPT 放映 / 全屏视频之类开始了就藏，结束了就回来"""
        self.set_hidden(should_hide_now())
        self._schedule("fullscreen", HIDE_POLL_MS, self.poll_fullscreen)

    # -------------------------------------------------------------- 刷新
    def render(self, now, entries):
        """把某个时刻的内容画上去（和 tick 分开，方便单独拿固定时刻做检查）"""
        self.canvas.itemconfigure(self.time_item, text=now.strftime("%H:%M:%S"))
        self.canvas.itemconfigure(self.date_item, text=DATE_NAMES[now.weekday()])
        self.update_status(entries, now)
        self.update_countdown(entries, now)
        self.update_progress(entries, now)

    def tick(self):
        now = datetime.datetime.now()
        self.render(now, self.entries_for(now))
        self._schedule("tick", TICK_MS, self.tick)

    def breathe(self):
        """状态圆点的呼吸：只在「上课中」时换色，其余时候没必要动"""
        self.breath_phase += 1
        if self.last_dot_state == "class":
            self.canvas.itemconfigure(
                self.dot_item,
                fill=DOT_BREATH_COLORS[self.breath_phase % len(DOT_BREATH_COLORS)])
        self._schedule("breath", DOT_BREATH_MS, self.breathe)

    def entries_for(self, now):
        """今天这个星期几的时段列表；课表读不到就返回 None"""
        if self.schedule is None:
            return None
        entries = self.schedule.get(DAY_KEYS[now.weekday()])
        return entries if isinstance(entries, list) else []

    # ---------------------------------------------------- 右栏上行：状态
    def update_status(self, entries, now):
        if entries is None:
            # 课表读不到：只留左栏的时间，右栏整块留空
            self.canvas.itemconfigure(self.dot_item, state="hidden")
            self.canvas.itemconfigure(self.status_item, state="hidden")
            self.last_dot_state = "rest"
            return

        now_minutes = now.hour * 60 + now.minute
        text = describe(entries, now_minutes)
        state = dot_state(entries, now_minutes)
        self.last_dot_state = state

        if state == "class":
            color = DOT_BREATH_COLORS[self.breath_phase % len(DOT_BREATH_COLORS)]
        elif state == "soon":
            color = DOT_SOON_COLOR
        else:
            color = DOT_REST_COLOR

        # 圆点和文字当成一整组，在右栏里水平居中
        radius = DOT_DIAMETER / 2.0
        total = DOT_DIAMETER + DOT_GAP + self.status_font.measure(text)
        start = self.right_center - total / 2.0
        self.canvas.coords(self.dot_item, start, ROW_TOP_Y - radius,
                           start + DOT_DIAMETER, ROW_TOP_Y + radius)
        self.canvas.coords(self.status_item, start + DOT_DIAMETER + DOT_GAP,
                           ROW_TOP_Y)
        self.canvas.itemconfigure(self.dot_item, fill=color, state="normal")
        self.canvas.itemconfigure(self.status_item, text=text, state="normal")

    # -------------------------------------------------- 右栏下行：倒计时
    def update_countdown(self, entries, now):
        if entries is None:
            self.canvas.itemconfigure(self.countdown_item, state="hidden")
            return
        to_class, to_break = counters(entries, now)
        text = countdown_line(to_class, to_break, self.countdown_font,
                              self.right_text_width)
        if not text:
            text = "今天没课了"
        if text != self.last_countdown:
            self.canvas.itemconfigure(self.countdown_item, text=text)
            self.last_countdown = text
        self.canvas.itemconfigure(self.countdown_item, state="normal")

    # -------------------------------------------------------- 底部进度条
    def update_progress(self, entries, now):
        if entries is None:
            self._show_bar(False)
            return
        # 需求：进度条只在上课时出现，课间 / 午休 / 放学后都不显示。
        # 判定口径与状态圆点、状态文字保持一致：那一段必须带科目才算「上课」。
        if current_entry(entries, now.hour * 60 + now.minute) is None:
            self._show_bar(False)
            return
        progress = segment_progress(entries, now)
        if progress is None:
            self._show_bar(False)
            return
        for item, y in zip(self.bar_items, self.bar_rows):
            left, right = row_span(y)
            end = left + (right - left) * progress
            if end - left < 1.5:           # 太短会缩成一个小点，干脆不画
                self._show_bar(False)
                return
            self.canvas.coords(item, left, y + 0.5, end, y + 0.5)
        self._show_bar(True)

    def _show_bar(self, visible):
        state = "normal" if visible else "hidden"
        for item in self.bar_items:
            self.canvas.itemconfigure(item, state=state)

    def poll_schedule(self):
        """每 10 秒比一次 schedule.json 的修改时间，变了才重新读"""
        mtime = read_mtime(SCHEDULE_PATH)
        if mtime != self.schedule_mtime:
            self.schedule_mtime = mtime
            reloaded = load_schedule(SCHEDULE_PATH)
            if reloaded is not None:
                self.schedule = reloaded      # 新文件坏了就继续用旧的
        self._schedule("schedule", SCHEDULE_POLL_MS, self.poll_schedule)

    # ------------------------------------------------------------ 右键菜单
    def _build_menu(self):
        self.menu = tk.Menu(self.root, tearoff=0)
        self.menu.add_command(label="退出", command=self.quit)
        for widget in (self.root, self.canvas):
            widget.bind("<Button-3>", self._popup_menu)
            if DRAGGABLE:
                widget.bind("<Button-1>", self._drag_begin, add="+")
                widget.bind("<B1-Motion>", self._drag_motion, add="+")
                widget.bind("<ButtonRelease-1>", self._drag_end, add="+")
                widget.configure(cursor=DRAG_CURSOR)

    def _popup_menu(self, event):
        try:
            self.menu.tk_popup(event.x_root, event.y_root)
        finally:
            # 菜单已经被销毁时 grab 也一并没了，这里再释放会报错，忽略掉
            try:
                self.menu.grab_release()
            except tk.TclError:
                pass

    def quit(self):
        for after_id in self._after_ids.values():
            try:
                self.root.after_cancel(after_id)
            except tk.TclError:
                pass
        self._after_ids = {}
        try:
            self.root.destroy()
        except tk.TclError:
            pass

    def run(self):
        self.root.mainloop()


def acquire_single_instance(name):
    """
    具名内核互斥体做「只允许跑一个」。

    返回 True 表示拿到了锁（可以继续跑），False 表示已经有一个在跑了。
    进程无论怎么退出，内核都会自动释放这个锁，所以不存在
    「上次没关干净导致这次打不开」的情况；也完全不落文件、不写注册表。
    """
    if not (_IS_WINDOWS and SINGLE_INSTANCE):
        return True
    try:
        # 单独开一个 use_last_error=True 的句柄：ctypes 会在调用后立刻把
        # 错误码存起来，不会被中间的其他 Win32 调用冲掉
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateMutexW.restype = ctypes.c_void_p
        kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_bool,
                                          ctypes.c_wchar_p]
        # 句柄故意不关：它要一直活到进程结束，由内核负责清理
        handle = kernel32.CreateMutexW(None, False, name)
        if not handle:
            return True                      # 建不出来就别拦着，照常跑
        if ctypes.get_last_error() == 183:   # ERROR_ALREADY_EXISTS
            return False
        acquire_single_instance.handle = handle
        return True
    except (OSError, AttributeError):
        return True


def main():
    if not acquire_single_instance(INSTANCE_MUTEX_NAME):
        return                               # 已经有一个时钟在跑了，安静退出
    ClockWindow().run()


if __name__ == "__main__":
    main()
