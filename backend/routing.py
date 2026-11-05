"""路徑分析。

步行、自行車：查前處理算好的「最短路徑樹」（每個路口記到最近車站多遠、往車站方向的下一個路口），
所以任意地點都能立刻得到路線，伺服器不必放整個步行路網。
機車：機車路網較小（約 2.5 萬個路口），直接在伺服器上跑 Dijkstra。
大眾運輸一段＝最初一哩（走路／YouBike／公車）＋ 軌道 ＋ 最後一哩。
"""
import heapq
import json
import math
from functools import lru_cache

import numpy as np
from scipy.spatial import cKDTree

from . import config, safety

WALK, BIKE, DOCK = config.WALK_M_PER_MIN, config.BIKE_M_PER_MIN, config.DOCK_MIN
# 簡易平面座標（公尺）：只用來找最近點、量幾百公尺內的距離；正式距離都在前處理用 EPSG:3826 算好
KX = 111320 * math.cos(math.radians(25.04))
KY = 110540


def meters(la1, lo1, la2, lo2):
    return math.hypot((lo2 - lo1) * KX, (la2 - la1) * KY)


def _xy(lat, lon):
    return [lon * KX, lat * KY]


@lru_cache(maxsize=1)
def data():
    """第一次用到時才讀檔，之後所有請求共用（測試時不會被迫讀大檔）。"""
    R = json.loads((config.APP_DATA / "route_data.json").read_text(encoding="utf-8"))
    V = json.loads((config.APP_DATA / "v3_data.json").read_text(encoding="utf-8"))
    lat, lon = np.array(R["lat"]), np.array(R["lon"])
    pts = np.c_[lon * KX, lat * KY]
    walk_idx = np.where(np.array(R["wd"]) >= 0)[0]
    road = V["road"]
    adj = [[] for _ in road["lat"]]
    e = road["e"]
    for k in range(0, len(e), 3):
        u, v, t = e[k], e[k + 1], e[k + 2] / 10
        adj[u].append((v, t))
        adj[v].append((u, t))
    return {
        "R": R, "V": V, "walk_idx": walk_idx, "walk_kd": cKDTree(pts[walk_idx]),
        "bikes_kd": cKDTree([_xy(b["lat"], b["lon"]) for b in R["bikes"]]),
        "stops_kd": cKDTree([_xy(s["lat"], s["lon"]) for s in V["stops"]]),
        "road_kd": cKDTree(np.c_[np.array(road["lon"]) * KX, np.array(road["lat"]) * KY]),
        "adj": adj,
    }


def in_area(lat, lon):
    s, w, n, e = data()["R"]["bbox"]
    return s <= lat <= n and w <= lon <= e


def _chain(i, key):
    """沿著最短路徑樹的「下一個路口」走到樹根（車站或車站端 YouBike）。"""
    R = data()["R"]
    pts, guard = [[R["lat"][i], R["lon"][i]]], 0
    while R[key][i] != i and guard < 20000:
        i = R[key][i]
        pts.append([R["lat"][i], R["lon"][i]])
        guard += 1
    return pts, i


