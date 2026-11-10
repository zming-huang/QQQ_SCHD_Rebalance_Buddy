# -*- coding: utf-8 -*-
"""提醒判定逻辑（与界面解耦，方便单独测试）。

触发条件（满足其一）：
  1. 距上次再平衡 >= 定期间隔（默认 31 天）—— 对应"月度强制再平衡"
  2. 目标偏差 >= 阈值（默认 5%，即 55:45 时触发）

抑制条件：未启用提醒 / 处于"稍后提醒"期间 / 当天已提醒过 / 未到每日提醒时间。
"""

from dataclasses import dataclass, field
from datetime import datetime, time as dtime
from typing import Optional


@dataclass
class Decision:
    due: bool = False
    reasons: list = field(default_factory=list)
    severity: str = "info"      # info | warn | strong
    blocked_by: Optional[str] = None


def parse_time(text: str, default: dtime = dtime(9, 30)) -> dtime:
    try:
        hh, mm = str(text).strip().split(":")
        return dtime(int(hh), int(mm))
    except (ValueError, AttributeError):
        return default


def evaluate(profile: dict, snapshot, now: datetime, settings: dict,
             ignore_gates: bool = False) -> Decision:
    if snapshot is None or not snapshot.has_position:
        return Decision(False, [], blocked_by="没有持仓或价格缺失")

    schedule_due = (snapshot.days_since is not None
                    and snapshot.days_since >= snapshot.interval_days)
    threshold_due = snapshot.deviation >= float(profile.get("threshold", 0.05))

    if not (schedule_due or threshold_due):
        return Decision(False, [])

    reasons = []
    if threshold_due:
        reasons.append(f"QQQ 占比 {snapshot.qqq_ratio*100:.1f}%，"
                       f"偏离目标 {snapshot.deviation*100:.1f}%"
                       f"（阈值 {snapshot.threshold*100:.0f}%）")
    if schedule_due:
        reasons.append(f"距上次再平衡 {snapshot.days_since} 天，"
                       f"已超过 {snapshot.interval_days} 天周期")

    severity = "strong" if (schedule_due and threshold_due) else "warn"
    decision = Decision(True, reasons, severity)

    if ignore_gates:
        return decision

    if not settings.get("reminder_enabled", True):
        decision.due, decision.blocked_by = False, "提醒已关闭"
        return decision

    snooze = settings.get("snooze_until")
    if snooze:
        try:
            if now < datetime.fromisoformat(str(snooze)):
                decision.due, decision.blocked_by = False, "处于稍后提醒期"
                return decision
        except ValueError:
            pass

    if now.time() < parse_time(settings.get("reminder_time", "09:30")):
        decision.due, decision.blocked_by = False, "未到每日提醒时间"
        return decision

    if settings.get("last_notified") == now.date().isoformat():
        decision.due, decision.blocked_by = False, "今天已提醒过"
    return decision
