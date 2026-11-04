"""即時雨量：中央氣象署開放資料平臺。

TODO：資料集代碼與欄位以平臺 Swagger 為準（opendata.cwa.gov.tw）；以下假設自動雨量站資料集
與 records.Station[].GeoInfo.Coordinates / RainfallElement.Past1hr 的結構，第一次呼叫後要核對。
"""
import math
import threading
import time

import requests

from . import config, db

URL = "https://opendata.cwa.gov.tw/api/v1/rest/datastore/{dataset}"
DATASET = "O-A0002-001"   # TODO：確認是自動雨量站即時資料
RAIN_THRESHOLD_MM = 0.5   # 過去 1 小時雨量超過這個值，就當作「正在下雨」

_cache = {"stations": [], "fetched": 0.0}
_lock = threading.Lock()


def _parse(j):
    out = []
    for s in j.get("records", {}).get("Station", []):
        try:
            coord = next(c for c in s["GeoInfo"]["Coordinates"] if c.get("CoordinateName") == "WGS84")
            rain = float(s["RainfallElement"]["Past1hr"]["Precipitation"])
        except (KeyError, StopIteration, ValueError, TypeError):
            continue
        if rain < 0:              # 氣象署用負值表示儀器異常或無資料
            continue
        out.append({"id": s.get("StationId"), "lat": float(coord["StationLatitude"]),
                    "lon": float(coord["StationLongitude"]), "rain_mm": rain})
    return out


def stations():
    """所有雨量站最新的過去 1 小時雨量；10 分鐘快取。沒有金鑰回傳空清單。"""
    with _lock:
        if time.time() - _cache["fetched"] < 600:
            return _cache["stations"]
        if config.CWA_API_KEY:
            r = requests.get(URL.format(dataset=DATASET), params={"Authorization": config.CWA_API_KEY, "format": "JSON"}, timeout=20)
            r.raise_for_status()
            _cache["stations"] = _parse(r.json())
        _cache["fetched"] = time.time()
        return _cache["stations"]


def rain_at(lat, lon):
    """最近雨量站的雨量（之後可改成反距離加權）；沒有資料回傳 None。"""
    st = stations()
    if not st:
        return None
    s = min(st, key=lambda x: math.hypot(x["lat"] - lat, x["lon"] - lon))
    return {"station": s["id"], "rain_mm": s["rain_mm"], "raining": s["rain_mm"] >= RAIN_THRESHOLD_MM}