# ---------- 某個地點與最近車站之間的三種方式 ----------
@lru_cache(maxsize=512)
def plan_point(lat, lon):
    d = data()
    R, V = d["R"], d["V"]
    dist, k = d["walk_kd"].query(_xy(lat, lon))
    i = int(d["walk_idx"][k])
    pts, end = _chain(i, "wn")
    wdist = R["wd"][i] + dist * R["detour"]
    walk = {"mins": wdist / WALK, "dist": wdist, "station": R["ws"][end], "pts": pts[::-1] + [[lat, lon]]}

    bike = None
    for k in d["bikes_kd"].query_ball_point(_xy(lat, lon), 500):
        b = R["bikes"][k]
        if b["node"] < 0 or R["bd"][b["node"]] < 0:
            continue
        src_k = R["bs"][b["node"]]
        home_leg = meters(lat, lon, b["lat"], b["lon"]) * R["detour"]
        ride, st_leg = R["bd"][b["node"]], R["bikes"][src_k]["std"]
        mins = (home_leg + st_leg) / WALK + ride / BIKE + DOCK
        if bike is None or mins < bike["mins"]:
            bike = {"mins": mins, "near": k, "src": src_k, "home_leg": home_leg, "ride": ride, "st_leg": st_leg,
                    "station": R["bikes"][src_k]["st"]}
    if bike:
        bike["pts"] = _chain(R["bikes"][bike["near"]]["node"], "bn")[0][::-1]

    st = R["stations"][walk["station"]]
    def near(la, lo, r):
        ks = d["stops_kd"].query_ball_point(_xy(la, lo), r)
        out = [{**V["stops"][k], "d": meters(la, lo, V["stops"][k]["lat"], V["stops"][k]["lon"])} for k in ks]
        return sorted(out, key=lambda s: s["d"])
    st_stops = near(st["lat"], st["lon"], 250)[:4] or near(st["lat"], st["lon"], 600)[:2]
    point_stops = near(lat, lon, 400)
    bus = None
    if st_stops and point_stops:
        s0, ps = st_stops[0], point_stops[0]
        ride = meters(s0["lat"], s0["lon"], ps["lat"], ps["lon"]) * 1.3 / config.BUS_M_PER_MIN
        bus = {"mins": s0["d"] / WALK + ride + ps["d"] * R["detour"] / WALK, "station_stop": s0, "point_stop": ps,
               "ride": ride, "station": walk["station"]}
    return {"walk": walk, "bike": bike, "bus": bus}


# ---------- 機車 ----------
@lru_cache(maxsize=512)
def moto(a_lat, a_lon, b_lat, b_lon):
    d = data()
    road = d["V"]["road"]
    da, s = d["road_kd"].query(_xy(a_lat, a_lon))
    db, t = d["road_kd"].query(_xy(b_lat, b_lon))
    dist, prev, heap = {s: 0.0}, {}, [(0.0, s)]
    while heap:
        du, u = heapq.heappop(heap)
        if u == t:
            break
        if du > dist[u]:
            continue
        for v, w in d["adj"][u]:
            nd = du + w
            if nd < dist.get(v, math.inf):
                dist[v], prev[v] = nd, u
                heapq.heappush(heap, (nd, v))
    if t not in dist:
        return None
    path, v = [], t
    while v != s:
        path.append([road["lat"][v], road["lon"][v]])
        v = prev[v]
    path.append([road["lat"][s], road["lon"][s]])
    mins = dist[t] / 60 + config.MOTO_PARK_MIN + (da + db) / WALK
    path = path[::-1]
    km = sum(meters(*p, *q) for p, q in zip(path, path[1:])) / 1000
    return {"mins": mins, "km": km, "path": [[a_lat, a_lon]] + path + [[b_lat, b_lon]]}


# ---------- 軌道（估計值；正式版改用 TDX 時刻表）----------
def rail_leg(A, B):
    shared = next((s for s in A["sys"] if s in B["sys"]), None)
    wait = min(config.RAIL_WAIT_MIN.get(s, 8) for s in A["sys"])
    km = meters(A["lat"], A["lon"], B["lat"], B["lon"]) * 1.25 / 1000
    ride = km * 1000 / config.RAIL_M_PER_MIN
    transfer = 0 if shared else config.TRANSFER_MIN
    # 轉乘時不知道兩個系統各坐多遠，取係數較高的那個（保守估計）
    g = config.CARBON_G_PER_KM
    factor = g.get(shared, 60) if shared else max(g.get(A["sys"][0], 60), g.get(B["sys"][0], 60))
    return {"from": A["name"], "to": B["name"], "sys": shared or f"{A['sys'][0]}轉{B['sys'][0]}",
            "wait": wait, "ride": ride, "transfer": transfer, "mins": wait + ride + transfer,
            "km": km, "co2": km * factor}


# ---------- 整趟行程 ----------
def _pick(opts, choice, rain):
    if choice in opts:
        return choice
    if rain and "bus" in opts:
        return "bus"
    return "bike" if "bike" in opts and opts["bike"]["mins"] < opts["walk"]["mins"] else "walk"


