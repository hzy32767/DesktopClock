# -*- coding: utf-8 -*-
"""桌面时钟 · 开机自启设置

双击本文件会弹出一个小窗口，用来打开 / 关闭「开机自动启动时钟」。

也可以在命令行里直接调用（方便批处理或者自动安装脚本）：
    开机自启.pyw --install     开启开机自启
    开机自启.pyw --remove      关闭开机自启
    开机自启.pyw --status      只打印当前状态，已开启返回码 0，未开启返回码 1

原理：全程不碰注册表。只在当前用户的「启动」文件夹
(%APPDATA%\\Microsoft\\Windows\\Start Menu\\Programs\\Startup) 里
增加或删除一个名为「桌面时钟.lnk」的快捷方式 —— 和手动把时钟拖进
「启动」文件夹完全是同一件事，不想要了删掉即可，不留任何残留。
"""

import os
import subprocess
import sys
import tempfile
import tkinter as tk
from tkinter import font as tkfont

APP_NAME = "桌面时钟"


def _base_dir():
    """打包成 exe 时是 exe 旁边的目录，直接跑 .pyw 时是脚本旁边的目录"""
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


HERE = _base_dir()
LINK_NAME = APP_NAME + ".lnk"
DESCRIPTION = "桌面时钟 · 课表时钟组件"

BG = "#F5F5F7"
FG = "#1D1D1F"
MUTED = "#6E6E73"
OK_COLOR = "#1E9E4A"
OFF_COLOR = "#B0B0B5"
BTN_BG = "#FFFFFF"


# ---------------------------------------------------------------- 路径与状态
def startup_dir():
    """当前用户的「启动」文件夹"""
    appdata = os.environ.get("APPDATA", "")
    return os.path.join(appdata, "Microsoft", "Windows", "Start Menu", "Programs", "Startup")


def link_path():
    return os.path.join(startup_dir(), LINK_NAME)


def clock_target():
    """返回要开机启动的目标。优先用打包好的 exe，其次用 clock.pyw"""
    exe = os.path.join(HERE, APP_NAME + ".exe")
    if os.path.isfile(exe):
        return exe
    pyw = os.path.join(HERE, "clock.pyw")
    if os.path.isfile(pyw):
        return pyw
    return ""


def icon_path():
    ico = os.path.join(HERE, "时钟.ico")
    return ico if os.path.isfile(ico) else ""


def is_enabled():
    return os.path.isfile(link_path())


# ---------------------------------------------------------------- 调 PowerShell 建/删快捷方式
def _ps_quote(text):
    """PowerShell 单引号字符串里，单引号要写两遍"""
    return "'" + str(text).replace("'", "''") + "'"


def _run_powershell(script):
    """把脚本写成临时 .ps1 再执行。用 utf-8-sig，Windows PowerShell 5.1 才认中文"""
    fd, path = tempfile.mkstemp(suffix=".ps1", prefix="dsh_clock_")
    try:
        with os.fdopen(fd, "w", encoding="utf-8-sig") as fh:
            fh.write(script)
        creation = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        proc = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive",
             "-ExecutionPolicy", "Bypass", "-File", path],
            capture_output=True, text=True, timeout=60,
            creationflags=creation)
        return proc.returncode, (proc.stdout or "").strip(), (proc.stderr or "").strip()
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


def enable():
    """开启开机自启。返回 (是否成功, 说明文字)"""
    target = clock_target()
    if not target:
        return False, ("没找到 clock.pyw 或 %s.exe。\n"
                       "请把本文件和时钟程序放在同一个文件夹里再运行。" % APP_NAME)

    ico = icon_path()
    icon_line = ""
    if ico:
        icon_line = "$sc.IconLocation = %s\n" % _ps_quote(ico + ",0")

    script = (
        "$ErrorActionPreference = 'Stop'\n"
        "$ws = New-Object -ComObject WScript.Shell\n"
        "$sc = $ws.CreateShortcut(%s)\n"
        "$sc.TargetPath = %s\n"
        "$sc.Arguments = ''\n"
        "$sc.WorkingDirectory = %s\n"
        "$sc.Description = %s\n"
        "%s"
        "$sc.Save()\n"
        "if (-not (Test-Path -LiteralPath %s)) { throw '快捷方式没有创建成功' }\n"
        "Write-Output 'OK'\n"
    ) % (_ps_quote(link_path()), _ps_quote(target), _ps_quote(HERE),
         _ps_quote(DESCRIPTION), icon_line, _ps_quote(link_path()))

    code, out, err = _run_powershell(script)
    if code == 0 and out.endswith("OK"):
        return True, "已开启。以后每次开机，时钟会自动出现在屏幕顶部。"
    return False, "开启失败。\n%s" % (err or out or "PowerShell 返回码 %d" % code)


def disable():
    """关闭开机自启。返回 (是否成功, 说明文字)"""
    script = (
        "$ErrorActionPreference = 'Stop'\n"
        "if (Test-Path -LiteralPath %s) { Remove-Item -LiteralPath %s -Force }\n"
        "if (Test-Path -LiteralPath %s) { throw '删除失败，可能被占用了' }\n"
        "Write-Output 'OK'\n"
    ) % (_ps_quote(link_path()), _ps_quote(link_path()), _ps_quote(link_path()))

    code, out, err = _run_powershell(script)
    if code == 0 and out.endswith("OK"):
        return True, "已关闭。时钟不会再自动启动，需要时双击 clock.pyw 即可。"
    return False, "关闭失败。\n%s" % (err or out or "PowerShell 返回码 %d" % code)


