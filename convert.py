# -*- coding: utf-8 -*-
"""
convert.py —— 把「课程表.xlsx」转换成 clock.pyw 只读的 schedule.json。

只在课表变动时手动跑一次：
    双击「转换课表.exe」          —— 会弹框让你挑 xlsx
    python convert.py            —— 同上，源码版
    python convert.py "D:\\某处\\课程表.xlsx"

没给文件时的查找顺序：
    1) 命令行参数
    2) 本文件/本 exe 同目录下的「课程表.xlsx」
    3) 同目录下唯一的 .xlsx
    4) DEFAULT_XLSX（默认留空，你想固定路径就填）
    5) 弹文件选择框

只读取、不修改源 xlsx，也不做任何猜测：schedule.json 里的每一个字
都来自 xlsx 的实际单元格。运行本脚本需要 openpyxl（clock.pyw 不需要，
转完这一次就可以不再安装）。
"""

import json
import os
import re
import sys

try:
    import openpyxl
except ImportError:
    # 唯一预期内的依赖缺失，给人话就行，不用抛 traceback
    raise SystemExit(
        "缺少 openpyxl，读不了 xlsx。先装一下：\n"
        "    pip install openpyxl\n"
        "（只有本脚本需要它；clock.pyw 是纯标准库，转完这一次即可。）"
    )

# ------------------------------------------------------------------ 配置
# xlsx 位置：命令行给了就用命令行的，否则按上面的顺序自动找
# 想固定用某个路径就把它填在这里（例如 r"D:\课表\课程表.xlsx"），留空则跳过这步
DEFAULT_XLSX = ""

# 同目录下优先认这个文件名
PREFERRED_XLSX_NAME = "课程表.xlsx"


def _base_dir():
    """
    程序所在目录。

    打包成 exe 后 __file__ 指向 %TEMP%\\_MEIxxxx 那个临时解包目录，
    必须改用 exe 自己的位置，schedule.json 才会写到 exe 旁边——
    这样整个文件夹可以随便拷贝到别的电脑上继续用。
    """
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


BASE_DIR = _base_dir()
JSON_PATH = os.path.join(BASE_DIR, "schedule.json")

# 输出顺序固定为周一到周五
DAY_KEYS = ("MON", "TUE", "WED", "THR", "FRI")

# 表头认表：把各种写法都归一成 MON/TUE/.../TIME
HEADER_ALIAS = {
    "MON": "MON", "MONDAY": "MON", "周一": "MON", "星期一": "MON",
    "TUE": "TUE", "TUES": "TUE", "TUESDAY": "TUE", "周二": "TUE", "星期二": "TUE",
    "WED": "WED", "WEDS": "WED", "WEDNESDAY": "WED", "周三": "WED", "星期三": "WED",
    "THR": "THR", "THU": "THR", "THUR": "THR", "THURS": "THR", "THURSDAY": "THR",
    "周四": "THR", "星期四": "THR",
    "FRI": "FRI", "FRIDAY": "FRI", "周五": "FRI", "星期五": "FRI",
    "TIME": "TIME", "时间": "TIME", "时间段": "TIME", "上课时间": "TIME",
}

# G 列的时间区间：容错常见的全角冒号、各种连字符和「至/到」
TIME_RE = re.compile(
    r"(\d{1,2})\s*[:：]\s*(\d{1,2})\s*[~～\-—–－至到]\s*(\d{1,2})\s*[:：]\s*(\d{1,2})"
)


# ------------------------------------------------------------ 单元格读取
def build_merge_map(worksheet):
    """
    合并单元格的值只存在左上角，其它格子读出来是 None。
    这里把被合并区域覆盖到的每个格子都映射到左上角的值，
    这样 B3:F3 这种横跨一周的「课间」才能被后面的规则识别出来。
    """
    merge_map = {}
    for merged in worksheet.merged_cells.ranges:
        top_left = worksheet.cell(row=merged.min_row, column=merged.min_col).value
        if top_left is None:
            continue
        for row in range(merged.min_row, merged.max_row + 1):
            for col in range(merged.min_col, merged.max_col + 1):
                merge_map[(row, col)] = top_left
    return merge_map


def cell_text(worksheet, merge_map, row, col):
    """读一个格子的文本；被合并覆盖的格子回退到合并区左上角的值"""
    value = worksheet.cell(row=row, column=col).value
    if value is None:
        value = merge_map.get((row, col))
    if value is None:
        return ""
    return str(value).strip()


def merged_width(worksheet, row, col):
    """该格子所在合并区域横跨几列；没合并返回 1"""
    for merged in worksheet.merged_cells.ranges:
        if (merged.min_row <= row <= merged.max_row
                and merged.min_col <= col <= merged.max_col):
            return merged.max_col - merged.min_col + 1
    return 1


def parse_time_range(text):
    """'8:00-8:40' -> ('08:00', '08:40')；补零成 HH:MM，解析不出来返回 (None, None)"""
    if not text:
        return None, None
    match = TIME_RE.search(str(text))
    if not match:
        return None, None
    hour1, minute1, hour2, minute2 = (int(part) for part in match.groups())
    if not (0 <= hour1 < 24 and 0 <= minute1 < 60
            and 0 <= hour2 < 24 and 0 <= minute2 < 60):
        return None, None
    return "%02d:%02d" % (hour1, minute1), "%02d:%02d" % (hour2, minute2)


# ---------------------------------------------------------------- 定位表
def pick_worksheet(workbook):
    """取第一张有内容的表；Sheet2/Sheet3 这类空表直接跳过"""
    for worksheet in workbook.worksheets:
        for row in worksheet.iter_rows():
            for cell in row:
                if cell.value not in (None, ""):
                    return worksheet
    return None


