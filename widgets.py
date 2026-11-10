# -*- coding: utf-8 -*-
"""可复用界面组件：卡片、指标卡、迷你走势、配置条、折线图、按钮。"""

import tkinter as tk
from datetime import datetime
from tkinter import font as tkfont

import theme as T


# ---------------------------------------------------------------------------
# 格式化
# ---------------------------------------------------------------------------

def money(v, digits: int = 2) -> str:
    if v is None:
        return "--"
    return f"${v:,.{digits}f}"


def pct(v, digits: int = 2, signed: bool = False) -> str:
    if v is None:
        return "--"
    sign = "+" if (signed and v > 0) else ""
    return f"{sign}{v * 100:.{digits}f}%"


def shares(v) -> str:
    if v is None:
        return "--"
    return f"{v:,.4f}".rstrip("0").rstrip(".") if abs(v) < 1000 else f"{v:,.2f}"


def signed_shares(v: float) -> str:
    return f"{v:+,.0f}"


# ---------------------------------------------------------------------------
# 基础组件
# ---------------------------------------------------------------------------

def round_rect(canvas: tk.Canvas, x1, y1, x2, y2, r=8, **kwargs):
    r = max(0, min(r, (x2 - x1) / 2, (y2 - y1) / 2))
    points = [
        x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
        x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2,
        x1, y2, x1, y2 - r, x1, y1 + r, x1, y1,
    ]
    return canvas.create_polygon(points, smooth=True, **kwargs)


class Card(tk.Frame):
    """带标题的白色卡片。内容放入 self.content。"""

    def __init__(self, master, title=None, subtitle=None, pad=14, **kw):
        super().__init__(master, bg=T.CARD, highlightbackground=T.BORDER,
                         highlightthickness=1, bd=0, **kw)
        self.body = tk.Frame(self, bg=T.CARD)
        self.body.pack(fill="both", expand=True, padx=pad, pady=pad)
        self.header = None
        if title:
            self.header = tk.Frame(self.body, bg=T.CARD)
            self.header.pack(fill="x", pady=(0, 10))
            tk.Label(self.header, text=title, bg=T.CARD, fg=T.TEXT,
                     font=T.font(10, "bold")).pack(side="left")
            if subtitle:
                tk.Label(self.header, text=subtitle, bg=T.CARD, fg=T.MUTED,
                         font=T.font(9)).pack(side="right")
        self.content = tk.Frame(self.body, bg=T.CARD)
        self.content.pack(fill="both", expand=True)


class Badge(tk.Label):
    def __init__(self, master, text="", fg=T.SUB, bg=T.CARD_ALT, **kw):
        super().__init__(master, text=text, fg=fg, bg=bg, font=T.font(9, "bold"),
                         padx=8, pady=2, **kw)

    def set(self, text, fg=T.SUB, bg=T.CARD_ALT):
        self.config(text=text, fg=fg, bg=bg)


class Sparkline(tk.Canvas):
    def __init__(self, master, height=34, color=T.ACCENT, **kw):
        super().__init__(master, height=height, bg=T.CARD,
                         highlightthickness=0, bd=0, **kw)
        self._points = []
        self._color = color
        self.bind("<Configure>", lambda e: self.redraw())

    def set_points(self, points, color=None):
        self._points = [p for p in (points or []) if p is not None]
        if color:
            self._color = color
        self.redraw()

    def redraw(self):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        pts = self._points
        if len(pts) < 2 or w < 24 or h < 10:
            return
        lo, hi = min(pts), max(pts)
        if hi - lo < 1e-9:
            hi = lo + 1e-9
        pad = 3
        coords = []
        for i, v in enumerate(pts):
            x = pad + (w - 2 * pad) * i / (len(pts) - 1)
            y = h - pad - (h - 2 * pad) * (v - lo) / (hi - lo)
            coords.append((x, y))
        area = coords + [(coords[-1][0], h), (coords[0][0], h)]
        self.create_polygon(area, fill=T.tint(self._color, 0.88), outline="")
        self.create_line(coords, fill=self._color, width=2, smooth=True)


