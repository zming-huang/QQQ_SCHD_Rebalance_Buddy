# -*- coding: utf-8 -*-
"""浅色主题：颜色、字体与 ttk 样式。"""

import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk

FONT = "Microsoft YaHei UI"

BG = "#eef1f6"
CARD = "#ffffff"
CARD_ALT = "#f7f9fc"
BORDER = "#dde3ec"
TEXT = "#1b2130"
SUB = "#4f5a6b"
MUTED = "#8a94a6"

ACCENT = "#2f6fed"
ACCENT_DARK = "#1f56c4"
ACCENT_SOFT = "#e8efff"

QQQ = "#2f6fed"
SCHD = "#8b5cf6"

UP = "#d64545"        # 涨 → 红
DOWN = "#12855b"      # 跌 → 绿
FLAT = "#6b7280"

WARN = "#b87400"
WARN_SOFT = "#fdf3df"
OK = "#12855b"
OK_SOFT = "#e6f5ee"
DANGER = "#c0392b"
DANGER_SOFT = "#fdecea"


def font(size=10, weight="normal"):
    return (FONT, size, weight)


def tint(hex_color: str, ratio: float = 0.9) -> str:
    """把颜色与白色混合，ratio 越大越浅。"""
    hex_color = hex_color.lstrip("#")
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (0, 2, 4))
    r = int(r + (255 - r) * ratio)
    g = int(g + (255 - g) * ratio)
    b = int(b + (255 - b) * ratio)
    return f"#{r:02x}{g:02x}{b:02x}"


def setup(root: tk.Misc) -> None:
    """配置 ttk 样式（Treeview / Combobox / Spinbox 等）。"""
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    style.configure("Treeview",
                    background=CARD, fieldbackground=CARD, foreground=TEXT,
                    rowheight=30, borderwidth=0, font=font(10))
    style.configure("Treeview.Heading",
                    background=CARD_ALT, foreground=SUB,
                    font=font(9, "bold"), relief="flat", borderwidth=0,
                    padding=(6, 7))
    style.map("Treeview.Heading", background=[("active", CARD_ALT)])
    style.map("Treeview",
              background=[("selected", ACCENT_SOFT)],
              foreground=[("selected", TEXT)])
    style.layout("Treeview", [("Treeview.treearea", {"sticky": "nswe"})])

    style.configure("TCombobox",
                    fieldbackground=CARD, background=CARD, foreground=TEXT,
                    bordercolor=BORDER, lightcolor=BORDER, darkcolor=BORDER,
                    arrowcolor=SUB, padding=(6, 4), font=font(10))
    style.map("TCombobox",
              fieldbackground=[("readonly", CARD)],
              foreground=[("readonly", TEXT)],
              bordercolor=[("focus", ACCENT)])

    style.configure("TSpinbox", fieldbackground=CARD, foreground=TEXT,
                    bordercolor=BORDER, arrowcolor=SUB, padding=(6, 4),
                    font=font(10))

    style.configure("TCheckbutton", background=CARD, foreground=TEXT,
                    font=font(10))
    style.map("TCheckbutton", background=[("active", CARD)])

    style.configure("Vertical.TScrollbar", background="#c9d1de",
                    troughcolor=BG, bordercolor=BG, arrowcolor=SUB,
                    relief="flat", width=10)