def read_link_target():
    """读一下启动项当前指向哪里，用来发现「时钟被挪走了」的情况"""
    if not is_enabled():
        return ""
    script = (
        "$ErrorActionPreference = 'Stop'\n"
        "$ws = New-Object -ComObject WScript.Shell\n"
        "$sc = $ws.CreateShortcut(%s)\n"
        "Write-Output $sc.TargetPath\n"
    ) % _ps_quote(link_path())
    code, out, _ = _run_powershell(script)
    return out if code == 0 else ""


# ---------------------------------------------------------------- 界面
def pick_font(root):
    families = set(tkfont.families(root))
    for name in ("HarmonyOS Sans SC", "Microsoft YaHei UI", "微软雅黑", "Segoe UI"):
        if name in families:
            return name
    return "TkDefaultFont"


class Panel(object):
    def __init__(self):
        self.root = tk.Tk()
        self.root.title(APP_NAME + " · 开机自启")
        self.root.configure(bg=BG)
        self.root.resizable(False, False)
        self.family = pick_font(self.root)

        width, height = 400, 268
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        x = (screen_w - width) // 2
        y = (screen_h - height) // 2
        self.root.geometry("%dx%d+%d+%d" % (width, height, x, y))

        head = tk.Label(self.root, text="开机自动启动", bg=BG, fg=FG,
                        font=(self.family, -19, "bold"))
        head.pack(pady=(22, 2))

        self.status = tk.Label(self.root, bg=BG, font=(self.family, -14, "bold"))
        self.status.pack(pady=(6, 0))

        self.detail = tk.Label(self.root, bg=BG, fg=MUTED, font=(self.family, -10),
                               wraplength=340, justify="center")
        self.detail.pack(pady=(4, 0))

        row = tk.Frame(self.root, bg=BG)
        row.pack(pady=(16, 0))
        self.btn_on = self._button(row, "开启开机自启", self.do_enable)
        self.btn_on.pack(side="left", padx=5)
        self.btn_off = self._button(row, "关闭开机自启", self.do_disable)
        self.btn_off.pack(side="left", padx=5)

        self.hint = tk.Label(
            self.root, bg=BG, fg=MUTED, font=(self.family, -9), justify="center",
            text="关闭本窗口不会影响时钟运行。\n想立刻看效果，双击文件夹里的 clock.pyw。")
        self.hint.pack(side="bottom", pady=(0, 14))

        self.refresh()

    def _button(self, parent, text, command):
        btn = tk.Button(parent, text=text, command=command, font=(self.family, -11),
                        bg=BTN_BG, fg=FG, activebackground="#EAEAEC",
                        relief="flat", bd=0, padx=14, pady=7, cursor="hand2")
        return btn

    # ------------------------------------------------------------ 状态刷新
    def refresh(self):
        enabled = is_enabled()
        if enabled:
            self.status.configure(text="● 已开启", fg=OK_COLOR)
            target = read_link_target()
            if target and os.path.normcase(target) != os.path.normcase(clock_target()):
                self.detail.configure(
                    text="启动项指向：%s\n（不是当前这个文件夹里的时钟，建议先关闭再重新开启）" % target)
            else:
                self.detail.configure(text="每次开机自动启动，不需要手动双击。")
            self.btn_on.configure(state="disabled")
            self.btn_off.configure(state="normal")
        else:
            self.status.configure(text="○ 未开启", fg=OFF_COLOR)
            self.detail.configure(text="开机后需要自己双击 clock.pyw 才能看到时钟。")
            self.btn_on.configure(state="normal")
            self.btn_off.configure(state="disabled")

    def _toast(self, ok, message):
        self.detail.configure(text=message, fg=(MUTED if ok else "#C0392B"))
        self.refresh()
        if ok:
            self.detail.configure(fg=MUTED)

    def do_enable(self):
        ok, message = enable()
        self._toast(ok, message)

    def do_disable(self):
        ok, message = disable()
        self._toast(ok, message)

    def run(self):
        self.root.mainloop()


# ---------------------------------------------------------------- 命令行入口
def _say(text):
    """打印一行。用 pythonw / 打包成窗口程序运行时 stdout 是 None，不能直接 print"""
    if sys.stdout is not None:
        print(text)


def main(argv):
    if "--install" in argv:
        ok, message = enable()
        _say(("OK " if ok else "FAIL ") + message.replace("\n", " "))
        return 0 if ok else 2
    if "--remove" in argv:
        ok, message = disable()
        _say(("OK " if ok else "FAIL ") + message.replace("\n", " "))
        return 0 if ok else 2
    if "--status" in argv:
        enabled = is_enabled()
        _say(("ON " if enabled else "OFF ") + link_path())
        if enabled:
            _say("target: " + read_link_target())
        return 0 if enabled else 1

    Panel().run()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
