"""尖峰時段由 GitHub Actions 每 15 分鐘執行一次：抓 YouBike 即時車位與雨量，寫進資料庫。

全系統只有這支程式定時呼叫 TDX，所以每月點數與 App 有多少人使用無關。
本機測試：python -m fetcher.fetch_snapshot（需要 .env 裡的金鑰與 DATABASE_URL）
"""
from datetime import datetime
from zoneinfo import ZoneInfo

from backend import config, db, tdx, weather
from backend.live import electric

TAIPEI = ZoneInfo("Asia/Taipei")


def main():
    if not (tdx.has_key() and db.enabled()):
        raise SystemExit("缺少 TDX 金鑰或 DATABASE_URL，請在 GitHub Secrets 設定")
    now = datetime.now(TAIPEI)

    path = f"/v2/Bike/Availability/City/{config.CITY}"
    rows = tdx.get_json(path)
    db.execute_many(
        "insert into bike_snapshot (fetched_at, station_uid, rent, rent_e, ret, service_status, update_time) "
        "values (%s, %s, %s, %s, %s, %s, %s) on conflict do nothing",
        [(now, r["StationUID"], r.get("AvailableRentBikes"), electric(r), r.get("AvailableReturnBikes"),
          r.get("ServiceStatus"), r.get("UpdateTime")) for r in rows])
    log = tdx.call_log[-1]
    db.execute_many("insert into api_log (called_at, source, path, n_records, bytes) values (%s, %s, %s, %s, %s)",
                    [(now, "tdx", path, len(rows), log["bytes"])])
    print(f"{now:%Y-%m-%d %H:%M} YouBike：{len(rows)} 站")

    if config.CWA_API_KEY:
        st = weather.stations()
        db.execute_many("insert into rain_snapshot (fetched_at, station_id, lat, lon, rain_mm) "
                        "values (%s, %s, %s, %s, %s) on conflict do nothing",
                        [(now, s["id"], s["lat"], s["lon"], s["rain_mm"]) for s in st])
        print(f"雨量站：{len(st)} 站")


if __name__ == "__main__":
    main()
