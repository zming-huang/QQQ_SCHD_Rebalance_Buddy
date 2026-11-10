# -*- coding: utf-8 -*-
"""再平衡计算与策略回测（对应 stragy.md 第九节的实用版本）。

核心思想：几何增长率最优（Kelly / log-optimal）的简化实践——
两只低相关、高波动的资产维持固定比例，定期"卖涨买跌"，
长期收割再平衡溢价（rebalancing premium / volatility harvesting）。
"""

import math
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Optional


def _to_date(value) -> Optional[date]:
    if not value:
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


@dataclass
class Snapshot:
    qqq_price: float
    schd_price: float
    qqq_shares: float
    schd_shares: float
    qqq_value: float
    schd_value: float
    total_value: float
    qqq_ratio: float
    target_ratio: float
    deviation: float
    target_qqq_shares: float
    target_schd_shares: float
    delta_qqq_shares: float
    delta_schd_shares: float
    trade_qqq: int
    trade_schd: int
    need_rebalance: bool
    threshold: float
    interval_days: int
    days_since: Optional[int]
    days_to_due: Optional[int]
    next_due_date: Optional[date]

    @property
    def schd_ratio(self) -> float:
        return 1.0 - self.qqq_ratio

    @property
    def has_position(self) -> bool:
        return self.total_value > 0


def compute(profile: dict, qqq_price: float, schd_price: float,
            today: Optional[date] = None) -> Snapshot:
    today = today or date.today()
    target = float(profile.get("target_ratio", 0.5))
    threshold = float(profile.get("threshold", 0.05))
    interval = int(profile.get("interval_days", 31))

    qs = float(profile.get("qqq_shares", 0) or 0)
    ss = float(profile.get("schd_shares", 0) or 0)
    qqq_value = qs * qqq_price
    schd_value = ss * schd_price
    total = qqq_value + schd_value

    if total > 0:
        qqq_ratio = qqq_value / total
    else:
        qqq_ratio = target
    deviation = abs(qqq_ratio - target)

    target_qqq_shares = (total * target / qqq_price) if qqq_price > 0 else 0.0
    target_schd_shares = (total * (1 - target) / schd_price) if schd_price > 0 else 0.0
    delta_q = target_qqq_shares - qs
    delta_s = target_schd_shares - ss

    last = _to_date(profile.get("last_rebalance_date"))
    days_since = (today - last).days if last else None
    next_due = last + timedelta(days=interval) if last else None
    days_to_due = (next_due - today).days if next_due else None

    return Snapshot(
        qqq_price=qqq_price,
        schd_price=schd_price,
        qqq_shares=qs,
        schd_shares=ss,
        qqq_value=qqq_value,
        schd_value=schd_value,
        total_value=total,
        qqq_ratio=qqq_ratio,
        target_ratio=target,
        deviation=deviation,
        target_qqq_shares=target_qqq_shares,
        target_schd_shares=target_schd_shares,
        delta_qqq_shares=delta_q,
        delta_schd_shares=delta_s,
        trade_qqq=int(round(delta_q)),
        trade_schd=int(round(delta_s)),
        need_rebalance=total > 0 and deviation >= threshold,
        threshold=threshold,
        interval_days=interval,
        days_since=days_since,
        days_to_due=days_to_due,
        next_due_date=next_due,
    )


# ---------------------------------------------------------------------------
# 回测
# ---------------------------------------------------------------------------

def _month_key(dt: datetime) -> tuple:
    return (dt.year, dt.month)


def backtest(qqq_hist: list, schd_hist: list, target_ratio: float = 0.5,
             start_value: float = 1.0) -> Optional[dict]:
    """按月对齐两只 ETF 的历史价格，比较四种持有方式。

    返回 curves: {名称: [(datetime, 净值倍数)]} 与 metrics: {名称: {...}}
    """
    if len(qqq_hist) < 3 or len(schd_hist) < 3:
        return None

    qmap = {}
    for dt, px in qqq_hist:
        qmap[_month_key(dt)] = (dt, px)
    smap = {}
    for dt, px in schd_hist:
        smap[_month_key(dt)] = (dt, px)

    keys = sorted(set(qmap) & set(smap))
    if len(keys) < 3:
        return None

    dates = []
    qqq_bh, schd_bh, blend, rebal = [], [], [], []
    q0 = qmap[keys[0]][1]
    s0 = smap[keys[0]][1]
    q_sh = start_value * target_ratio / q0        # 买入后长期不动
    s_sh = start_value * (1 - target_ratio) / s0
    r_value = start_value                         # 每月末调回目标比例

    for i, key in enumerate(keys):
        q_dt, q_px = qmap[key]
        _, s_px = smap[key]
        dates.append(q_dt)

        if i > 0:
            prev = keys[i - 1]
            r_value *= (target_ratio * q_px / qmap[prev][1]
                        + (1 - target_ratio) * s_px / smap[prev][1])

        qqq_bh.append(q_px / q0)
        schd_bh.append(s_px / s0)
        blend.append((q_sh * q_px + s_sh * s_px) / start_value)
        rebal.append(r_value / start_value)

    curves = {
        "qqq": (dates, qqq_bh),
        "schd": (dates, schd_bh),
        "blend": (dates, blend),
        "rebal": (dates, rebal),
    }
    metrics = {k: _metrics(dates, v[1]) for k, v in curves.items()}
    return {"dates": dates, "curves": curves, "metrics": metrics}


def _metrics(dates: list, values: list) -> dict:
    if not values:
        return {}
    first, last = values[0], values[-1]
    years = max((dates[-1] - dates[0]).days / 365.25, 1e-9)
    cagr = (last / first) ** (1 / years) - 1 if first > 0 else 0.0

    rets = []
    for i in range(1, len(values)):
        if values[i - 1] > 0:
            rets.append(values[i] / values[i - 1] - 1)
    if len(rets) > 2:
        mean = sum(rets) / len(rets)
        var = sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)
        vol = math.sqrt(var) * math.sqrt(12)
    else:
        vol = 0.0

    peak, maxdd = values[0], 0.0
    for v in values:
        peak = max(peak, v)
        if peak > 0:
            maxdd = min(maxdd, v / peak - 1)

    return {
        "total_return": last / first - 1 if first else 0.0,
        "cagr": cagr,
        "vol": vol,
        "maxdd": maxdd,
        "final": last,
        "years": years,
    }
