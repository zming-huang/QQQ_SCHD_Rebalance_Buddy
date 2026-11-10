# -*- coding: utf-8 -*-
"""行情获取：Yahoo Finance 为主，新浪财经为备份，全部使用标准库。"""

import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
TIMEOUT = 8


@dataclass
class Quote:
    ticker: str
    price: float
    prev_close: Optional[float] = None
    change: Optional[float] = None
    change_pct: Optional[float] = None
    source: str = ""
    time: str = ""
    series: list = field(default_factory=list)   # [(datetime, close), ...]


def _http_get(url: str, headers: Optional[dict] = None, encoding="utf-8") -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return resp.read().decode(encoding, errors="replace")


# ---------------------------------------------------------------------------
# Yahoo Finance
# ---------------------------------------------------------------------------

def _fetch_yahoo(ticker: str, rng: str = "1mo", interval: str = "1d") -> Optional[Quote]:
    for host in ("query1", "query2"):
        url = (f"https://{host}.finance.yahoo.com/v8/finance/chart/{ticker}"
               f"?interval={interval}&range={rng}&includePrePost=false")
        try:
            data = json.loads(_http_get(url))
            result = data["chart"]["result"][0]
            meta = result.get("meta", {})
            stamps = result.get("timestamp") or []
            closes = (result.get("indicators", {}).get("quote") or [{}])[0].get("close") or []
            series = []
            for ts, close in zip(stamps, closes):
                if close is None:
                    continue
                series.append((datetime.fromtimestamp(ts), float(close)))

            price = meta.get("regularMarketPrice")
            if price is None and series:
                price = series[-1][1]
            if price is None:
                continue
            price = float(price)

            prev = None
            if len(series) >= 2:
                # 上一交易日收盘（Yahoo 的 chartPreviousClose 在 1mo 区间下
                # 指的是区间起点前一天的收盘，不能反映"当日涨跌"，故优先用日线序列）
                prev = series[-2][1]
            if prev is None:
                prev = meta.get("previousClose") or meta.get("chartPreviousClose")
            prev = float(prev) if prev else None

            change = round(price - prev, 4) if prev else None
            change_pct = (price / prev - 1) * 100 if prev else None
            mt = meta.get("regularMarketTime")
            t = (datetime.fromtimestamp(mt).strftime("%Y-%m-%d %H:%M")
                 if mt else datetime.now().strftime("%Y-%m-%d %H:%M"))
            return Quote(ticker, price, prev, change, change_pct,
                         source="Yahoo Finance", time=t, series=series)
        except (urllib.error.URLError, TimeoutError, OSError, KeyError,
                IndexError, TypeError, ValueError, json.JSONDecodeError):
            continue
    return None


# ---------------------------------------------------------------------------
# 新浪财经（备份，GBK 编码）
# ---------------------------------------------------------------------------

def _fetch_sina(ticker: str) -> Optional[Quote]:
    url = f"https://hq.sinajs.cn/list=gb_{ticker.lower()}"
    try:
        text = _http_get(url, headers={"Referer": "https://finance.sina.com.cn/"},
                         encoding="gbk")
        body = text.split('"')[1]
        f = body.split(",")
        price = float(f[1])
        pct = float(f[2])
        prev = price - float(f[4]) if len(f) > 4 and f[4] else None
        return Quote(ticker, price, prev, float(f[4]) if len(f) > 4 and f[4] else None,
                     pct, source="新浪财经", time=f[3] if len(f) > 3 else "")
    except (urllib.error.URLError, TimeoutError, OSError, IndexError,
            TypeError, ValueError):
        return None


def fetch_quote(ticker: str) -> Optional[Quote]:
    """获取最新报价（含近一月日线，用于迷你走势图）。"""
    q = _fetch_yahoo(ticker)
    if q is None or q.price <= 0:
        q = _fetch_sina(ticker)
    return q


def fetch_history(ticker: str, rng: str = "10y", interval: str = "1mo") -> list:
    """获取月度/日度历史收盘价：[(datetime, close), ...]。"""
    for host in ("query1", "query2"):
        url = (f"https://{host}.finance.yahoo.com/v8/finance/chart/{ticker}"
               f"?interval={interval}&range={rng}")
        try:
            data = json.loads(_http_get(url))
            result = data["chart"]["result"][0]
            stamps = result.get("timestamp") or []
            closes = (result.get("indicators", {}).get("quote") or [{}])[0].get("close") or []
            out, last = [], None
            for ts, close in zip(stamps, closes):
                if close is None:
                    if last is None:
                        continue
                    close = last          # 缺失值向前填充
                close = float(close)
                last = close
                out.append((datetime.fromtimestamp(ts), close))
            if out:
                return out
        except (urllib.error.URLError, TimeoutError, OSError, KeyError,
                IndexError, TypeError, ValueError, json.JSONDecodeError):
            continue
    return []


class PriceService:
    """简单内存缓存，界面层负责调度刷新。"""

    def __init__(self):
        self.cache: dict = {}
        self.last_update: Optional[datetime] = None
        self.last_error: Optional[str] = None

    def refresh(self, tickers) -> tuple:
        """返回 (成功更新的报价 dict, 错误信息)。"""
        quotes, errors = {}, []
        for t in tickers:
            try:
                q = fetch_quote(t)
            except Exception as exc:  # noqa: BLE001 - 网络层兜底
                q = None
                errors.append(f"{t}: {exc}")
            if q is not None and q.price > 0:
                quotes[t] = q
                self.cache[t] = q
            else:
                errors.append(f"{t} 获取失败")
        if quotes:
            self.last_update = datetime.now()
            self.last_error = "; ".join(errors) or None
        else:
            self.last_error = "; ".join(errors) or "网络请求失败"
        return quotes, self.last_error

    def get(self, ticker: str) -> Optional[Quote]:
        return self.cache.get(ticker)