class StatCard(tk.Frame):
    """价格 / 市值 指标卡。"""

    def __init__(self, master, title, subtitle="", accent=T.ACCENT, **kw):
        super().__init__(master, bg=T.CARD, highlightbackground=T.BORDER,
                         highlightthickness=1, bd=0, **kw)
        inner = tk.Frame(self, bg=T.CARD)
        inner.pack(fill="both", expand=True, padx=14, pady=12)

        top = tk.Frame(inner, bg=T.CARD)
        top.pack(fill="x")
        tk.Label(top, text=title, bg=T.CARD, fg=T.SUB,
                 font=T.font(10, "bold")).pack(side="left")
        self.sub_lbl = tk.Label(top, text=subtitle, bg=T.CARD, fg=T.MUTED,
                                font=T.font(9))
        self.sub_lbl.pack(side="right")

        self.value_lbl = tk.Label(inner, text="--", bg=T.CARD, fg=T.TEXT,
                                  font=(T.FONT, 19, "bold"), anchor="w")
        self.value_lbl.pack(fill="x", pady=(6, 0))

        self.delta_lbl = tk.Label(inner, text="等待刷新", bg=T.CARD, fg=T.MUTED,
                                  font=T.font(9), anchor="w")
        self.delta_lbl.pack(fill="x")

        self.spark = Sparkline(inner, height=32, color=accent)
        self.spark.pack(fill="x", pady=(6, 0))

    def set(self, value, delta=None, delta_color=T.MUTED, sub=None, spark=None):
        self.value_lbl.config(text=value)
        if delta is not None:
            self.delta_lbl.config(text=delta, fg=delta_color)
        if sub is not None:
            self.sub_lbl.config(text=sub)
        if spark is not None:
            self.spark.set_points(spark)


class AllocationBar(tk.Canvas):
    """QQQ / SCHD 配置条，带目标位置刻度。"""

    def __init__(self, master, height=62, **kw):
        super().__init__(master, height=height, bg=T.CARD,
                         highlightthickness=0, bd=0, **kw)
        self._ratio = 0.5
        self._target = 0.5
        self._labels = ("QQQ", "SCHD")
        self.bind("<Configure>", lambda e: self.redraw())

    def set(self, qqq_ratio: float, target: float = 0.5):
        self._ratio = max(0.0, min(1.0, qqq_ratio))
        self._target = target
        self.redraw()

    def redraw(self):
        self.delete("all")
        w = self.winfo_width()
        if w < 40:
            return
        x0, x1 = 2, w - 2
        y0, y1 = 12, 38
        split = x0 + (x1 - x0) * self._ratio

        round_rect(self, x0, y0, x1, y1, 12, fill="#f0f3f9", outline="")
        if split - x0 > 1:
            round_rect(self, x0, y0, max(split, x0 + 2), y1, 12,
                       fill=T.QQQ, outline="")
        if x1 - split > 1:
            round_rect(self, min(split, x1 - 2), y0, x1, y1, 12,
                       fill=T.SCHD, outline="")

        f = tkfont.Font(family=T.FONT, size=9, weight="bold")
        self._label(x0 + 12, (y0 + y1) / 2, split - x0 - 20,
                    f"QQQ {self._ratio*100:.1f}%", f)
        self._label(split + 12, (y0 + y1) / 2, x1 - split - 20,
                    f"SCHD {(1-self._ratio)*100:.1f}%", f)

        tx = x0 + (x1 - x0) * self._target
        self.create_line(tx, y0 - 7, tx, y1 + 7, fill=T.TEXT, width=2,
                         dash=(3, 2))
        self.create_text(tx, y1 + 17, text=f"目标 {self._target*100:.0f}%",
                         fill=T.SUB, font=T.font(8))

    def _label(self, x, y, maxw, text, f):
        if maxw > f.measure(text) + 8:
            self.create_text(x, y, text=text, anchor="w", fill="#ffffff", font=f)


