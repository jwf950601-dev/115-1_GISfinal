"""FastAPI 主程式：API 與前端網頁都由這個服務提供。

本機啟動：uvicorn backend.main:app --reload，然後開 http://127.0.0.1:8000
"""
import requests
from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import bus, config, geocode, live, routing, safety, tdx, weather

app = FastAPI(title="Last Mile 綠行臺北 API")


class Point(BaseModel):
    lat: float
    lon: float
    label: str = ""


class TripRequest(BaseModel):
    points: list[Point] = Field(min_length=2, max_length=5)   # 出發地、最多 3 個中繼站、目的地
    choices: dict[str, str] = {}                              # 例：{"0a": "bike", "0b": "bus"}
    rain: bool | None = None                                  # None＝依即時雨量自動判斷


@app.get("/api/health")
def health():
    return {"ok": True, "tdx_key": tdx.has_key(), "database": bool(config.DATABASE_URL), "cwa_key": bool(config.CWA_API_KEY)}


@app.get("/api/geocode")
def api_geocode(q: str = Query(min_length=2, max_length=100)):
    """備用：前端已改成瀏覽器直接查 Nominatim（Render 的 IP 會被擋），這支留給本機測試。"""
    try:
        hit = geocode.geocode(q.strip())
    except requests.RequestException as e:
        code = getattr(e.response, "status_code", None) or type(e).__name__
        raise HTTPException(502, f"Nominatim 連線失敗（{code}），請改在地圖上點選位置")
    if hit is None:
        raise HTTPException(404, "找不到這個地址，請改在地圖上點選位置")
    if not routing.in_area(hit["lat"], hit["lon"]):
        raise HTTPException(422, "這個位置不在研究範圍內")
    return hit                       # 地址只用來計算，不寫進資料庫、不記錄


@app.post("/api/trip")
def api_trip(req: TripRequest):
    pts = [p.model_dump() for p in req.points]
    rain = req.rain
    if rain is None:
        r = weather.rain_at(pts[0]["lat"], pts[0]["lon"])
        rain = bool(r and r["raining"])

    def info(uid):
        return live.lookup(uid)

    result = routing.trip(pts, req.choices, rain, info)
    for leg in result["legs"]:                       # 用 YouBike 的段落附上可靠度
        for end in ("first", "last"):
            m = leg.get(end)
            if m and m["mode"] == "bike":
                m["reliability"] = live.reliability(m["borrow"]["uid"], m["give"]["uid"])
    meta = live.latest()
    result["meta"] = {"rain": rain, "live_time": meta.get("time"), "live_source": meta.get("source"),
                      "live_error": meta.get("error")}
    return result


@app.get("/api/weather")
def api_weather(lat: float, lon: float):
    return weather.rain_at(lat, lon) or {"rain_mm": None, "raining": False}


@app.get("/api/bus/eta")
def api_bus_eta(stop_uid: str = Query(min_length=3, max_length=40)):
    if not tdx.has_key():
        raise HTTPException(503, "伺服器沒有設定 TDX 金鑰")
    return bus.eta(stop_uid)


@app.get("/api/stations")
def api_stations():
    R = routing.data()["R"]
    return {"stations": R["stations"], "bbox": R["bbox"]}


@app.get("/api/layers")
def api_layers():
    """慢行路網（人行道、自行車道）與涉及行人／自行車的事故點，前端開圖層時才抓一次。"""
    return safety.layers()


# 前端網頁（放在最後，才不會蓋掉 /api 路徑）
app.mount("/", StaticFiles(directory=config.FRONTEND, html=True), name="frontend")
