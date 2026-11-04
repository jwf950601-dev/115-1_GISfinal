"""YouBike 即時資料、15 分鐘預估與可靠度。

資料來源的優先順序：
1. 資料庫（GitHub Actions 尖峰每 15 分鐘寫入）：最新快照、預估與可靠度都由歷史計算。
2. 沒有資料庫但有 TDX 金鑰：App 自己抓，所有使用者共用 15 分鐘快取。
3. 兩者都沒有：回傳空的，前端顯示「沒有即時資料」。
"""
import threading
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from . import config, db, tdx

TAIPEI = ZoneInfo("Asia/Taipei")
_cache = {"data": {}, "time": None, "fetched": 0.0, "source": "none"}
_lock = threading.Lock()


def electric(r):
    """可借車數中的電輔車（AvailableRentBikesDetail.ElectricBikes）；沒有這個欄位回傳 None。"""
    d = r.get("AvailableRentBikesDetail")
    if isinstance(d, list):
        d = d[0] if d else None
    return d.get("ElectricBikes") if isinstance(d, dict) else None


def _from_tdx():
    rows = tdx.get_json(f"/v2/Bike/Availability/City/{config.CITY}")
    # 欄位依 TDX Swagger（公共運輸-自行車 v2）：ServiceStatus 0＝停止營運、1＝正常營運、2＝暫停營運
    return {r["StationUID"]: {"rent": r.get("AvailableRentBikes"), "rent_e": electric(r), "ret": r.get("AvailableReturnBikes"),
                              "status": r.get("ServiceStatus"), "update": r.get("UpdateTime")} for r in rows}


def _from_db():
    rows = db.query("""
        select station_uid, rent, rent_e, ret, service_status, update_time, fetched_at
        from bike_snapshot where fetched_at = (select max(fetched_at) from bike_snapshot)""")
    data = {r[0]: {"rent": r[1], "rent_e": r[2], "ret": r[3], "status": r[4], "update": r[5].isoformat() if r[5] else None}
            for r in rows}
    return data, (rows[0][6].astimezone(TAIPEI).isoformat() if rows else None)


def latest():
    """回傳 {StationUID: {rent, ret, status, update}}，以及資料時間與來源。"""
    with _lock:
        if time.time() - _cache["fetched"] < 60 and _cache["data"]:
            return _cache
        try:
            if db.enabled():
                data, t = _from_db()
                _cache.update(data=data, time=t, source="database")
            elif tdx.has_key() and time.time() - _cache["fetched"] > config.LIVE_CACHE_SEC:
                _cache.update(data=_from_tdx(), time=datetime.now(TAIPEI).isoformat(), source="tdx")
            _cache["fetched"] = time.time()
        except Exception as e:                       # 更新失敗：沿用上一份，並讓前端知道
            _cache["error"] = f"{type(e).__name__}: {e}"
        return _cache


def lookup(uid):
    """給路徑分析用：查一個站此刻的可借、可還，以及預估與可靠度。"""
    row = latest()["data"].get(uid)
    if not row:
        return None
    if row["status"] is not None and row["status"] != 1:     # 暫停或停止營運：借不到也還不了
        row = {**row, "rent": 0, "rent_e": 0, "ret": 0}
    return {**row, "rent_15": forecast(uid, "rent", row["rent"]), "ret_15": forecast(uid, "ret", row["ret"])}


def forecast(uid, field, now_value, minutes=15):
    """15 分鐘後預估＝現在值＋過去 14 天平日同一時段、15 分鐘內的平均變化。沒有資料庫回傳 None。"""
    if not db.enabled() or now_value is None:
        return None
    col = "rent" if field == "rent" else "ret"
    rows = db.query(f"""
        with s as (
          select fetched_at, {col} as v,
                 lead({col}) over (order by fetched_at) as v_next,
                 lead(fetched_at) over (order by fetched_at) as t_next
          from bike_snapshot
          where station_uid = %s and fetched_at > now() - interval '14 days'
            and extract(isodow from fetched_at at time zone 'Asia/Taipei') <= 5)
        select avg(v_next - v) from s
        where t_next - fetched_at between interval '10 minutes' and interval '20 minutes'
          and abs(extract(epoch from (fetched_at at time zone 'Asia/Taipei')::time
                  - (now() at time zone 'Asia/Taipei')::time)) <= 15 * 60""", (uid,))
    change = rows[0][0] if rows and rows[0][0] is not None else 0
    return max(0, round(now_value + float(change)))


def reliability(borrow_uid, return_uid):
    """過去 14 天平日同一時段（±15 分鐘），借車站可借 ≥ 1 且還車站可還 ≥ 1 的比例。"""
    if not db.enabled():
        return None
    rows = db.query("""
        select avg(case when b.rent >= 1 and r.ret >= 1 then 1.0 else 0.0 end), count(*)
        from bike_snapshot b join bike_snapshot r on r.fetched_at = b.fetched_at
        where b.station_uid = %s and r.station_uid = %s and b.fetched_at > now() - interval '14 days'
          and extract(isodow from b.fetched_at at time zone 'Asia/Taipei') <= 5
          and abs(extract(epoch from (b.fetched_at at time zone 'Asia/Taipei')::time
                  - (now() at time zone 'Asia/Taipei')::time)) <= 15 * 60""", (borrow_uid, return_uid))
    share, n = rows[0]
    return {"share": float(share), "samples": n} if n else None
