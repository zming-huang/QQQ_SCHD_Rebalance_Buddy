# -*- coding: utf-8 -*-
"""全局配置、路径与默认值。"""

from pathlib import Path

APP_NAME = "QQQ x SCHD 再平衡管家"
APP_TITLE = "QQQ x SCHD 再平衡管家"
APP_VERSION = "1.0.0"

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
STATE_FILE = DATA_DIR / "state.json"
ERROR_LOG = DATA_DIR / "error.log"

# 早期版本（工作区根目录）的状态文件，首次运行时自动迁移
LEGACY_STATE_FILE = BASE_DIR.parent / "rebalance_state.json"

TICKERS = ("QQQ", "SCHD")
TICKER_NAMES = {"QQQ": "纳指100 ETF", "SCHD": "美国红利 ETF"}

DEFAULT_SETTINGS = {
    "refresh_minutes": 5,        # 自动刷新价格间隔（分钟）
    "reminder_enabled": True,    # 是否启用定期提醒
    "reminder_time": "09:30",    # 每天这个时间之后可以弹提醒
    "snooze_until": None,        # ISO 时间字符串："稍后提醒"截止
    "last_notified": None,       # 上次提醒日期 "YYYY-MM-DD"
    "window_geometry": "",
    "autostart": False,
    "backtest_range": "5y",
}

DEFAULT_PROFILE = {
    "name": "我的组合",
    "qqq_shares": 0.0,
    "schd_shares": 0.0,
    "target_ratio": 0.5,     # QQQ 目标占比
    "threshold": 0.05,       # 偏差阈值（5%）
    "interval_days": 31,     # 定期再平衡间隔（天）
    "last_rebalance_date": None,
    "history": [],
    "created_at": None,
}
