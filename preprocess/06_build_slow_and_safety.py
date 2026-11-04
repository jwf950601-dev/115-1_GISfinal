"""第 6 步：慢行路網（人行道、自行車道）與交通事故點。

輸出 app/safety_data.json：
- walk、cycle：線段座標（地圖圖層用，也給後端算「路線有幾成走在人行道／自行車道上」）
- crash：研究範圍內 113 年 A1、A2 事故，一案一點，旗標 1＝有行人、2＝有自行車、4＝A1（30 日內死亡）

慢行路網暫用 OSM（臺北市標註相當完整）；之後可換成政府資料開放平臺 145867 標線型人行道。
"""
import csv
import glob
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import settings as S

sys.stdout.reconfigure(encoding="utf-8")
south, west, north, east = S.BBOX
inside = lambda lat, lon: south <= lat <= north and west <= lon <= east

# ---------- 慢行路網 ----------
OSM = json.loads((S.WORK / "osm" / "ways.json").read_text(encoding="utf-8"))
nodes = {e["id"]: (e["lat"], e["lon"]) for e in OSM["elements"] if e["type"] == "node"}
DEDICATED = {"lane", "track", "separate"}          # 不含 shared_lane（只畫標誌、與汽機車共用）


def kind(t):
    hw = t.get("highway")
    if hw == "cycleway" or t.get("bicycle") == "designated" \
            or DEDICATED & {t.get(k) for k in ("cycleway", "cycleway:left", "cycleway:right", "cycleway:both")}:
        return "cycle"
    if t.get("footway") == "crossing" or hw in ("steps", "corridor", "elevator", "platform"):
        return None
    if hw in ("footway", "pedestrian") or t.get("sidewalk") in ("both", "left", "right", "separate"):
        return "walk"
    return None


lines = {"walk": [], "cycle": []}
for w in (e for e in OSM["elements"] if e["type"] == "way"):
    k = kind(w.get("tags", {}))
    pts = [nodes[n] for n in w["nodes"] if n in nodes]
    if k and len(pts) >= 2 and any(inside(*p) for p in pts):
        lines[k].append([[round(la, 5), round(lo, 5)] for la, lo in pts])
print("人行道／步道線段：", len(lines["walk"]), "；自行車道線段：", len(lines["cycle"]))

# ---------- 交通事故（原始資料一列是一位當事者，要合併成一案）----------
CRASH_DIR = S.ROOT / "01_Data" / "raw" / "crash_113_20261104" / "unzipped"
cases = {}
for f in sorted(glob.glob(str(CRASH_DIR / "113*.csv"))):
    for r in csv.DictReader(open(f, encoding="utf-8-sig")):
        if not r["處理單位名稱警局層"].startswith(S.CITY_NAME):
            continue
        try:
            lat, lon = float(r["緯度"]), float(r["經度"])
        except ValueError:
            continue
        if not inside(lat, lon):
            continue
        key = (r["發生日期"], r["發生時間"], r["經度"], r["緯度"])
        sub = r["當事者區分-類別-子類別名稱-車種"]
        flag = (1 if sub == "行人" else 0) | (2 if sub in ("腳踏自行車", "電動輔助自行車") else 0) \
            | (4 if r["事故類別名稱"] == "A1" else 0)
        cases[key] = [round(lat, 5), round(lon, 5), cases.get(key, [0, 0, 0])[2] | flag]
crash = list(cases.values())
print("研究範圍內事故：", len(crash), "案；涉及行人", sum(c[2] & 1 > 0 for c in crash),
      "案；涉及自行車", sum(c[2] & 2 > 0 for c in crash), "案；A1", sum(c[2] & 4 > 0 for c in crash), "案")

out = {"walk": lines["walk"], "cycle": lines["cycle"], "crash": crash, "crash_year": 113}
(S.APP / "safety_data.json").write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
print("輸出：", S.APP / "safety_data.json", round((S.APP / "safety_data.json").stat().st_size / 1e6, 1), "MB")
