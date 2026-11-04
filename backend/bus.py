"""公車預估到站：使用者按了「查到站時間」才查那一站，結果快取 60 秒。

注意點數：呼叫次數＝使用者查詢次數（扣掉快取命中），要在報告裡另外估算。
TODO：
1. 站牌要改用 TDX `/v2/Bus/Stop/City/Taipei`（目前 demo 用 OSM 站牌，沒有 TDX 的 StopUID）。
2. 用自己的呼叫確認預估到站 API 的欄位（EstimateTime 單位是秒、StopStatus 各值意義）。
"""
import threading
import time

from . import config, tdx

_cache = {}
_lock = threading.Lock()


def eta(stop_uid):
    with _lock:
        hit = _cache.get(stop_uid)
        if hit and time.time() - hit["fetched"] < 60:
            return hit
    rows = tdx.get_json(f"/v2/Bus/EstimatedTimeOfArrival/City/{config.CITY}",
                        {"$filter": f"StopUID eq '{stop_uid}'",
                         "$select": "RouteName,Direction,EstimateTime,StopStatus"})
    arrivals = sorted(
        [{"route": r["RouteName"]["Zh_tw"], "minutes": round(r["EstimateTime"] / 60)}
         for r in rows if r.get("EstimateTime") is not None],
        key=lambda a: a["minutes"])
    result = {"stop_uid": stop_uid, "arrivals": arrivals, "fetched": time.time()}
    with _lock:
        _cache[stop_uid] = result
    return result