class LineChart(tk.Canvas):
    """多序列折线图（数值以"初始=1"的倍数表示）。"""

    def __init__(self, master, height=300, **kw):
        super().__init__(master, height=height, bg=T.CARD,
                         highlightthickness=0, bd=0, **kw)
        self.series = []
        self.bind("<Configure>", lambda e: self.redraw())

    def set_series(self, series):
        """series: [{'name': str, 'color': str, 'points': [(datetime, float)]}]"""
        self.series = series or []
        self.redraw()

    def redraw(self):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if not self.series or w < 100 or h < 80:
            return
        pad_l, pad_r, pad_t, pad_b = 54, 16, 32, 26

        all_pts = [p for s in self.series for p in s["points"]]
        if not all_pts:
            return
        xs = [p[0].timestamp() for p in all_pts]
        ys = [p[1] for p in all_pts]
        xmin, xmax = min(xs), max(xs)
        if xmax - xmin <= 0:
            return
        ymin, ymax = min(ys), max(ys)
        ymin = min(ymin, 1.0)
        span = max(ymax - ymin, 1e-6)
        ymin -= span * 0.06
        ymax += span * 0.06

        def sx(ts):
            return pad_l + (w - pad_l - pad_r) * (ts - xmin) / (xmax - xmin)

        def sy(v):
            return h - pad_b - (h - pad_t - pad_b) * (v - ymin) / (ymax - ymin)

        # 网格与 Y 轴刻度
        for i in range(5):
            v = ymin + (ymax - ymin) * i / 4
            y = sy(v)
            self.create_line(pad_l, y, w - pad_r, y, fill="#eef1f7")
            self.create_text(pad_l - 8, y, text=f"{v:.1f}x", anchor="e",
                             fill=T.MUTED, font=T.font(8))

        # 基准线 1.0
        if ymin < 1.0 < ymax:
            self.create_line(pad_l, sy(1.0), w - pad_r, sy(1.0),
                             fill="#c9d1de", dash=(4, 3))

        # X 轴刻度
        first = datetime.fromtimestamp(xmin)
        last = datetime.fromtimestamp(xmax)
        span_years = (last - first).days / 365.25
        tick_fmt = "%Y" if span_years >= 2 else "%y/%m"
        n_ticks = 6
        for i in range(n_ticks):
            ts = xmin + (xmax - xmin) * i / (n_ticks - 1)
            dt = datetime.fromtimestamp(ts)
            self.create_text(sx(ts), h - pad_b + 12,
                             text=dt.strftime(tick_fmt),
                             fill=T.MUTED, font=T.font(8))

        # 折线
        for s in self.series:
            pts = s["points"]
            if len(pts) < 2:
                continue
            coords = []
            for dt, v in pts:
                coords.extend([sx(dt.timestamp()), sy(v)])
            self.create_line(coords, fill=s["color"], width=2,
                             smooth=len(pts) > 60)

        # 图例
        lx = pad_l + 4
        for s in self.series:
            self.create_line(lx, 14, lx + 18, 14, fill=s["color"], width=3)
            self.create_text(lx + 24, 14, text=s["name"], anchor="w",
                             fill=T.SUB, font=T.font(8))
            lx += 26 + tkfont.Font(family=T.FONT, size=8).measure(s["name"]) + 14


# ---------------------------------------------------------------------------
# 按钮
# ---------------------------------------------------------------------------

def button(master, text, command=None, kind="ghost", width=None, padx=12, pady=6):
    palette = {
        "primary": (T.ACCENT, "#ffffff", T.ACCENT_DARK, T.ACCENT),
        "ghost": (T.CARD, T.SUB, T.CARD_ALT, T.BORDER),
        "soft": (T.ACCENT_SOFT, T.ACCENT, "#dbe6ff", T.ACCENT_SOFT),
        "warn": (T.WARN_SOFT, T.WARN, "#f7e7c4", T.WARN_SOFT),
        "danger": (T.CARD, T.DANGER, T.DANGER_SOFT, T.BORDER),
    }
    bg, fg, hover, border = palette.get(kind, palette["ghost"])
    btn = tk.Button(master, text=text, command=command, bg=bg, fg=fg,
                    activebackground=hover, activeforeground=fg,
                    font=T.font(9, "bold"), bd=0, relief="flat",
                    highlightthickness=1, highlightbackground=border,
                    highlightcolor=border, padx=padx, pady=pady,
                    cursor="hand2")
    if width:
        btn.config(width=width)

    def on_enter(_):
        btn.config(bg=hover)

    def on_leave(_):
        btn.config(bg=bg)

    btn.bind("<Enter>", on_enter)
    btn.bind("<Leave>", on_leave)
    return btn


def entry(master, textvariable=None, width=16, justify="right"):
    e = tk.Entry(master, textvariable=textvariable, width=width, justify=justify,
                 bg=T.CARD, fg=T.TEXT, font=T.font(10), bd=0, relief="flat",
                 highlightthickness=1, highlightbackground=T.BORDER,
                 highlightcolor=T.ACCENT, insertbackground=T.TEXT)
    e.config(relief="flat", highlightthickness=1)
    return e


def hint(master, text, fg=T.MUTED, bg=T.CARD, size=9, **kw):
    return tk.Label(master, text=text, bg=bg, fg=fg, font=T.font(size),
                    justify="left", **kw)


def center(win, w, h):
    win.update_idletasks()
    sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
    x = max(0, (sw - w) // 2)
    y = max(0, int((sh - h) * 0.42))
    win.geometry(f"{w}x{h}+{x}+{y}")
