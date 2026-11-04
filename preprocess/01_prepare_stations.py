"""第 1 步：軌道車站（100 m 內共站合併）、YouBike 站點、車站 × 站點對照表、行政區底圖。

輸出 work/city_data.json。所有距離都在 EPSG:3826（公尺）下計算。
"""
import json
import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import settings as S

sys.stdout.reconfigure(encoding="utf-8")
S.WORK.mkdir(parents=True, exist_ok=True)


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def to_gdf(rows, sys_name):
    df = pd.json_normalize(rows)
    return gpd.GeoDataFrame(
        {"系統": sys_name, "StationID": df["StationID"], "站名": df["StationName.Zh_tw"]},
        geometry=gpd.points_from_xy(df["StationPosition.PositionLon"], df["StationPosition.PositionLat"]),
        crs="EPSG:4326")


# ---------- 軌道車站 ----------
parts = []
for path, name in S.RAIL_FILES:
    data = load(path)
    rows = data["Stations"] if isinstance(data, dict) else data      # 臺鐵 v3 回傳 dict，車站在 Stations 裡
    parts.append(to_gdf(rows, name))
st = pd.concat(parts, ignore_index=True)
st = st[~st["站名"].str.contains("|".join(S.EXCLUDE_NAMES), regex=True)]

town = gpd.read_file(S.TOWN_SHP)
st = st.to_crs(town.crs)
st = gpd.sjoin(st, town[["COUNTYNAME", "TOWNNAME", "geometry"]], how="left", predicate="within").drop(columns="index_right")
city = st[st["COUNTYNAME"] == S.CITY_NAME].reset_index(drop=True)
print(f"{S.CITY_NAME}軌道點位：", len(city), city["系統"].value_counts().to_dict())

# 相距 MERGE_M 公尺內合併成一站；代表點依 SYSTEM_ORDER
circle = city[["geometry"]].copy()
circle["geometry"] = city.buffer(S.MERGE_M)
pairs = gpd.sjoin(city[["geometry"]], circle, predicate="within")
city["群組"] = pairs.groupby(level=0)["index_right"].min()
city["序"] = city["系統"].map(S.SYSTEM_ORDER)
rows = []
for _, grp in city.sort_values(["序", "StationID"]).groupby("群組"):
    rep = grp.iloc[0]
    rows.append({"id": rep["StationID"], "name": rep["站名"], "sys": sorted(set(grp["系統"]), key=S.SYSTEM_ORDER.get),
                 "names": list(dict.fromkeys(grp["站名"])), "codes": sorted(set(grp["StationID"])),
                 "town": rep["TOWNNAME"], "geometry": rep.geometry})
stations = gpd.GeoDataFrame(rows, crs=city.crs)
print("合併後車站：", len(stations))

# ---------- YouBike 站點 ----------
raw = pd.json_normalize(load(S.BIKE_FILE))
bike = gpd.GeoDataFrame(
    {"uid": raw["StationUID"], "name": raw["StationName.Zh_tw"].str.replace("YouBike2.0_", "", regex=False),
     "cap": raw["BikesCapacity"].fillna(0).astype(int)},
    geometry=gpd.points_from_xy(raw["StationPosition.PositionLon"], raw["StationPosition.PositionLat"]),
    crs="EPSG:4326").to_crs(town.crs)
print("YouBike 站點：", len(bike), "；快照 UpdateTime：", raw["UpdateTime"].iloc[0])

# 車站 × YouBike 對照表（500 m 內）
b500 = stations[["geometry"]].copy()
b500["geometry"] = stations.buffer(500)
pj = gpd.sjoin(bike[["geometry"]], b500, predicate="within")
pj["d"] = [round(bike.geometry.loc[i].distance(stations.geometry.loc[s])) for i, s in zip(pj.index, pj["index_right"])]
pairs = {int(s): sorted([[int(i), int(d)] for i, d in zip(g.index, g["d"])], key=lambda x: x[1]) for s, g in pj.groupby("index_right")}

# 行政區底圖（只給 prototype demo 用）
area = gpd.GeoSeries(gpd.points_from_xy([S.BBOX[1], S.BBOX[3]], [S.BBOX[0], S.BBOX[2]]), crs=4326).to_crs(town.crs).union_all().envelope.buffer(3000)
tw = town[(town["COUNTYNAME"] == S.CITY_NAME) & town.intersects(area)][["TOWNNAME", "geometry"]].copy()
tw["geometry"] = tw.geometry.simplify(25)
tw = tw.to_crs(4326)

def rings(geom):
    polys = [geom] if geom.geom_type == "Polygon" else list(geom.geoms)
    return [[[round(x, 5), round(y, 5)] for x, y in p.exterior.coords] for p in polys]

s4326, b4326 = stations.to_crs(4326), bike.to_crs(4326)
out = {
    "meta": {"rail": [str(p.name) for p, _ in S.RAIL_FILES], "bike": f"{S.BIKE_FILE.name}（UpdateTime {raw['UpdateTime'].iloc[0]}）"},
    "stations": [{"id": r["id"], "name": r["name"], "sys": r["sys"], "names": r["names"], "codes": r["codes"], "town": r["town"],
                  "lat": round(g.y, 6), "lon": round(g.x, 6)} for (_, r), g in zip(stations.iterrows(), s4326.geometry)],
    "bikes": [[r["uid"], r["name"], r["cap"], round(g.y, 6), round(g.x, 6)] for (_, r), g in zip(bike.iterrows(), b4326.geometry)],
    "pairs": [pairs.get(i, []) for i in range(len(stations))],
    "towns": [{"name": r["TOWNNAME"], "rings": rings(r.geometry)} for _, r in tw.iterrows()],
}
(S.WORK / "city_data.json").write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
print("輸出：", S.WORK / "city_data.json")
