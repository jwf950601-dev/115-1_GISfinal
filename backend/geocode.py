"""地理編碼：Nominatim。

實測（2026-11-01）：完整中文門牌用自由文字查詢 6/6 找不到，所以先把地址拆成
「區、路、號」改用結構化查詢；找不到退到只查路名；不像地址就當地標名稱查。
Nominatim 規定整個 App 每秒最多 1 次、要可辨識的 User-Agent、要快取、不可做自動完成。
"""
import re
import threading
import time
from functools import lru_cache

import requests

from . import config

URL = "https://nominatim.openstreetmap.org/search"
# 例：「大安區羅斯福路四段1號」→ 區＝大安區、路＝羅斯福路四段、號＝1（「2之1號」這類格式要另外處理）
ADDRESS = re.compile(r"(?P<district>\S+?區)?(?P<road>\S+?(?:路|街|大道)(?:\S+?段)?(?:\d+巷)?(?:\d+弄)?)(?P<no>\d+)號")

_lock = threading.Lock()
_last_call = [0.0]


def parse_address(text):
    """把地址拆成 {district, road, no}；不像地址回傳 None。"""
    m = ADDRESS.search(text.replace(" ", ""))
    return m.groupdict() if m else None


def _search(params):
    """呼叫 Nominatim；用鎖保證整個 App 每秒最多 1 次。"""
    with _lock:
        wait = 1.0 - (time.time() - _last_call[0])
        if wait > 0:
            time.sleep(wait)
        r = requests.get(URL, params={"format": "jsonv2", "limit": 1, "countrycodes": "tw", **params},
                         headers={"User-Agent": config.NOMINATIM_UA}, timeout=10)
        _last_call[0] = time.time()
    r.raise_for_status()
    return r.json()


def _result(hit, level):
    return {"lat": float(hit["lat"]), "lon": float(hit["lon"]), "display": hit["display_name"], "level": level}


@lru_cache(maxsize=2000)
def geocode(text):
    """回傳 {lat, lon, display, level}；level 是 address（門牌）、road（只到路）、place（地標）。找不到回傳 None。"""
    parts = parse_address(text)
    if parts:
        hits = _search({"street": f"{parts['no']} {parts['road']}", "city": config.CITY_ZH})
        if hits:
            return _result(hits[0], "address")
        hits = _search({"street": parts["road"], "city": config.CITY_ZH})
        if hits:
            return _result(hits[0], "road")
    hits = _search({"q": text})
    return _result(hits[0], "place") if hits else None
