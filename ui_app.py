# -*- coding: utf-8 -*-
"""主窗口：侧栏用户切换 + 仪表盘 + 持仓 + 回测 + 记录 + 设置 + 策略说明。"""

import csv
import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from datetime import date, datetime, timedelta
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

import reminders
import strategy
import theme as T
import widgets as W
from config import (APP_TITLE, APP_VERSION, DATA_DIR, TICKER_NAMES, TICKERS,
                    BASE_DIR)
from prices import PriceService, fetch_history
from store import Store

NAV = [
    ("dashboard", "仪表盘"),
    ("holdings", "持仓与参数"),
    ("backtest", "策略回测"),
    ("history", "再平衡记录"),
    ("settings", "提醒与设置"),
    ("about", "策略原理"),
]

PAGE_META = {
    "dashboard": ("仪表盘", "实时价差与调仓建议一览"),
    "holdings": ("持仓与参数", "股数、目标比例、阈值与周期"),
    "backtest": ("策略回测", "月度再平衡 vs 买入持有（历史数据）"),
    "history": ("再平衡记录", "每次调仓的时间与规模"),
    "settings": ("提醒与设置", "自动刷新、每日提醒、开机启动"),
    "about": ("策略原理", "Cover 增长最优 / 通用投资组合"),
}

RANGE_LABEL = {"3y": "近 3 年", "5y": "近 5 年", "10y": "近 10 年", "max": "最长"}


