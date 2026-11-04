"""第 5 步（只給 prototype demo 用）：用 OSM 道路、水域、公園畫成簡化底圖。正式網站直接用 OSM 圖磚，不需要這一步。

輸出 work/basemap.json。
"""
import json
import sys
from pathlib import Path

from shapely.geometry import LineString, Polygon

sys.path.insert(0, str(Path(__file__).resolve().parent))
import settings as S

sys.stdout.reconfigure(encoding="utf-8")
osm = json.loads((S.WORK / "osm" / "ways.json").read_text(encoding="utf-8"))
base = json.loads((S.WORK / "osm" / "base.json").read_text(encoding="utf-8"))
city = json.loads((S.WORK / "city_data.json").read_text(encoding="utf-8"))
CLASS = {"primary": 0, "primary_link": 0, "secondary": 0, "secondary_link": 0, "tertiary": 1, "tertiary_link": 1,
         "unclassified": 1, "residential": 1, "living_street": 1, "service": 2, "pedestrian": 2, "footway": 2,
         "cycleway": 2, "path": 2, "steps": 2, "track": 2}


def coords(geom, tol):
    return [[round(y, 5), round(x, 5)] for x, y in geom.simplify(tol, preserve_topology=False).coords]


def ways(data):
    nd = {e["id"]: (e["lon"], e["lat"]) for e in data["elements"] if e["type"] == "node"}
    for e in data["elements"]:
        if e["type"] == "way":
            pts = [nd[n] for n in e["nodes"] if n in nd]
            if len(pts) >= 2:
                yield e, pts


roads = [[], [], []]
for e, pts in ways(osm):
    c = CLASS.get(e.get("tags", {}).get("highway"))
    if c is not None:
        roads[c].append(coords(LineString(pts), 0.00004))
water, rivers, parks = [], [], []
for e, pts in ways(base):
    t = e.get("tags", {})
    closed = e["nodes"][0] == e["nodes"][-1] and len(pts) >= 4
    if t.get("natural") == "water" and closed:
        water.append(coords(Polygon(pts).exterior, 0.00005))
    elif t.get("leisure") == "park" and closed:
        parks.append(coords(Polygon(pts).exterior, 0.00005))
    elif t.get("waterway"):
        rivers.append(coords(LineString(pts), 0.00005))

towns = []
for t in city["towns"]:
    ring = t["rings"][0]
    cx, cy = sum(p[0] for p in ring) / len(ring), sum(p[1] for p in ring) / len(ring)
    if S.BBOX[0] <= cy <= S.BBOX[2] and S.BBOX[1] <= cx <= S.BBOX[3]:
        towns.append({"name": t["name"], "lat": round(cy, 5), "lon": round(cx, 5)})
out = {"roads": roads, "water": water, "rivers": rivers, "coast": [], "parks": parks, "towns": towns,
       "townLines": [[[p[1], p[0]] for p in r] for t in city["towns"] for r in t["rings"]]}
(S.WORK / "basemap.json").write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
print("道路：", [len(r) for r in roads], "；水域：", len(water), "；河川：", len(rivers), "；公園：", len(parks), "；區名：", [t["name"] for t in towns])
