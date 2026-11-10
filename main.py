#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""QQQ x SCHD 再平衡管家 —— 程序入口。

双击 launch.bat（或本文件）即可启动窗口界面。
"""

import ctypes
import os
import sys
import traceback
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))


def _enable_dpi_awareness() -> None:
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except (AttributeError, OSError):
            pass


def _log_error(text: str) -> Path:
    log = BASE_DIR / "data" / "error.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("a", encoding="utf-8") as f:
        f.write(f"\n[{datetime.now():%Y-%m-%d %H:%M:%S}]\n{text}\n")
    return log


def main() -> int:
    _enable_dpi_awareness()
    try:
        from ui_app import run
        run()
        return 0
    except Exception:  # noqa: BLE001 - GUI 程序兜底，确保错误可见
        tb = traceback.format_exc()
        log = _log_error(tb)
        try:
            import tkinter as tk
            from tkinter import messagebox
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror(
                "程序启动失败",
                f"错误信息已写入：\n{log}\n\n{tb.splitlines()[-1]}")
            root.destroy()
        except Exception:  # noqa: BLE001
            print(tb)
        return 1


if __name__ == "__main__":
    sys.exit(main())