class App(tk.Tk):
    def __init__(self, store: Store):
        super().__init__()
        self.store = store
        self.prices = PriceService()
        self.manual_prices: dict = {}
        self.q: queue.Queue = queue.Queue()
        self._fetching = False
        self._backtesting = False
        self._last_attempt = None
        self._last_quote_warn = 0.0
        self.current_page = "dashboard"

        self.title(f"{APP_TITLE}  v{APP_VERSION}")
        self.configure(bg=T.BG)
        self.minsize(1040, 700)
        self._restore_geometry()
        T.setup(self)

        self._build()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self.after(120, self._pump)
        self.after(400, lambda: self.refresh_prices(silent=True))
        self._refresh_profile_box()
        self._select_page("dashboard")

    # ------------------------------------------------------------------
    # 窗口
    # ------------------------------------------------------------------
    def _restore_geometry(self):
        geo = self.store.settings.get("window_geometry") or ""
        if geo:
            try:
                self.geometry(geo)
                return
            except tk.TclError:
                pass
        W.center(self, 1180, 800)

    def _build(self):
        self.sidebar = tk.Frame(self, bg=T.CARD, width=216)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        main = tk.Frame(self, bg=T.BG)
        main.pack(side="left", fill="both", expand=True)

        self._build_sidebar()

        header = tk.Frame(main, bg=T.BG)
        header.pack(fill="x", padx=18, pady=(16, 8))
        left = tk.Frame(header, bg=T.BG)
        left.pack(side="left")
        self.page_title = tk.Label(left, text="", bg=T.BG, fg=T.TEXT,
                                   font=T.font(14, "bold"))
        self.page_title.pack(anchor="w")
        self.page_sub = tk.Label(left, text="", bg=T.BG, fg=T.MUTED,
                                 font=T.font(9))
        self.page_sub.pack(anchor="w")

        right = tk.Frame(header, bg=T.BG)
        right.pack(side="right")
        self.status_lbl = tk.Label(right, text="正在获取最新价格…", bg=T.BG,
                                   fg=T.MUTED, font=T.font(9))
        self.status_lbl.pack(side="left", padx=(0, 10))
        W.button(right, "刷新价格", lambda: self.refresh_prices(),
                 kind="ghost").pack(side="left", padx=(0, 8))
        W.button(right, "手动价格", self._manual_price_dialog,
                 kind="soft").pack(side="left")

        self.body = tk.Frame(main, bg=T.BG)
        self.body.pack(fill="both", expand=True, padx=18, pady=(0, 14))
        self.body.grid_rowconfigure(0, weight=1)
        self.body.grid_columnconfigure(0, weight=1)
        self._build_pages()

    def _build_sidebar(self):
        brand = tk.Frame(self.sidebar, bg=T.CARD)
        brand.pack(fill="x", padx=18, pady=(20, 14))
        tk.Label(brand, text="REBALANCE BUDDY", bg=T.CARD, fg=T.ACCENT,
                 font=(T.FONT, 8, "bold")).pack(anchor="w")
        tk.Label(brand, text="QQQ × SCHD 再平衡管家", bg=T.CARD, fg=T.TEXT,
                 font=T.font(10, "bold"), wraplength=178,
                 justify="left").pack(anchor="w", pady=(2, 0))

        tk.Frame(self.sidebar, bg=T.BORDER, height=1).pack(fill="x", padx=18)

        box = tk.Frame(self.sidebar, bg=T.CARD)
        box.pack(fill="x", padx=18, pady=14)
        tk.Label(box, text="当前用户", bg=T.CARD, fg=T.MUTED,
                 font=T.font(8)).pack(anchor="w")
        self.profile_var = tk.StringVar()
        self.profile_box = ttk.Combobox(box, textvariable=self.profile_var,
                                        state="readonly", font=T.font(10))
        self.profile_box.pack(fill="x", pady=(4, 6))
        self.profile_box.bind("<<ComboboxSelected>>", self._on_profile_switch)

        row = tk.Frame(box, bg=T.CARD)
        row.pack(fill="x")
        for text, cmd in (("新建", self._new_profile),
                          ("改名", self._rename_profile),
                          ("删除", self._delete_profile)):
            btn = tk.Button(row, text=text, command=cmd, bg=T.CARD_ALT, fg=T.SUB,
                            font=T.font(8), bd=0, relief="flat", padx=6, pady=3,
                            cursor="hand2", activebackground=T.ACCENT_SOFT,
                            highlightthickness=0)
            btn.pack(side="left", padx=(0, 5))

        nav = tk.Frame(self.sidebar, bg=T.CARD)
        nav.pack(fill="x", padx=10, pady=(8, 0))
        self.nav_btns = {}
        for key, label in NAV:
            btn = tk.Button(nav, text=label, anchor="w", bg=T.CARD, fg=T.SUB,
                            font=T.font(10), bd=0, relief="flat",
                            padx=14, pady=9, cursor="hand2",
                            activebackground=T.ACCENT_SOFT,
                            activeforeground=T.ACCENT)
            btn.pack(fill="x", pady=1)
            btn.config(command=lambda k=key: self._select_page(k))
            self.nav_btns[key] = btn

        foot = tk.Frame(self.sidebar, bg=T.CARD)
        foot.pack(side="bottom", fill="x", padx=18, pady=14)
        tk.Label(foot, text="数据源：Yahoo Finance / 新浪财经", bg=T.CARD,
                 fg=T.MUTED, font=T.font(8)).pack(anchor="w")
        tk.Label(foot, text=f"v{APP_VERSION} · 仅供个人参考", bg=T.CARD,
                 fg=T.MUTED, font=T.font(8)).pack(anchor="w", pady=(2, 0))

    def _build_pages(self):
        self.pages = {}
        builders = {
            "dashboard": self._page_dashboard,
            "holdings": self._page_holdings,
            "backtest": self._page_backtest,
            "history": self._page_history,
            "settings": self._page_settings,
            "about": self._page_about,
        }
        for key, fn in builders.items():
            frame = tk.Frame(self.body, bg=T.BG)
            frame.grid(row=0, column=0, sticky="nsew")
            self.pages[key] = frame
            fn(frame)

    # ------------------------------------------------------------------
    # 仪表盘
    # ------------------------------------------------------------------
    def _page_dashboard(self, page):
        page.grid_columnconfigure(0, weight=1)
        page.grid_rowconfigure(2, weight=1)

        cards = tk.Frame(page, bg=T.BG)
        cards.grid(row=0, column=0, sticky="ew")
        for i in range(3):
            cards.grid_columnconfigure(i, weight=1, uniform="stat")

        self.card_qqq = W.StatCard(cards, "QQQ", TICKER_NAMES["QQQ"], accent=T.QQQ)
        self.card_qqq.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        self.card_schd = W.StatCard(cards, "SCHD", TICKER_NAMES["SCHD"], accent=T.SCHD)
        self.card_schd.grid(row=0, column=1, sticky="nsew", padx=(0, 10))
        self.card_total = W.StatCard(cards, "组合总市值", "QQQ + SCHD", accent=T.ACCENT)
        self.card_total.grid(row=0, column=2, sticky="nsew")

        alloc = W.Card(page, "目标配置 vs 当前配置", "虚线为 50:50 目标")
        alloc.grid(row=1, column=0, sticky="ew", pady=10)
        self.alloc_bar = W.AllocationBar(alloc.content, height=64)
        self.alloc_bar.pack(fill="x")

        meta = tk.Frame(alloc.content, bg=T.CARD)
        meta.pack(fill="x", pady=(8, 0))
        for i in range(4):
            meta.grid_columnconfigure(i, weight=1, uniform="m")
        self.meta_dev = self._meta_block(meta, 0, "当前偏差")
        self.meta_due = self._meta_block(meta, 1, "距下次定期再平衡")
        self.meta_last = self._meta_block(meta, 2, "上次再平衡")
        self.meta_state = self._meta_block(meta, 3, "状态")

        advice = W.Card(page, "建议操作", "按整数股取整")
        advice.grid(row=2, column=0, sticky="nsew")

        cols = ("ticker", "price", "shares", "target", "action", "trade", "amount")
        self.tree = ttk.Treeview(advice.content, columns=cols, show="headings",
                                 height=4)
        heads = ("代码", "现价", "当前股数", "目标股数", "操作", "交易股数", "金额")
        widths = (90, 110, 120, 120, 90, 100, 130)
        for c, h, wd in zip(cols, heads, widths):
            self.tree.heading(c, text=h)
            self.tree.column(c, width=wd, anchor="center" if c != "ticker" else "w",
                             stretch=True)
        self.tree.tag_configure("buy", foreground=T.UP)
        self.tree.tag_configure("sell", foreground=T.DOWN)
        self.tree.tag_configure("hold", foreground=T.MUTED)
        self.tree.pack(fill="both", expand=True, pady=(2, 8))

        bar = tk.Frame(advice.content, bg=T.CARD)
        bar.pack(fill="x")
        self.advice_hint = W.hint(bar, "", fg=T.SUB)
        self.advice_hint.pack(side="left")
        W.button(bar, "记录本次再平衡", self._record_rebalance,
                 kind="primary").pack(side="right")
        W.button(bar, "编辑持仓", lambda: self._select_page("holdings"),
                 kind="ghost").pack(side="right", padx=(0, 8))

    def _meta_block(self, master, col, title):
        box = tk.Frame(master, bg=T.CARD)
        box.grid(row=0, column=col, sticky="w")
        tk.Label(box, text=title, bg=T.CARD, fg=T.MUTED,
                 font=T.font(8)).pack(anchor="w")
        value = tk.Label(box, text="--", bg=T.CARD, fg=T.TEXT,
                         font=T.font(12, "bold"))
        value.pack(anchor="w", pady=(2, 0))
        return value

    # ------------------------------------------------------------------
    # 持仓与参数
    # ------------------------------------------------------------------
    def _page_holdings(self, page):
        page.grid_columnconfigure(0, weight=1)
        page.grid_columnconfigure(1, weight=1)
        page.grid_rowconfigure(0, weight=1)

        left = W.Card(page, "持仓")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        self.var_qqq = tk.StringVar()
        self.var_schd = tk.StringVar()
        self._form_row(left.content, "QQQ 股数", self.var_qqq,
                       f"现价 {TICKER_NAMES['QQQ']}")
        self._form_row(left.content, "SCHD 股数", self.var_schd,
                       f"现价 {TICKER_NAMES['SCHD']}")
        self.lbl_position_value = W.hint(left.content, "组合总市值 --", fg=T.SUB)
        self.lbl_position_value.pack(anchor="w", pady=(12, 4))

        tk.Frame(left.content, bg=T.BORDER, height=1).pack(fill="x", pady=12)
        tk.Label(left.content, text="上次再平衡日期", bg=T.CARD, fg=T.MUTED,
                 font=T.font(9)).pack(anchor="w")
        row = tk.Frame(left.content, bg=T.CARD)
        row.pack(fill="x", pady=(4, 0))
        self.lbl_last_rebalance = tk.Label(row, text="未记录", bg=T.CARD,
                                           fg=T.TEXT, font=T.font(11, "bold"))
        self.lbl_last_rebalance.pack(side="left")
        W.button(row, "设为今天", self._mark_today, kind="ghost",
                 padx=8, pady=3).pack(side="right")

        right = W.Card(page, "再平衡参数")
        right.grid(row=0, column=1, sticky="nsew")
        self.var_ratio = tk.StringVar()
        self.var_threshold = tk.StringVar()
        self.var_interval = tk.StringVar()
        self._form_row(right.content, "QQQ 目标占比 (%)", self.var_ratio,
                       "默认 50")
        self._form_row(right.content, "偏差阈值 (%)", self.var_threshold,
                       "超过则提醒，默认 5")
        self._form_row(right.content, "定期再平衡间隔 (天)", self.var_interval,
                       "默认 31（约每月）")
        W.hint(right.content,
               "说明：两资产同时下跌时仍会亏损；\n"
               "频率过高会被手续费与税侵蚀，月度或阈值触发更实际。",
               fg=T.MUTED).pack(anchor="w", pady=(14, 0))

        bar = tk.Frame(page, bg=T.BG)
        bar.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(12, 0))
        self.holdings_hint = W.hint(bar, "", fg=T.MUTED, bg=T.BG)
        self.holdings_hint.pack(side="left")
        W.button(bar, "保存并重新计算", self._save_holdings,
                 kind="primary", padx=16, pady=8).pack(side="right")

    def _form_row(self, master, label, var, tip=""):
        box = tk.Frame(master, bg=T.CARD)
        box.pack(fill="x", pady=(0, 12))
        head = tk.Frame(box, bg=T.CARD)
        head.pack(fill="x")
        tk.Label(head, text=label, bg=T.CARD, fg=T.SUB,
                 font=T.font(9)).pack(side="left")
        if tip:
            tk.Label(head, text=tip, bg=T.CARD, fg=T.MUTED,
                     font=T.font(8)).pack(side="right")
        e = W.entry(box, var, width=18)
        e.pack(fill="x", pady=(4, 0), ipady=6)
        return e

    # ------------------------------------------------------------------
    # 回测
    # ------------------------------------------------------------------
    def _page_backtest(self, page):
        page.grid_columnconfigure(0, weight=1)
        page.grid_rowconfigure(0, weight=1)

        card = W.Card(page, "月度再平衡 vs 买入持有", "初始净值 = 1.00")
        card.grid(row=0, column=0, sticky="nsew")

        ctrl = tk.Frame(card.content, bg=T.CARD)
        ctrl.pack(fill="x", pady=(0, 8))
        tk.Label(ctrl, text="回测区间", bg=T.CARD, fg=T.SUB,
                 font=T.font(9)).pack(side="left")
        self.var_range = tk.StringVar(
            value=RANGE_LABEL.get(self.store.settings.get("backtest_range", "5y"),
                                  "近 5 年"))
        combo = ttk.Combobox(ctrl, textvariable=self.var_range, state="readonly",
                             values=list(RANGE_LABEL.values()), width=10,
                             font=T.font(9))
        combo.pack(side="left", padx=(8, 12))
        self.btn_backtest = W.button(ctrl, "运行回测", self._run_backtest,
                                    kind="primary", padx=14)
        self.btn_backtest.pack(side="left")
        self.lbl_bt_status = W.hint(ctrl, "点击运行，拉取 QQQ / SCHD 历史月度价格",
                                    fg=T.MUTED)
        self.lbl_bt_status.pack(side="left", padx=12)

        self.chart = W.LineChart(card.content, height=300)
        self.chart.pack(fill="both", expand=True, pady=(4, 10))

        mcols = ("name", "total", "cagr", "vol", "dd", "final")
        self.bt_tree = ttk.Treeview(card.content, columns=mcols, show="headings",
                                    height=4)
        for c, h, wd in zip(mcols,
                            ("策略", "累计收益", "年化收益", "年化波动", "最大回撤", "期末倍数"),
                            (200, 120, 120, 120, 120, 120)):
            self.bt_tree.heading(c, text=h)
            self.bt_tree.column(c, width=wd, anchor="center" if c != "name" else "w")
        self.bt_tree.pack(fill="x")

        self.lbl_bt_conclusion = W.hint(card.content, "", fg=T.SUB)
        self.lbl_bt_conclusion.pack(anchor="w", pady=(10, 0))

    # ------------------------------------------------------------------
    # 记录
    # ------------------------------------------------------------------
    def _page_history(self, page):
        page.grid_columnconfigure(0, weight=1)
        page.grid_rowconfigure(0, weight=1)

        card = W.Card(page, "再平衡记录")
        card.grid(row=0, column=0, sticky="nsew")

        bar = tk.Frame(card.content, bg=T.CARD)
        bar.pack(fill="x", pady=(0, 8))
        W.button(bar, "导出 CSV", self._export_history, kind="ghost").pack(side="left")
        W.button(bar, "清空本用户记录", self._clear_history, kind="danger").pack(
            side="left", padx=8)
        self.lbl_history_count = W.hint(bar, "", fg=T.MUTED)
        self.lbl_history_count.pack(side="right")

        cols = ("date", "type", "qqq", "schd", "value", "ratio", "note")
        self.hist_tree = ttk.Treeview(card.content, columns=cols,
                                      show="headings", height=10)
        heads = ("日期", "类型", "QQQ 股数", "SCHD 股数", "总市值", "QQQ 占比", "备注")
        widths = (110, 90, 110, 110, 120, 100, 220)
        for c, h, wd in zip(cols, heads, widths):
            self.hist_tree.heading(c, text=h)
            self.hist_tree.column(c, width=wd,
                                  anchor="w" if c == "note" else "center")
        self.hist_tree.pack(fill="both", expand=True)

    # ------------------------------------------------------------------
    # 设置
    # ------------------------------------------------------------------
    def _page_settings(self, page):
        page.grid_columnconfigure(0, weight=1)
        page.grid_columnconfigure(1, weight=1)
        page.grid_rowconfigure(0, weight=1)

        left = W.Card(page, "提醒")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

        self.var_remind_on = tk.BooleanVar()
        ttk.Checkbutton(left.content, text="启用定期提醒（窗口弹窗 + 提示音）",
                        variable=self.var_remind_on).pack(anchor="w", pady=(0, 12))

        row = tk.Frame(left.content, bg=T.CARD)
        row.pack(fill="x", pady=(0, 12))
        tk.Label(row, text="每日提醒时间", bg=T.CARD, fg=T.SUB,
                 font=T.font(9)).pack(side="left")
        self.var_remind_time = tk.StringVar()
        e = W.entry(row, self.var_remind_time, width=8, justify="center")
        e.pack(side="right", ipady=5)
        W.hint(left.content, "格式 24 小时制，例如 09:30；当天此时间之后才会弹提醒。",
               fg=T.MUTED).pack(anchor="w")

        tk.Frame(left.content, bg=T.BORDER, height=1).pack(fill="x", pady=12)

        row2 = tk.Frame(left.content, bg=T.CARD)
        row2.pack(fill="x", pady=(0, 12))
        tk.Label(row2, text="自动刷新价格间隔（分钟）", bg=T.CARD, fg=T.SUB,
                 font=T.font(9)).pack(side="left")
        self.var_refresh = tk.StringVar()
        sp = ttk.Spinbox(row2, from_=1, to=240, width=6, textvariable=self.var_refresh,
                         font=T.font(9))
        sp.pack(side="right")
        W.hint(left.content, "程序运行期间按此间隔自动拉取最新价格。",
               fg=T.MUTED).pack(anchor="w")

        tk.Frame(left.content, bg=T.BORDER, height=1).pack(fill="x", pady=12)
        W.button(left.content, "立即检查一次提醒", self._check_reminder_now,
                 kind="soft").pack(anchor="w")

        right = W.Card(page, "数据与启动")
        right.grid(row=0, column=1, sticky="nsew")

        self.var_autostart = tk.BooleanVar()
        ttk.Checkbutton(right.content, text="开机自动启动（最小化到后台提醒）",
                        variable=self.var_autostart).pack(anchor="w", pady=(0, 12))

        W.hint(right.content, "数据文件", fg=T.MUTED).pack(anchor="w")
        W.hint(right.content, str(DATA_DIR / "state.json"), fg=T.SUB).pack(anchor="w")
        W.button(right.content, "打开数据文件夹", self._open_data_dir,
                 kind="ghost").pack(anchor="w", pady=(8, 16))

        tk.Frame(right.content, bg=T.BORDER, height=1).pack(fill="x", pady=(0, 14))
        W.hint(right.content,
               "多用户：侧栏可新建多个组合（例如本人 / 家人 / 测试仓），\n"
               "每个用户独立保存股数、参数与再平衡记录。",
               fg=T.MUTED).pack(anchor="w")

        bar = tk.Frame(page, bg=T.BG)
        bar.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(12, 0))
        self.settings_hint = W.hint(bar, "", fg=T.MUTED, bg=T.BG)
        self.settings_hint.pack(side="left")
        W.button(bar, "保存设置", self._save_settings, kind="primary",
                 padx=16, pady=8).pack(side="right")

    # ------------------------------------------------------------------
    # 策略原理
    # ------------------------------------------------------------------
    def _page_about(self, page):
        page.grid_columnconfigure(0, weight=1)
        page.grid_rowconfigure(0, weight=1)
        card = W.Card(page, "策略原理：从波动中「无中生有」")
        card.grid(row=0, column=0, sticky="nsew")

        text = tk.Text(card.content, wrap="word", bg=T.CARD, fg=T.SUB,
                       font=T.font(10), bd=0, relief="flat",
                       highlightthickness=0, spacing1=2, spacing3=6,
                       padx=4, pady=4, cursor="arrow")
        sb = ttk.Scrollbar(card.content, orient="vertical", command=text.yview)
        text.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        text.pack(side="left", fill="both", expand=True)

        text.tag_configure("h", font=T.font(11, "bold"), foreground=T.TEXT,
                           spacing1=12, spacing3=6)
        text.tag_configure("b", font=T.font(10, "bold"), foreground=T.TEXT)
        text.tag_configure("q", lmargin1=16, lmargin2=16, foreground=T.SUB)
        text.tag_configure("small", font=T.font(9), foreground=T.MUTED)

        blocks = [
            ("h", "一、为什么再平衡能「无中生有」"),
            ("p", "假设现金恒为 1，另一只资产每天以 1/2 概率翻倍、1/2 概率减半。"
                  "单独持有任何一方，长期财富都不增长；但每天强制调回 50:50，"
                  "几乎必然获得约每期 6% 的增长率。数学原因是长期财富由几何平均"
                  "（几何增长率 E[log(b·X)]）决定，而不是算数平均。"),
            ("p", "这就是 Cover 增长最优（log-optimal）组合的核心：最大化期望对数财富，"
                  "而不是最大化期望收益。系统性地「卖涨买跌」，把波动本身转化为收益"
                  "（volatility harvesting / 再平衡溢价）。"),
            ("h", "二、真实的经典案例"),
            ("q", "1960s–1980s 的 Iroquois Brands 与 Kin Ark：单独持有分别约 4 倍、8 倍；"
                  "事后最优的固定比例（约 55:45）月度再平衡约 73.6 倍。"),
            ("h", "三、本工具的做法"),
            ("p", "把理论简化为可执行的纪律：选两只低相关资产（QQQ 成长 / SCHD 价值红利），"
                  "维持固定比例（默认 50:50），按月（默认 31 天）或偏差超阈值（默认 5%）"
                  "时调回目标比例。程序只做三件事：取价、算偏差、提醒你下单。"),
            ("h", "四、必须知道的风险"),
            ("p", "· 并非万能盈利：两资产同时大跌时组合仍然亏损。\n"
                  "· 再平衡溢价来自波动，波动越低溢价越小。\n"
                  "· 频率过高会被手续费、买卖价差与税侵蚀，月度或阈值触发更实际。\n"
                  "· 通用投资组合（Universal Portfolios）只保证在指数增长率上逼近事后最优，"
                  "不保证任何单期收益。"),
            ("h", "五、参考"),
            ("small", "Thomas M. Cover, “Universal Portfolios”, Mathematical Finance, 1991；"
                      "斯坦福讲座《The Natural Mathematics Arising in Information Theory "
                      "and Investment》。"),
        ]
        for tag, content in blocks:
            text.insert("end", content + "\n", tag)
        text.configure(state="disabled")

    # ------------------------------------------------------------------
    # 页面切换
    # ------------------------------------------------------------------
    def _select_page(self, key):
        self.current_page = key
        self.pages[key].tkraise()
        title, sub = PAGE_META[key]
        self.page_title.config(text=title)
        self.page_sub.config(text=sub)
        for k, btn in self.nav_btns.items():
            if k == key:
                btn.config(bg=T.ACCENT_SOFT, fg=T.ACCENT, font=T.font(10, "bold"))
            else:
                btn.config(bg=T.CARD, fg=T.SUB, font=T.font(10))
        self._refresh_page(key)

    def _refresh_page(self, key=None):
        key = key or self.current_page
        if key == "dashboard":
            self._render_dashboard()
        elif key == "holdings":
            self._load_holdings()
        elif key == "history":
            self._render_history()
        elif key == "settings":
            self._load_settings()

    def _refresh_profile_box(self):
        names = [p["name"] for p in self.store.profiles]
        self.profile_box.config(values=names)
        self.profile_var.set(self.store.active_profile["name"])

    def _on_profile_switch(self, _event=None):
        name = self.profile_var.get()
        for p in self.store.profiles:
            if p["name"] == name:
                self.store.set_active(p["id"])
                break
        self._refresh_all()

    def _refresh_all(self):
        self._refresh_profile_box()
        self._refresh_page(self.current_page)

    # ------------------------------------------------------------------
    # 价格刷新
    # ------------------------------------------------------------------
    def refresh_prices(self, silent=False):
        if self._fetching:
            return
        self._fetching = True
        self._last_attempt = datetime.now()
        if not silent:
            self.status_lbl.config(text="正在获取最新价格…")
        threading.Thread(target=self._fetch_worker, daemon=True).start()

    def _fetch_worker(self):
        try:
            quotes, err = self.prices.refresh(TICKERS)
        except Exception as exc:  # noqa: BLE001
            quotes, err = {}, str(exc)
        self.q.put(("prices", (quotes, err)))

    def _apply_prices(self, quotes, err):
        self._fetching = False
        if self.prices.last_update:
            ts = self.prices.last_update.strftime("%H:%M:%S")
            src = "Yahoo Finance" if any(
                q.source.startswith("Yahoo") for q in quotes.values()) else "新浪财经"
            text = f"已更新 {ts} · {src}"
            if err:
                text += "（部分失败，已用缓存）"
        else:
            text = "价格获取失败，请检查网络或手动输入"
        self.status_lbl.config(text=text,
                               fg=T.MUTED if quotes else T.DANGER)
        self._refresh_page(self.current_page)

    def _manual_price_dialog(self):
        win = tk.Toplevel(self)
        win.title("手动输入价格")
        win.configure(bg=T.CARD)
        win.resizable(False, False)
        win.transient(self)
        W.center(win, 340, 250)

        wrap = tk.Frame(win, bg=T.CARD)
        wrap.pack(fill="both", expand=True, padx=18, pady=16)
        tk.Label(wrap, text="手动价格", bg=T.CARD, fg=T.TEXT,
                 font=T.font(12, "bold")).pack(anchor="w")
        W.hint(wrap, "网络不通或休市时可临时使用，手动价格优先于自动行情。",
               fg=T.MUTED).pack(anchor="w", pady=(2, 12))

        cur = {t: (self.prices.get(t).price if self.prices.get(t) else "")
               for t in TICKERS}
        vars_ = {}
        for t in TICKERS:
            row = tk.Frame(wrap, bg=T.CARD)
            row.pack(fill="x", pady=5)
            tk.Label(row, text=f"{t} 价格", bg=T.CARD, fg=T.SUB,
                     font=T.font(9)).pack(side="left")
            v = tk.StringVar(value=str(cur[t] or ""))
            vars_[t] = v
            W.entry(row, v, width=12).pack(side="right", ipady=5)

        def apply():
            try:
                prices = {}
                for t in TICKERS:
                    raw = vars_[t].get().strip()
                    if raw:
                        prices[t] = float(raw)
                        if prices[t] <= 0:
                            raise ValueError
                self.manual_prices = prices
                self.status_lbl.config(
                    text="已使用手动价格" if prices else "已清空手动价格", fg=T.WARN)
                win.destroy()
                self._refresh_page(self.current_page)
            except ValueError:
                messagebox.showwarning("输入有误", "请输入大于 0 的数字，或留空。", parent=win)

        btns = tk.Frame(wrap, bg=T.CARD)
        btns.pack(fill="x", pady=(14, 0))
        W.button(btns, "应用", apply, kind="primary", padx=16, pady=6).pack(side="right")
        W.button(btns, "取消", win.destroy, kind="ghost").pack(side="right", padx=(0, 8))
        win.grab_set()

    # ------------------------------------------------------------------
    # 快照
    # ------------------------------------------------------------------
    def _price_of(self, ticker):
        if ticker in self.manual_prices:
            return self.manual_prices[ticker]
        q = self.prices.get(ticker)
        return q.price if q else None

    def snapshot(self):
        qp, sp = self._price_of("QQQ"), self._price_of("SCHD")
        if qp is None or sp is None:
            return None
        return strategy.compute(self.store.active_profile, qp, sp)

    # ------------------------------------------------------------------
    # 仪表盘渲染
    # ------------------------------------------------------------------
    def _render_dashboard(self):
        prof = self.store.active_profile
        for ticker, card in (("QQQ", self.card_qqq), ("SCHD", self.card_schd)):
            q = self.prices.get(ticker)
            manual = ticker in self.manual_prices
            if q is None and not manual:
                card.set("--", "未获取到行情", T.MUTED, spark=[])
                continue
            price = self._price_of(ticker)
            if q is not None:
                chg = q.change or 0.0
                pctv = q.change_pct or 0.0
                color = T.UP if chg > 0 else T.DOWN if chg < 0 else T.FLAT
                delta = f"{chg:+.2f}  ({pctv:+.2f}%)"
                spark = [c for _, c in q.series]
            else:
                color, delta, spark = T.WARN, "手动价格", []
            if manual:
                delta += " · 手动"
            card.set(W.money(price), delta, color, spark=spark)

        snap = self.snapshot()
        if snap is None:
            self.card_total.set("--", "缺少价格，无法计算", T.MUTED)
            self.alloc_bar.set(prof.get("target_ratio", 0.5), prof.get("target_ratio", 0.5))
            for lbl in (self.meta_dev, self.meta_due, self.meta_last):
                lbl.config(text="--", fg=T.MUTED)
            self.meta_state.config(text="等待行情", fg=T.WARN)
            for item in self.tree.get_children():
                self.tree.delete(item)
            self.tree.insert("", "end", values=("QQQ", "--", "--", "--", "--", "--", "--"),
                             tags=("hold",))
            self.tree.insert("", "end", values=("SCHD", "--", "--", "--", "--", "--", "--"),
                             tags=("hold",))
            self.advice_hint.config(text="网络不可用时，可点击右上角「手动价格」。")
            return

        self.card_total.set(
            W.money(snap.total_value),
            f"QQQ {W.money(snap.qqq_value, 0)} · SCHD {W.money(snap.schd_value, 0)}",
            T.MUTED,
        )
        self.alloc_bar.set(snap.qqq_ratio, snap.target_ratio)

        over = snap.deviation >= snap.threshold
        self.meta_dev.config(text=W.pct(snap.deviation),
                             fg=T.DANGER if over else T.TEXT)

        if snap.days_since is None:
            self.meta_due.config(text="未记录", fg=T.MUTED)
            self.meta_last.config(text="未记录", fg=T.MUTED)
        else:
            if snap.days_to_due is not None and snap.days_to_due > 0:
                self.meta_due.config(text=f"{snap.days_to_due} 天", fg=T.TEXT)
            else:
                self.meta_due.config(
                    text=f"已超期 {abs(snap.days_to_due or 0)} 天", fg=T.WARN)
            self.meta_last.config(
                text=f"{snap.days_since} 天前", fg=T.TEXT)

        if not snap.has_position:
            self.meta_state.config(text="未录入持仓", fg=T.WARN)
        elif snap.need_rebalance:
            self.meta_state.config(text="需要再平衡", fg=T.DANGER)
        else:
            self.meta_state.config(text="保持持有", fg=T.OK)

        for item in self.tree.get_children():
            self.tree.delete(item)
        rows = (
            ("QQQ", snap.qqq_price, snap.qqq_shares, snap.target_qqq_shares, snap.trade_qqq),
            ("SCHD", snap.schd_price, snap.schd_shares, snap.target_schd_shares, snap.trade_schd),
        )
        for ticker, price, held, target, trade in rows:
            if trade == 0:
                action, tag = "无需调整", "hold"
            elif trade > 0:
                action, tag = "买入", "buy"
            else:
                action, tag = "卖出", "sell"
            self.tree.insert("", "end", values=(
                ticker,
                W.money(price),
                W.shares(held),
                W.shares(round(target, 4)),
                action,
                f"{abs(trade)}" if trade else "0",
                W.money(abs(trade) * price),
            ), tags=(tag,))

        if not snap.has_position:
            self.advice_hint.config(
                text="还没有录入持仓：请到【持仓与参数】填写股数。", fg=T.WARN)
        elif snap.need_rebalance:
            self.advice_hint.config(
                text=f"偏差 {W.pct(snap.deviation)} ≥ 阈值 {W.pct(snap.threshold, 0)}，建议调仓。",
                fg=T.DANGER)
        else:
            self.advice_hint.config(
                text="偏差未超阈值，可继续持有；到期日会自动提醒。", fg=T.SUB)

    # ------------------------------------------------------------------
    # 持仓页
    # ------------------------------------------------------------------
    def _load_holdings(self):
        p = self.store.active_profile
        self.var_qqq.set(self._num(p.get("qqq_shares", 0)))
        self.var_schd.set(self._num(p.get("schd_shares", 0)))
        self.var_ratio.set(self._num(p.get("target_ratio", 0.5) * 100))
        self.var_threshold.set(self._num(p.get("threshold", 0.05) * 100))
        self.var_interval.set(str(int(p.get("interval_days", 31))))
        last = p.get("last_rebalance_date")
        self.lbl_last_rebalance.config(
            text=last if last else "未记录",
            fg=T.TEXT if last else T.MUTED)
        snap = self.snapshot()
        if snap:
            self.lbl_position_value.config(
                text=f"组合总市值 {W.money(snap.total_value)}"
                     f"（QQQ {W.money(snap.qqq_value)} / SCHD {W.money(snap.schd_value)}）")
        else:
            self.lbl_position_value.config(text="组合总市值 --（等待价格）")

    @staticmethod
    def _num(v):
        v = float(v or 0)
        return (f"{v:.4f}".rstrip("0").rstrip(".")) if v else "0"

    def _save_holdings(self):
        try:
            q = float(self.var_qqq.get().strip() or 0)
            s = float(self.var_schd.get().strip() or 0)
            ratio = float(self.var_ratio.get().strip()) / 100
            th = float(self.var_threshold.get().strip()) / 100
            iv = int(float(self.var_interval.get().strip()))
        except ValueError:
            messagebox.showwarning("输入有误", "请检查：股数与参数必须是数字。")
            return
        if q < 0 or s < 0:
            messagebox.showwarning("输入有误", "股数不能为负数。")
            return
        if not 0.01 <= ratio <= 0.99:
            messagebox.showwarning("输入有误", "目标占比需在 1% ~ 99% 之间。")
            return
        if not 0.001 <= th <= 0.5:
            messagebox.showwarning("输入有误", "偏差阈值需在 0.1% ~ 50% 之间。")
            return
        if not 1 <= iv <= 365:
            messagebox.showwarning("输入有误", "间隔需为 1 ~ 365 天。")
            return

        p = self.store.active_profile
        p["qqq_shares"], p["schd_shares"] = q, s
        p["target_ratio"], p["threshold"], p["interval_days"] = ratio, th, iv
        self.store.save()
        self.holdings_hint.config(text="已保存", fg=T.OK)
        self.after(2200, lambda: self.holdings_hint.config(text=""))
        self._load_holdings()

    def _mark_today(self):
        p = self.store.active_profile
        p["last_rebalance_date"] = date.today().isoformat()
        self.store.save()
        self._load_holdings()
        messagebox.showinfo("已记录", "已把今天设为上次再平衡日期，周期从今天重新计算。")

    # ------------------------------------------------------------------
    # 记录再平衡
    # ------------------------------------------------------------------
    def _record_rebalance(self):
        snap = self.snapshot()
        prof = self.store.active_profile
        if snap is None or not snap.has_position:
            messagebox.showinfo("无法记录", "请先录入持仓并获取价格。")
            return

        win = tk.Toplevel(self)
        win.title("记录本次再平衡")
        win.configure(bg=T.CARD)
        win.resizable(False, False)
        win.transient(self)
        W.center(win, 420, 360)

        wrap = tk.Frame(win, bg=T.CARD)
        wrap.pack(fill="both", expand=True, padx=20, pady=18)
        tk.Label(wrap, text="记录本次再平衡", bg=T.CARD, fg=T.TEXT,
                 font=T.font(13, "bold")).pack(anchor="w")
        W.hint(wrap,
               f"当前 QQQ {snap.qqq_ratio*100:.1f}% / SCHD {snap.schd_ratio*100:.1f}%，"
               f"偏差 {snap.deviation*100:.2f}%",
               fg=T.MUTED).pack(anchor="w", pady=(2, 14))

        tk.Label(wrap, text="调仓后的实际股数（可自行修正）", bg=T.CARD, fg=T.SUB,
                 font=T.font(9)).pack(anchor="w")

        vars_ = {}
        for ticker, target in (("QQQ", snap.target_qqq_shares),
                               ("SCHD", snap.target_schd_shares)):
            row = tk.Frame(wrap, bg=T.CARD)
            row.pack(fill="x", pady=6)
            tk.Label(row, text=f"{ticker} 股数", bg=T.CARD, fg=T.SUB,
                     font=T.font(9)).pack(side="left")
            v = tk.StringVar(value=f"{target:.4f}")
            vars_[ticker] = v
            W.entry(row, v, width=14).pack(side="right", ipady=5)

        note_var = tk.StringVar(value="按目标比例调仓")
        row = tk.Frame(wrap, bg=T.CARD)
        row.pack(fill="x", pady=(8, 0))
        tk.Label(row, text="备注", bg=T.CARD, fg=T.SUB,
                 font=T.font(9)).pack(side="left")
        W.entry(row, note_var, width=24, justify="left").pack(side="right", ipady=5)

        date_var = tk.StringVar(value=date.today().isoformat())
        row = tk.Frame(wrap, bg=T.CARD)
        row.pack(fill="x", pady=8)
        tk.Label(row, text="日期", bg=T.CARD, fg=T.SUB,
                 font=T.font(9)).pack(side="left")
        W.entry(row, date_var, width=14, justify="center").pack(side="right", ipady=5)

        keep_var = tk.BooleanVar(value=True)
        chk = ttk.Checkbutton(wrap, text="同时把上面的股数保存为当前持仓",
                              variable=keep_var)
        chk.pack(anchor="w", pady=(6, 0))

        def save():
            try:
                q = float(vars_["QQQ"].get())
                s = float(vars_["SCHD"].get())
                d = date.fromisoformat(date_var.get().strip())
                if q < 0 or s < 0:
                    raise ValueError
            except ValueError:
                messagebox.showwarning("输入有误", "股数需为非负数，日期格式 YYYY-MM-DD。",
                                       parent=win)
                return
            if keep_var.get():
                prof["qqq_shares"], prof["schd_shares"] = q, s
            prof["last_rebalance_date"] = d.isoformat()
            self.store.add_history(prof, {
                "type": "再平衡",
                "date": d.isoformat(),
                "qqq_shares": q,
                "schd_shares": s,
                "qqq_price": round(snap.qqq_price, 4),
                "schd_price": round(snap.schd_price, 4),
                "total_value": round(q * snap.qqq_price + s * snap.schd_price, 2),
                "qqq_ratio_before": round(snap.qqq_ratio, 4),
                "deviation_before": round(snap.deviation, 4),
                "note": note_var.get().strip(),
            })
            self.store.save()
            win.destroy()
            self._refresh_all()
            self.status_lbl.config(text=f"已记录再平衡：{d.isoformat()}", fg=T.OK)

        btns = tk.Frame(wrap, bg=T.CARD)
        btns.pack(fill="x", pady=(16, 0))
        W.button(btns, "保存记录", save, kind="primary", padx=16, pady=7).pack(side="right")
        W.button(btns, "取消", win.destroy, kind="ghost").pack(side="right", padx=(0, 8))
        win.grab_set()

    # ------------------------------------------------------------------
    # 用户档案
    # ------------------------------------------------------------------
    def _new_profile(self):
        name = simpledialog.askstring("新建用户", "给这个组合起个名字：",
                                      parent=self, initialvalue="新组合")
        if not name:
            return
        self.store.add_profile(name)
        self._refresh_all()

    def _rename_profile(self):
        p = self.store.active_profile
        name = simpledialog.askstring("重命名", "新的名称：", parent=self,
                                      initialvalue=p["name"])
        if name:
            self.store.rename_profile(p["id"], name)
            self._refresh_all()

    def _delete_profile(self):
        p = self.store.active_profile
        if len(self.store.profiles) <= 1:
            messagebox.showinfo("无法删除", "至少保留一个用户。")
            return
        if messagebox.askyesno("删除用户",
                              f"确定删除「{p['name']}」及其再平衡记录？此操作不可撤销。"):
            self.store.delete_profile(p["id"])
            self._refresh_all()

    # ------------------------------------------------------------------
    # 记录页
    # ------------------------------------------------------------------
    def _render_history(self):
        for item in self.hist_tree.get_children():
            self.hist_tree.delete(item)
        hist = list(self.store.active_profile.get("history") or [])
        hist.sort(key=lambda r: (r.get("date") or "", r.get("created_at") or ""),
                  reverse=True)
        for r in hist:
            self.hist_tree.insert("", "end", values=(
                r.get("date", ""),
                r.get("type", "再平衡"),
                W.shares(float(r.get("qqq_shares") or 0)),
                W.shares(float(r.get("schd_shares") or 0)),
                W.money(float(r.get("total_value") or 0)),
                f"{(r.get('qqq_ratio_before') or 0)*100:.1f}%",
                r.get("note", ""),
            ))
        self.lbl_history_count.config(text=f"共 {len(hist)} 条记录")

    def _export_history(self):
        hist = self.store.active_profile.get("history") or []
        if not hist:
            messagebox.showinfo("没有记录", "当前用户还没有再平衡记录。")
            return
        path = filedialog.asksaveasfilename(
            title="导出记录", defaultextension=".csv",
            initialfile=f"rebalance_{self.store.active_profile['name']}.csv",
            filetypes=[("CSV 文件", "*.csv")])
        if not path:
            return
        headers = ["日期", "类型", "QQQ股数", "SCHD股数", "QQQ价格", "SCHD价格",
                   "总市值", "调仓前QQQ占比", "调仓前偏差", "备注"]
        keys = ["date", "type", "qqq_shares", "schd_shares", "qqq_price",
                "schd_price", "total_value", "qqq_ratio_before",
                "deviation_before", "note"]
        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                w = csv.writer(f)
                w.writerow(headers)
                for r in hist:
                    w.writerow([r.get(k, "") for k in keys])
            messagebox.showinfo("已导出", path)
        except OSError as exc:
            messagebox.showerror("导出失败", str(exc))

    def _clear_history(self):
        if not messagebox.askyesno("清空记录", "确定清空当前用户的全部再平衡记录？"):
            return
        self.store.clear_history(self.store.active_profile)
        self._render_history()

    # ------------------------------------------------------------------
    # 设置
    # ------------------------------------------------------------------
    def _load_settings(self):
        s = self.store.settings
        self.var_remind_on.set(bool(s.get("reminder_enabled", True)))
        self.var_remind_time.set(s.get("reminder_time", "09:30"))
        self.var_refresh.set(str(s.get("refresh_minutes", 5)))
        self.var_autostart.set(bool(s.get("autostart", False)))

    def _save_settings(self):
        s = self.store.settings
        try:
            hh, mm = self.var_remind_time.get().strip().split(":")
            if not (0 <= int(hh) <= 23 and 0 <= int(mm) <= 59):
                raise ValueError
            minutes = int(float(self.var_refresh.get().strip()))
            if not 1 <= minutes <= 240:
                raise ValueError
        except ValueError:
            messagebox.showwarning("输入有误", "提醒时间格式应为 HH:MM，刷新间隔 1~240 分钟。")
            return

        s["reminder_enabled"] = bool(self.var_remind_on.get())
        s["reminder_time"] = f"{int(hh):02d}:{int(mm):02d}"
        s["refresh_minutes"] = minutes
        want_auto = bool(self.var_autostart.get())
        if want_auto != bool(s.get("autostart")):
            if self._set_autostart(want_auto):
                s["autostart"] = want_auto
            else:
                self.var_autostart.set(bool(s.get("autostart")))
                messagebox.showwarning("开机启动设置失败", "无法创建启动快捷方式，请手动放置快捷方式。")
        self.store.save()
        self.settings_hint.config(text="设置已保存", fg=T.OK)
        self.after(2200, lambda: self.settings_hint.config(text=""))

    def _set_autostart(self, enabled: bool) -> bool:
        try:
            startup = (Path(os.environ.get("APPDATA", "")) /
                       "Microsoft/Windows/Start Menu/Programs/Startup")
            if not startup.exists():
                return False
            lnk = startup / "QQQ-SCHD-Rebalance.lnk"
            if not enabled:
                if lnk.exists():
                    lnk.unlink()
                return True
            pythonw = Path(sys.executable).with_name("pythonw.exe")
            target = pythonw if pythonw.exists() else Path(sys.executable)
            script = BASE_DIR / "main.py"
            ps = (
                '$W=New-Object -ComObject WScript.Shell;'
                f'$s=$W.CreateShortcut("{lnk}");'
                f'$s.TargetPath="{target}";'
                f'$s.Arguments=\'"{script}"\';'
                f'$s.WorkingDirectory="{BASE_DIR}";'
                f'$s.IconLocation="{target}";'
                '$s.Save();'
            )
            subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                            "-Command", ps],
                           capture_output=True, timeout=25,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            return lnk.exists()
        except (OSError, subprocess.SubprocessError):
            return False

    def _open_data_dir(self):
        try:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            os.startfile(str(DATA_DIR))  # noqa: S606
        except OSError as exc:
            messagebox.showerror("打开失败", str(exc))

    # ------------------------------------------------------------------
    # 回测
    # ------------------------------------------------------------------
    def _run_backtest(self):
        if self._backtesting:
            return
        self._backtesting = True
        label = self.var_range.get()
        rng = next((k for k, v in RANGE_LABEL.items() if v == label), "5y")
        self.store.settings["backtest_range"] = rng
        self.store.save()
        self.lbl_bt_status.config(text="正在拉取历史数据…", fg=T.MUTED)
        self.btn_backtest.config(state="disabled")
        threading.Thread(target=self._backtest_worker, args=(rng,), daemon=True).start()

    def _backtest_worker(self, rng):
        try:
            q = fetch_history("QQQ", rng=rng)
            s = fetch_history("SCHD", rng=rng)
            result = strategy.backtest(q, s,
                                       float(self.store.active_profile.get("target_ratio", 0.5)))
            self.q.put(("backtest", (result, None)))
        except Exception as exc:  # noqa: BLE001
            self.q.put(("backtest", (None, str(exc))))

    def _apply_backtest(self, result, err):
        self._backtesting = False
        self.btn_backtest.config(state="normal")
        if err or not result:
            self.lbl_bt_status.config(text="回测失败：" + (err or "数据不足"),
                                      fg=T.DANGER)
            return

        self.lbl_bt_status.config(text="回测完成", fg=T.OK)
        names = {"qqq": ("QQQ 单持", T.QQQ), "schd": ("SCHD 单持", T.SCHD),
                 "blend": ("50:50 不再平衡", "#9aa4b6"),
                 "rebal": ("50:50 月度再平衡", "#e08a2e")}
        series = []
        for key, (name, color) in names.items():
            dates, values = result["curves"][key]
            series.append({"name": name, "color": color,
                           "points": list(zip(dates, values))})
        self.chart.set_series(series)

        for item in self.bt_tree.get_children():
            self.bt_tree.delete(item)
        order = ["qqq", "schd", "blend", "rebal"]
        for key in order:
            m = result["metrics"][key]
            self.bt_tree.insert("", "end", values=(
                names[key][0],
                W.pct(m["total_return"], 1, signed=True),
                W.pct(m["cagr"], 2),
                W.pct(m["vol"], 1),
                W.pct(m["maxdd"], 1),
                f"{m['final']:.2f}x",
            ))

        m = result["metrics"]
        years = m["rebal"].get("years", 0)
        diff = (m["rebal"]["final"] / m["blend"]["final"] - 1) * 100
        self.lbl_bt_conclusion.config(
            text=f"区间 {years:.1f} 年：月度再平衡期末 {m['rebal']['final']:.2f}x，"
                 f"不再平衡 {m['blend']['final']:.2f}x，"
                 f"再平衡{'多' if diff >= 0 else '少'} {abs(diff):.1f}%；"
                 f"最大回撤由 {abs(m['blend']['maxdd'])*100:.1f}% 变为 "
                 f"{abs(m['rebal']['maxdd'])*100:.1f}%。"
                 f"（历史不代表未来）",
            fg=T.SUB)

    # ------------------------------------------------------------------
    # 提醒
    # ------------------------------------------------------------------
    def _pump(self):
        try:
            while True:
                kind, payload = self.q.get_nowait()
                if kind == "prices":
                    self._apply_prices(*payload)
                elif kind == "backtest":
                    self._apply_backtest(*payload)
        except queue.Empty:
            pass
        try:
            self._tick()
        except Exception:  # noqa: BLE001 - 定时器不能因单次异常停止
            pass
        finally:
            self.after(1000, self._pump)

    def _tick(self):
        now = datetime.now()
        minutes = int(self.store.settings.get("refresh_minutes", 5) or 5)
        last = self.prices.last_update
        last_try = self._last_attempt
        due_time = last is None or (now - last).total_seconds() >= minutes * 60
        # 失败时至少间隔 90 秒再重试，避免反复发请求
        cooldown_ok = (last_try is None
                       or (now - last_try).total_seconds() >= min(minutes * 60, 90))
        if due_time and cooldown_ok:
            self.refresh_prices(silent=True)

        if self._reminder_open:
            return
        decision = reminders.evaluate(self.store.active_profile, self.snapshot(),
                                      now, self.store.settings)
        if decision.due:
            self.store.settings["last_notified"] = now.date().isoformat()
            self.store.save()
            self._show_reminder(decision)

    _reminder_open = False

    def _check_reminder_now(self):
        decision = reminders.evaluate(self.store.active_profile, self.snapshot(),
                                      datetime.now(), self.store.settings,
                                      ignore_gates=True)
        if decision.due:
            self._show_reminder(decision)
        else:
            messagebox.showinfo(
                "暂不需要再平衡",
                decision.blocked_by or "偏差未超阈值，且未到定期再平衡时间。")

    def _show_reminder(self, decision):
        snap = self.snapshot()
        if snap is None:
            return
        self._reminder_open = True
        try:
            self.deiconify()
            self.lift()
            self.bell()
        except tk.TclError:
            pass

        win = tk.Toplevel(self)
        win.title("再平衡提醒")
        win.configure(bg=T.CARD)
        win.resizable(False, False)
        win.transient(self)
        win.attributes("-topmost", True)
        W.center(win, 460, 440)

        head = tk.Frame(win, bg=T.WARN_SOFT, height=64)
        head.pack(fill="x")
        head.pack_propagate(False)
        tk.Label(head, text="该再平衡了", bg=T.WARN_SOFT, fg=T.WARN,
                 font=T.font(14, "bold")).pack(side="left", padx=20)

        wrap = tk.Frame(win, bg=T.CARD)
        wrap.pack(fill="both", expand=True, padx=20, pady=16)

        for reason in decision.reasons:
            tk.Label(wrap, text="· " + reason, bg=T.CARD, fg=T.TEXT,
                     font=T.font(10), wraplength=400, justify="left",
                     anchor="w").pack(fill="x", pady=(0, 6))

        box = tk.Frame(wrap, bg=T.CARD_ALT, highlightbackground=T.BORDER,
                       highlightthickness=1)
        box.pack(fill="x", pady=(10, 0))
        inner = tk.Frame(box, bg=T.CARD_ALT)
        inner.pack(fill="x", padx=12, pady=10)
        lines = [
            f"总市值 {W.money(snap.total_value)}　"
            f"QQQ {snap.qqq_ratio*100:.1f}% / SCHD {snap.schd_ratio*100:.1f}%",
        ]
        for ticker, trade, price in (("QQQ", snap.trade_qqq, snap.qqq_price),
                                     ("SCHD", snap.trade_schd, snap.schd_price)):
            if trade == 0:
                continue
            verb = "买入" if trade > 0 else "卖出"
            lines.append(f"{ticker} {verb} {abs(trade)} 股（约 {W.money(abs(trade)*price)}）")
        if len(lines) == 1:
            lines.append("按整数股无需调整，可按目标股数微调。")
        for line in lines:
            tk.Label(inner, text=line, bg=T.CARD_ALT, fg=T.SUB,
                     font=T.font(9), anchor="w", justify="left").pack(fill="x")

        W.hint(wrap, "提醒只是提示，不会自动交易；请到券商 App 手动下单。",
               fg=T.MUTED).pack(anchor="w", pady=(12, 0))

        btns = tk.Frame(wrap, bg=T.CARD)
        btns.pack(fill="x", side="bottom", pady=(12, 0))

        def close():
            try:
                win.attributes("-topmost", False)
            except tk.TclError:
                pass
            win.destroy()
            self._reminder_open = False

        def done():
            close()
            self._record_rebalance()

        def snooze():
            until = datetime.now() + timedelta(days=3)
            self.store.settings["snooze_until"] = until.isoformat(timespec="seconds")
            self.store.settings["last_notified"] = datetime.now().date().isoformat()
            self.store.save()
            close()

        W.button(btns, "记录已完成", done, kind="primary", padx=14, pady=7).pack(side="right")
        W.button(btns, "3 天后再提醒", snooze, kind="warn", padx=12,
                 pady=7).pack(side="right", padx=(0, 8))
        W.button(btns, "关闭", close, kind="ghost", padx=12,
                 pady=7).pack(side="right", padx=(0, 8))

        win.protocol("WM_DELETE_WINDOW", close)
        win.grab_set()
        win.after(400, lambda: win.attributes("-topmost", False))

    # ------------------------------------------------------------------
    def _on_close(self):
        try:
            self.store.settings["window_geometry"] = self.geometry()
            self.store.save()
        except (tk.TclError, OSError):
            pass
        self.destroy()


def run():
    store = Store()
    app = App(store)
    app.mainloop()