def _mile(p, mode, role, live):
    """一段最初（role=first：地點→車站）或最後（role=last：車站→地點）一哩的細節。"""
    R = data()["R"]
    m = p[mode]
    out = {"mode": mode, "mins": m["mins"], "options": {k: round(v["mins"], 1) for k, v in p.items() if v}}
    if mode == "walk":
        out.update(dist=m["dist"], pts=m["pts"], co2=0, slow=safety.profile(m["pts"], "walk"))
    elif mode == "bike":
        near, src = R["bikes"][m["near"]], R["bikes"][m["src"]]
        borrow, give = (near, src) if role == "first" else (src, near)
        info = lambda b: {"uid": b["uid"], "name": b["name"], "lat": b["lat"], "lon": b["lon"], **(live(b["uid"]) or {})}
        out.update(borrow=info(borrow), give=info(give), ride=m["ride"], pts=m["pts"],
                   walk_before=m["home_leg"] if role == "first" else m["st_leg"],
                   walk_after=m["st_leg"] if role == "first" else m["home_leg"],
                   co2=0, slow=safety.profile(m["pts"], "bike"))
    else:
        board, alight = (m["point_stop"], m["station_stop"]) if role == "first" else (m["station_stop"], m["point_stop"])
        km = m["ride"] * config.BUS_M_PER_MIN / 1000
        out.update(board=board, alight=alight, ride=m["ride"], co2=km * config.CARBON_G_PER_KM["公車"])
    return out


def trip(points, choices=None, rain=False, live=lambda uid: None):
    """points：[{lat, lon, label}, ...]（至少 2 個）；choices：{"0a": "bike", "0b": "bus", ...}。"""
    R = data()["R"]
    choices = choices or {}
    legs = []
    for k, (a, b) in enumerate(zip(points, points[1:])):
        leg = {"k": k, "from": a, "to": b, "moto": moto(a["lat"], a["lon"], b["lat"], b["lon"])}
        if not (in_area(a["lat"], a["lon"]) and in_area(b["lat"], b["lon"])):
            legs.append({**leg, "error": "起點或終點不在研究範圍內"})
            continue
        pa = {m: v for m, v in plan_point(a["lat"], a["lon"]).items() if v}
        pb = {m: v for m, v in plan_point(b["lat"], b["lon"]).items() if v}
        ca, cb = _pick(pa, choices.get(f"{k}a"), rain), _pick(pb, choices.get(f"{k}b"), rain)
        A, B = R["stations"][pa[ca]["station"]], R["stations"][pb[cb]["station"]]
        direct = meters(a["lat"], a["lon"], b["lat"], b["lon"]) * R["detour"]
        first, last = _mile(pa, ca, "first", live), _mile(pb, cb, "last", live)
        # 每段首末哩的兩端（起點→車站、車站→終點）：前端用來畫往返 YouBike 站或公車站的步行
        first["ends"] = [[a["lat"], a["lon"]], [A["lat"], A["lon"]]]
        last["ends"] = [[B["lat"], B["lon"]], [b["lat"], b["lon"]]]
        rail = None if A is B else rail_leg(A, B)
        mile = first["mins"] + last["mins"]
        moto_co2 = leg["moto"]["km"] * config.CARBON_G_PER_KM["機車"] if leg["moto"] else 0
        if rail is None or direct / WALK <= mile + rail["mins"]:
            legs.append({**leg, "direct": True, "dist": direct, "total": direct / WALK, "mile": direct / WALK, "ride": 0,
                         "co2": 0, "moto_co2": moto_co2})
        else:
            legs.append({**leg, "direct": False, "first": first, "rail": rail, "last": last,
                         "mile": mile, "ride": rail["mins"], "total": mile + rail["mins"],
                         "co2": first["co2"] + rail["co2"] + last["co2"], "moto_co2": moto_co2})
    ok = [l for l in legs if "error" not in l]
    co2, moto_co2 = sum(l["co2"] for l in ok), sum(l["moto_co2"] for l in ok)
    return {
        "legs": legs,
        "total": sum(l["total"] for l in ok), "mile": sum(l["mile"] for l in ok), "ride": sum(l["ride"] for l in ok),
        "moto": sum(l["moto"]["mins"] for l in legs if l["moto"]),
        "carbon": {"transit_g": round(co2), "moto_g": round(moto_co2), "saved_g": round(moto_co2 - co2),
                   "draft": list(config.CARBON_TODO)},
    }
