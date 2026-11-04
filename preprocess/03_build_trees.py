"""第 3 步：步行與自行車的最短路徑樹（從所有軌道車站同時出發）。

每個路口記錄：到最近車站的步行距離、往車站方向的下一個路口；自行車樹則從「車站 350 m 內的 YouBike 站」出發。
App 查任意地點時，只要沿著「下一個路口」走到樹根，就得到路線。輸出 app/route_data.json。
"""
import json
import math
import random
import sys
from pathlib import Path

import networkx as nx
import numpy as np
from pyproj import Transformer
from scipy.spatial import cKDTree

sys.path.insert(0, str(Path(__file__).resolve().parent))
import settings as S

sys.stdout.reconfigure(encoding="utf-8")
OSM = json.loads((S.WORK / "osm" / "ways.json").read_text(encoding="utf-8"))
CITY = json.loads((S.WORK / "city_data.json").read_text(encoding="utf-8"))
EXAMPLES = json.loads((S.WORK / "osm" / "examples.json").read_text(encoding="utf-8"))
to3826 = Transformer.from_crs("EPSG:4326", "EPSG:3826", always_xy=True)

nodes = {e["id"]: (e["lat"], e["lon"]) for e in OSM["elements"] if e["type"] == "node"}
ids = list(nodes)
xs, ys = to3826.transform([nodes[i][1] for i in ids], [nodes[i][0] for i in ids])
XY = dict(zip(ids, zip(xs, ys)))

NO_BIKE = {"footway", "steps", "pedestrian", "corridor", "elevator"}
walk, bike = nx.Graph(), nx.Graph()        # 簡化：不考慮單行道
for w in (e for e in OSM["elements"] if e["type"] == "way"):
    t = w.get("tags", {})
    hw = t.get("highway")
    walk_ok = t.get("foot") != "no"
    bike_ok = t.get("bicycle") != "no" and (hw not in NO_BIKE or t.get("bicycle") in ("yes", "designated"))
    for a, b in zip(w["nodes"], w["nodes"][1:]):
        if a in XY and b in XY:
            d = math.dist(XY[a], XY[b])
            if walk_ok:
                walk.add_edge(a, b, length=d)
            if bike_ok:
                bike.add_edge(a, b, length=d)
print("步行路網：", walk.number_of_nodes(), "；自行車路網：", bike.number_of_nodes())


def snap(graph, lonlat):
    gn = list(graph.nodes)
    kd = cKDTree(np.array([XY[n] for n in gn]))
    x, y = to3826.transform([p[0] for p in lonlat], [p[1] for p in lonlat])
    d, i = kd.query(np.c_[x, y])
    return [gn[k] for k in i], d


def tree(graph, sources, cutoff):
    """虛擬起點連到所有來源（長度 0），跑一次 Dijkstra＝多源最短路徑。"""
    g = graph.copy()
    for n in sources:
        g.add_edge("SRC", n, length=0)
    pred, dist = nx.dijkstra_predecessor_and_distance(g, "SRC", cutoff=cutoff, weight="length")
    dist.pop("SRC")
    return dist, {n: (n if pred[n][0] == "SRC" else pred[n][0]) for n in dist}


m = 0.01
inb = lambda lat, lon, mm=m: S.BBOX[0] - mm <= lat <= S.BBOX[2] + mm and S.BBOX[1] - mm <= lon <= S.BBOX[3] + mm
st_idx = [i for i, s in enumerate(CITY["stations"]) if inb(s["lat"], s["lon"])]
stations = [CITY["stations"][i] for i in st_idx]
st_nodes, st_snap = snap(walk, [(s["lon"], s["lat"]) for s in stations])
print("車站：", len(stations), "；吸附距離中位數", round(float(np.median(st_snap)), 1), "m")
wd, wn = tree(walk, set(st_nodes), 3000)
node2station = {}
for k, n in enumerate(st_nodes):
    node2station.setdefault(n, k)

b_idx = [i for i, b in enumerate(CITY["bikes"]) if inb(b[3], b[4], 0.004)]
bikes = [CITY["bikes"][i] for i in b_idx]
old2new = {o: k for k, o in enumerate(b_idx)}
station_side = {}
for k, si in enumerate(st_idx):
    for bi, d in CITY["pairs"][si]:
        if d <= S.STATION_SIDE_M and bi in old2new:
            nb = old2new[bi]
            if nb not in station_side or d < station_side[nb][1]:
                station_side[nb] = (k, d)
b_nodes, _ = snap(bike, [(b[4], b[3]) for b in bikes])
src_nodes = {b_nodes[k]: k for k in station_side}
bd, bn = tree(bike, set(src_nodes), 6000)
bsrc = {}
for n in sorted(bd, key=bd.get):
    bsrc[n] = src_nodes[n] if bn[n] == n else bsrc[bn[n]]
print("YouBike：", len(bikes), "站；車站端", len(station_side), "站")

random.seed(1)
ratios = []
for n in random.sample(list(wd), min(3000, len(wd))):
    j = n
    while wn[j] != j:
        j = wn[j]
    s = math.dist(XY[n], XY[j])
    if s > 200:
        ratios.append(wd[n] / s)
detour = float(np.median(ratios))
print("繞路係數中位數：", round(detour, 3))

keep = sorted(set(wd) | set(bd), key=lambda n: (nodes[n][0], nodes[n][1]))
idx = {n: k for k, n in enumerate(keep)}
out = {
    "bbox": S.BBOX, "detour": round(detour, 3),
    "lat": [round(nodes[n][0], 5) for n in keep], "lon": [round(nodes[n][1], 5) for n in keep],
    "wd": [round(wd[n]) if n in wd else -1 for n in keep], "wn": [idx[wn[n]] if n in wd else -1 for n in keep],
    "ws": [node2station.get(n, -1) for n in keep],
    "bd": [round(bd[n]) if n in bd else -1 for n in keep], "bn": [idx[bn[n]] if n in bd else -1 for n in keep],
    "bs": [bsrc[n] if n in bd else -1 for n in keep],
    "stations": [{"name": s["name"], "sys": s["sys"], "town": s["town"], "lat": s["lat"], "lon": s["lon"]} for s in stations],
    "bikes": [{"uid": b[0], "name": b[1], "cap": b[2], "lat": b[3], "lon": b[4], "node": idx.get(b_nodes[k], -1),
               "st": station_side.get(k, (-1, -1))[0], "std": station_side.get(k, (-1, -1))[1]} for k, b in enumerate(bikes)],
    "examples": [{"label": q, "lat": float(h["lat"]), "lon": float(h["lon"]), "display": h["display_name"]}
                 for q, h in EXAMPLES.items() if h and inb(float(h["lat"]), float(h["lon"]), 0)],
}
assert all(wd[n] == 0 for n in st_nodes)
S.APP.mkdir(parents=True, exist_ok=True)
(S.APP / "route_data.json").write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
(S.WORK / "route_node_ids.json").write_text(json.dumps(keep), encoding="utf-8")
reach = np.array([v for v in out["wd"] if v >= 0])
print("輸出節點：", len(keep), "；步行 800 m 內的路口比例：", round(float((reach <= 800).mean()), 3))
print("示範地點：", [e["label"] for e in out["examples"]])
