"""第 7 步：捷運路線（地圖底下的彩色線）。

TDX 捷運車站的 StationID 依路線順序編號（BL01、BL02…），同一條線照編號把車站連起來就是路線；
轉乘站每條線各有一筆。線段是車站之間的直線（示意），不是實際軌道線形；
要畫真正線形可改用 TDX /v2/Rail/Metro/Shape/TRTC。

輸出 app/metro_lines.json：[{line, name, color, coords: [[緯度, 經度], ...]}, ...]，支線各自一段。
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import settings as S

sys.stdout.reconfigure(encoding="utf-8")
# 臺北捷運官方路線色；機場捷運用桃園機場捷運的紫色
LINES = {"BR": ("文湖線", "#C48C31"), "R": ("淡水信義線", "#E3002C"), "G": ("松山新店線", "#008659"),
         "O": ("中和新蘆線", "#F8B61C"), "BL": ("板南線", "#0070BD"), "A": ("機場捷運", "#8246AF")}
# 支線：(路線, 起點站代碼, 支線的站代碼)
BRANCHES = [("R", "R22", ["R22A"]), ("G", "G03", ["G03A"]), ("O", "O12", ["O50", "O51", "O52", "O53", "O54"])]

pos = {}
for f, system in S.RAIL_FILES:
    if system not in ("捷運", "機場捷運"):
        continue
    for r in json.loads(f.read_text(encoding="utf-8")):
        p = r["StationPosition"]
        pos[r["StationID"].upper()] = [round(p["PositionLat"], 6), round(p["PositionLon"], 6)]


def key(sid):
    m = re.match(r"([A-Z]+)(\d+)", sid)
    return m.group(1), int(m.group(2))


branch_ids = {s for _, _, ids in BRANCHES for s in ids}
out = []
for line, (name, color) in LINES.items():
    main = sorted((s for s in pos if key(s)[0] == line and s not in branch_ids), key=lambda s: key(s)[1])
    # 機場捷運的 A14a 排在 A14 的位置（沒有 A14）
    if len(main) >= 2:
        out.append({"line": line, "name": name, "color": color, "coords": [pos[s] for s in main]})
    for bl, start, ids in BRANCHES:
        if bl == line and start in pos and all(s in pos for s in ids):
            out.append({"line": line, "name": name, "color": color, "coords": [pos[start]] + [pos[s] for s in ids]})
    print(f"{name}：{len(main)} 站")

(S.APP / "metro_lines.json").write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
print("輸出：", S.APP / "metro_lines.json", len(out), "段")