def locate_columns(worksheet):
    """返回 ({'MON': 2, 'TUE': 3, ...}, 时间列号)。表头认不全就退回 B-F / G 的固定位置"""
    header = {}
    for col in range(1, worksheet.max_column + 1):
        raw = worksheet.cell(row=1, column=col).value
        if raw is None:
            continue
        key = "".join(str(raw).split()).upper()
        header[col] = HEADER_ALIAS.get(key, key)

    day_cols = {}
    for col in sorted(header):
        key = header[col]
        if key in DAY_KEYS and key not in day_cols:
            day_cols[key] = col
    if len(day_cols) < len(DAY_KEYS):
        day_cols = {key: 2 + index for index, key in enumerate(DAY_KEYS)}

    time_col = None
    for col in sorted(header):
        if header[col] == "TIME":
            time_col = col
            break
    if time_col is None:
        time_col = 7

    return day_cols, time_col


# ------------------------------------------------------------------ 转换
def convert(xlsx_path):
    workbook = openpyxl.load_workbook(xlsx_path, data_only=True)
    worksheet = pick_worksheet(workbook)
    if worksheet is None:
        raise SystemExit("xlsx 里没有任何有数据的表，无法转换。")

    merge_map = build_merge_map(worksheet)
    day_cols, time_col = locate_columns(worksheet)

    days = {key: [] for key in DAY_KEYS}
    slot_count = 0

    for row in range(2, worksheet.max_row + 1):
        start, end = parse_time_range(cell_text(worksheet, merge_map, row, time_col))
        if start is None:
            # G 列没有合法时间区间 -> 这行不是时间段，跳过
            continue

        # A 列 = 节次名 / 区间名
        name = cell_text(worksheet, merge_map, row, 1)

        # B-F 列 = 周一~周五各自的科目
        subjects = {key: cell_text(worksheet, merge_map, row, col)
                    for key, col in day_cols.items()}

        # 横向合并的标签（例如 B3:F3 的「课间」）表示的是这一行的区间名，
        # 不是某一天的科目，所以要把科目位清空、必要时提升为 name。
        merged_label = ""
        for key, col in day_cols.items():
            if subjects[key] and merged_width(worksheet, row, col) > 1:
                merged_label = subjects[key]
                break
        if merged_label:
            if not name:
                name = merged_label
            for key in subjects:
                subjects[key] = ""

        # 五天都要完整保留这个时间段（哪怕这天没课），
        # 时钟要靠这些区间判断「现在是第几节 / 是否课间」。
        for key in DAY_KEYS:
            days[key].append({
                "name": name,
                "start": start,
                "end": end,
                "subject": subjects.get(key, ""),
            })
        slot_count += 1

    return {
        "version": "1.0",
        "source": os.path.basename(xlsx_path),
        "days": days,
    }, slot_count


# ------------------------------------------------------------------ 入口
def _say(text):
    """打包成无控制台的窗口程序时 sys.stdout 是 None，print 会抛 AttributeError"""
    if sys.stdout is not None:
        print(text)


def find_local_xlsx():
    """在本程序所在目录里找课表：先认「课程表.xlsx」，再看是不是只有一个 .xlsx"""
    preferred = os.path.join(BASE_DIR, PREFERRED_XLSX_NAME)
    if os.path.isfile(preferred):
        return preferred

    try:
        names = os.listdir(BASE_DIR)
    except OSError:
        return ""

    found = [
        os.path.join(BASE_DIR, name)
        for name in names
        # ~$ 开头的是 Excel 打开文件时留下的临时锁文件
        if name.lower().endswith(".xlsx") and not name.startswith("~$")
    ]
    if len(found) == 1:
        return found[0]
    return ""


def choose_xlsx():
    """实在找不到就弹个文件选择框，让人自己挑（tkinter 是标准库，不用额外装东西）"""
    try:
        import tkinter
        from tkinter import filedialog
    except ImportError:
        return ""

    root = tkinter.Tk()
    root.withdraw()
    try:
        root.attributes("-topmost", True)
    except tkinter.TclError:
        pass
    path = filedialog.askopenfilename(
        title="选择课程表（.xlsx）",
        filetypes=[("Excel 工作簿", "*.xlsx"), ("所有文件", "*.*")],
    )
    root.destroy()
    return path or ""


def locate_xlsx():
    if len(sys.argv) > 1:
        return sys.argv[1]

    path = find_local_xlsx()
    if path:
        return path

    if DEFAULT_XLSX and os.path.isfile(DEFAULT_XLSX):
        return DEFAULT_XLSX

    _say("没在程序旁边找到课表，请在弹出的窗口里选一个 .xlsx …")
    return choose_xlsx()


def main():
    xlsx_path = locate_xlsx()

    if not xlsx_path:
        raise SystemExit("没有选择课表文件，已取消（schedule.json 未改动）。")

    if not os.path.isfile(xlsx_path):
        raise SystemExit("找不到课表文件：%s" % xlsx_path)

    schedule, slot_count = convert(xlsx_path)

    with open(JSON_PATH, "w", encoding="utf-8") as handle:
        json.dump(schedule, handle, ensure_ascii=False, indent=2)
        handle.write("\n")

    _say("已生成：%s" % JSON_PATH)
    _say("来源：%s" % os.path.basename(xlsx_path))
    _say("时间段：%d 个/天" % slot_count)
    for key in DAY_KEYS:
        subjects = [item["subject"] for item in schedule["days"][key] if item["subject"]]
        _say("  %s: %2d 个时间段，有科目 %d 个" % (key, len(schedule["days"][key]), len(subjects)))
    _say("")
    _say("转换完成，桌面时钟会在 10 秒内自动读取新课表。")


if __name__ == "__main__":
    main()
