"""第 2 步：從 Overpass 下載研究範圍的 OSM 資料（各一次），並用 Nominatim 查示範地點。

輸出 work/osm/：ways.json（道路）、base.json（水域、公園）、busstops.json（公車站牌）、examples.json。
檔案已存在就不重抓。Overpass 偶爾忙碌回 502／504，程式會換另一台伺服器再試。
"""
import json
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
import settings as S

sys.stdout.reconfigure(encoding="utf-8")
OUT = S.WORK / "osm"
OUT.mkdir(parents=True, exist_ok=True)
UA = {"User-Agent": S.USER_AGENT}
b = S.BBOX
QUERIES = {
    "ways.json": f'[out:json][timeout:180];way["highway"]["highway"!~"motorway|motorway_link|trunk|trunk_link|construction|proposed|raceway|bus_guideway"]["access"!~"private|no"]({b[0]},{b[1]},{b[2]},{b[3]});(._;>;);out body;',
    "base.json": f'[out:json][timeout:120];(way["natural"="water"]({b[0]},{b[1]},{b[2]},{b[3]});way["waterway"~"river|canal"]({b[0]},{b[1]},{b[2]},{b[3]});way["leisure"="park"]({b[0]},{b[1]},{b[2]},{b[3]}););(._;>;);out body;',
    "busstops.json": f'[out:json][timeout:60];node["highway"="bus_stop"]({b[0]},{b[1]},{b[2]},{b[3]});out body;',
}
for name, q in QUERIES.items():
    f = OUT / name
    if f.exists():
        print("已存在：", name)
        continue
    for attempt in range(4):
        url = S.OVERPASS[attempt % len(S.OVERPASS)]
        try:
            r = requests.post(url, data={"data": q}, headers=UA, timeout=300)
            r.raise_for_status()
            f.write_bytes(r.content)
            print(f"{name}：{len(r.content) / 1e6:.1f} MB（{url}）")
            break
        except requests.RequestException as e:
            print(f"{name} 第 {attempt + 1} 次失敗：{type(e).__name__}，30 秒後重試")
            time.sleep(30)
    else:
        raise SystemExit(f"{name} 下載失敗，稍後再執行一次")

ex_file = OUT / "examples.json"
examples = json.loads(ex_file.read_text(encoding="utf-8")) if ex_file.exists() else {}
for q in S.EXAMPLES:
    if q in examples:
        continue
    r = requests.get("https://nominatim.openstreetmap.org/search", headers=UA, timeout=30,
                     params={"q": q, "format": "jsonv2", "limit": 1, "countrycodes": "tw"})
    r.raise_for_status()
    hits = r.json()
    examples[q] = hits[0] if hits else None
    print("Nominatim：", q, "→", (hits[0]["lat"], hits[0]["lon"]) if hits else "找不到")
    time.sleep(1.2)                           # 每秒最多 1 次
ex_file.write_text(json.dumps(examples, ensure_ascii=False, indent=1), encoding="utf-8")
