"""第 4 步：機車路網（App 在伺服器上跑 Dijkstra）、每個路口目前最快往返車站的時間、OSM 公車站牌。

輸出 app/v3_data.json。機車速度依道路等級假設，不考慮號誌與單行道。
"""
import json
import math
import sys
from pathlib import Path

import networkx as nx
import numpy as np
from pyproj import Transformer
from scipy.spatial import cKDTree

sys.path.insert(0, str(Path(__file__).resolve().parent))
import settings as S

sys.stdout.reconfigure(encoding="utf-8")
R = json.loads((S.APP / "route_data.json").read_text(encoding="utf-8"))
OSM = json.loads((S.WORK / "osm" / "ways.json").read_text(encoding="utf-8"))
to3826 = Transformer.from_crs("EPSG:4326", "EPSG:3826", always_xy=True)

SPEED = {"primary": 30, "primary_link": 30, "secondary": 30, "secondary_link": 30, "tertiary": 25, "tertiary_link": 25,
         "unclassified": 25, "residential": 18, "living_street": 15, "service": 15}   # 公里／小時
nodes = {e["id"]: (e["lon"], e["lat"]) for e in OSM["elements"] if e["type"] == "node"}
ids = list(nodes)
xs, ys = to3826.transform([nodes[i][0] for i in ids], [nodes[i][1] for i in ids])
XY = dict(zip(ids, zip(xs, ys)))
road = nx.Graph()
for w in (e for e in OSM["elements"] if e["type"] == "way"):
    t = w.get("tags", {})
    v = SPEED.get(t.get("highway"))
    if v is None or t.get("motorcycle") == "no" or t.get("motor_vehicle") == "no":
        continue
    for a, b in zip(w["nodes"], w["nodes"][1:]):
        if a in XY and b in XY:
            road.add_edge(a, b, sec=math.dist(XY[a], XY[b]) / (v / 3.6))
rn = list(road.nodes)
r_idx = {n: k for k, n in enumerate(rn)}
edges = []
for a, b, sec in road.edges(data="sec"):
    edges += [r_idx[a], r_idx[b], max(1, round(sec * 10))]        # 0.1 秒
print("機車路網：", len(rn), "節點、", len(edges) // 3, "路段")

# 每個路口目前最快往返車站的時間（走路或 YouBike），給「增設 YouBike 站」比較用
N = len(R["lat"])
node_xy = np.c_[to3826.transform(R["lon"], R["lat"])]
bikes = R["bikes"]
bxy = np.c_[to3826.transform([b["lon"] for b in bikes], [b["lat"] for b in bikes])]
bkd = cKDTree(bxy)
best = []
for i in range(N):
    walk = R["wd"][i] / 80 if R["wd"][i] >= 0 else math.inf
    bike = math.inf
    for k in bkd.query_ball_point(node_xy[i], 500):
        b = bikes[k]
        if b["node"] < 0 or R["bd"][b["node"]] < 0:
            continue
        src = bikes[R["bs"][b["node"]]]
        bike = min(bike, math.dist(node_xy[i], bxy[k]) * R["detour"] / 80 + R["bd"][b["node"]] / 250 + src["std"] / 80 + 2)
    v = min(walk, bike)
    best.append(round(v * 10) if v < math.inf else -1)
print("最快 ≤ 20 分鐘可到車站的路口比例：", round(np.mean([0 <= v <= 200 for v in best]), 3))

stops = [{"name": e.get("tags", {}).get("name", "未命名站牌"), "lat": round(e["lat"], 6), "lon": round(e["lon"], 6)}
         for e in json.loads((S.WORK / "osm" / "busstops.json").read_text(encoding="utf-8"))["elements"]]
print("公車站牌：", len(stops))
r_lon, r_lat = zip(*(nodes[n] for n in rn))
out = {"road": {"lat": [round(v, 5) for v in r_lat], "lon": [round(v, 5) for v in r_lon], "e": edges}, "best": best, "stops": stops}
(S.APP / "v3_data.json").write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
print("輸出：", S.APP / "v3_data.json")
