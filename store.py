# -*- coding: utf-8 -*-
"""数据持久化：多用户档案 + 设置 + 再平衡记录。

数据文件：buddy/data/state.json
结构：
{
  "version": 2,
  "active_profile_id": "p_xxx",
  "settings": {...},
  "profiles": [ {id, name, qqq_shares, ..., history: [...]}, ... ]
}
"""

import json
import time
import uuid
from datetime import date, datetime
from pathlib import Path

from config import (DATA_DIR, DEFAULT_PROFILE, DEFAULT_SETTINGS,
                    LEGACY_STATE_FILE, STATE_FILE)


def _now_iso() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def new_profile(name: str = "我的组合") -> dict:
    p = dict(DEFAULT_PROFILE)
    p["name"] = name
    p["id"] = "p_" + uuid.uuid4().hex[:8]
    p["history"] = []
    p["created_at"] = _now_iso()
    return p


class Store:
    """状态文件读写。所有修改后调用 save() 落盘。"""

    def __init__(self, path: Path | str = STATE_FILE):
        self.path = Path(path)
        self.data = self._load()

    # ------------------------------------------------------------------
    # 载入 / 保存
    # ------------------------------------------------------------------
    def _load(self) -> dict:
        if self.path.exists():
            try:
                raw = json.loads(self.path.read_text(encoding="utf-8"))
                return self._normalize(raw)
            except (json.JSONDecodeError, OSError, UnicodeDecodeError):
                pass
        data = self._fresh()
        self._migrate_legacy(data)
        self.data = data
        self.save()
        return data

    def _fresh(self) -> dict:
        p = new_profile("我的组合")
        return {
            "version": 2,
            "active_profile_id": p["id"],
            "settings": dict(DEFAULT_SETTINGS),
            "profiles": [p],
        }

    def _migrate_legacy(self, data: dict) -> None:
        """把旧版 rebalance_state.json 的持仓迁移进来。"""
        try:
            if not LEGACY_STATE_FILE.exists():
                return
            old = json.loads(LEGACY_STATE_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return
        prof = data["profiles"][0]
        for key in ("qqq_shares", "schd_shares", "last_rebalance_date",
                    "threshold", "interval_days"):
            if key in old and old[key] is not None:
                prof[key] = old[key]
        if prof.get("qqq_shares") or prof.get("schd_shares"):
            prof["name"] = "我的组合"

    def _normalize(self, raw: dict) -> dict:
        if not isinstance(raw, dict):
            raise ValueError("状态文件格式错误")

        # 兼容旧版单用户结构（无 profiles 字段）
        if "profiles" not in raw:
            p = new_profile("我的组合")
            for key in DEFAULT_PROFILE:
                if key in raw and raw[key] is not None:
                    p[key] = raw[key]
            raw = {
                "version": 2,
                "active_profile_id": p["id"],
                "settings": dict(DEFAULT_SETTINGS),
                "profiles": [p],
            }

        settings = dict(DEFAULT_SETTINGS)
        settings.update(raw.get("settings") or {})
        raw["settings"] = settings

        profiles = []
        for item in raw.get("profiles") or []:
            if not isinstance(item, dict):
                continue
            prof = new_profile(item.get("name") or "我的组合")
            for key, val in item.items():
                prof[key] = val
            prof["qqq_shares"] = float(prof.get("qqq_shares") or 0)
            prof["schd_shares"] = float(prof.get("schd_shares") or 0)
            prof["target_ratio"] = float(prof.get("target_ratio") or 0.5)
            prof["threshold"] = float(prof.get("threshold") or 0.05)
            prof["interval_days"] = int(prof.get("interval_days") or 31)
            prof["history"] = list(prof.get("history") or [])
            profiles.append(prof)
        if not profiles:
            profiles = [new_profile("我的组合")]
        raw["profiles"] = profiles

        if raw.get("active_profile_id") not in [p["id"] for p in profiles]:
            raw["active_profile_id"] = profiles[0]["id"]
        raw["version"] = 2
        return raw

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        text = json.dumps(self.data, ensure_ascii=False, indent=2)
        tmp = self.path.with_suffix(".json.tmp")
        tmp.write_text(text, encoding="utf-8")
        # OneDrive / 杀毒软件可能短暂锁定文件，重试几次
        for attempt in range(6):
            try:
                tmp.replace(self.path)
                return
            except PermissionError:
                if attempt == 5:
                    # 退化为直接写入，避免数据丢失
                    self.path.write_text(text, encoding="utf-8")
                    try:
                        tmp.unlink()
                    except OSError:
                        pass
                    return
                time.sleep(0.12)

    # ------------------------------------------------------------------
    # 设置
    # ------------------------------------------------------------------
    @property
    def settings(self) -> dict:
        return self.data["settings"]

    # ------------------------------------------------------------------
    # 用户档案
    # ------------------------------------------------------------------
    @property
    def profiles(self) -> list:
        return self.data["profiles"]

    @property
    def active_profile(self) -> dict:
        pid = self.data.get("active_profile_id")
        for p in self.profiles:
            if p["id"] == pid:
                return p
        self.data["active_profile_id"] = self.profiles[0]["id"]
        return self.profiles[0]

    def set_active(self, pid: str) -> None:
        if any(p["id"] == pid for p in self.profiles):
            self.data["active_profile_id"] = pid
            self.save()

    def add_profile(self, name: str) -> dict:
        name = (name or "").strip() or "新用户"
        p = new_profile(self._unique_name(name))
        self.profiles.append(p)
        self.data["active_profile_id"] = p["id"]
        self.save()
        return p

    def _unique_name(self, name: str) -> str:
        names = {p["name"] for p in self.profiles}
        if name not in names:
            return name
        i = 2
        while f"{name} {i}" in names:
            i += 1
        return f"{name} {i}"

    def rename_profile(self, pid: str, name: str) -> None:
        name = (name or "").strip()
        if not name:
            return
        for p in self.profiles:
            if p["id"] == pid:
                p["name"] = name
        self.save()

    def delete_profile(self, pid: str) -> bool:
        if len(self.profiles) <= 1:
            return False
        self.data["profiles"] = [p for p in self.profiles if p["id"] != pid]
        if self.data["active_profile_id"] == pid:
            self.data["active_profile_id"] = self.profiles[0]["id"]
        self.save()
        return True

    # ------------------------------------------------------------------
    # 再平衡记录
    # ------------------------------------------------------------------
    def add_history(self, profile: dict, record: dict) -> None:
        record = dict(record)
        record.setdefault("date", date.today().isoformat())
        record.setdefault("created_at", _now_iso())
        profile.setdefault("history", []).append(record)
        self.save()

    def clear_history(self, profile: dict) -> None:
        profile["history"] = []
        self.save()
