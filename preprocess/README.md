# 前處理

產生 App 要讀的兩個檔案：`01_Data/processed/app/route_data.json`、`v3_data.json`。
空間分析都在這裡做完（EPSG:3826、最短路徑），網站只查表，不在線上跑大型分析。

**城市、研究範圍、原始資料路徑都在 `settings.py`**；換城市或擴大範圍只改那裡。
中間檔放 `01_Data/processed/work/`（已被 `.gitignore` 排除，不上傳）。

| 順序 | 程式 | 做什麼 | 輸出 |
|---|---|---|---|
| 1 | `01_prepare_stations.py` | 軌道車站合併 100 m 內共站、YouBike 站點、車站 × 站點對照表、行政區 | `work/city_data.json` |
| 2 | `02_download_osm.py` | Overpass 下載道路、水域公園、公車站牌（各一次）；Nominatim 查示範地點 | `work/osm/*.json` |
| 3 | `03_build_trees.py` | 步行、自行車最短路徑樹（從所有車站同時出發） | `app/route_data.json` |
| 4 | `04_build_road_and_stops.py` | 機車路網、每個路口目前最快時間、公車站牌 | `app/v3_data.json` |
| 5 | `05_build_basemap.py` | 簡化底圖，只給 `prototype/` 的 demo 用 | `work/basemap.json` |
| 6 | `06_build_slow_and_safety.py` | OSM 人行道與自行車道；事故資料一列一位當事者，合併成一案一點 | `app/safety_data.json` |
| 7 | `07_build_metro_lines.py` | 捷運各線：同一條線照 StationID 順序連起車站，套官方路線色 | `app/metro_lines.json` |

```bash
# 在專案根目錄依序執行（本機或 Colab；Colab 先 !pip install pyproj shapely）
python preprocess/01_prepare_stations.py
python preprocess/02_download_osm.py
python preprocess/03_build_trees.py
python preprocess/04_build_road_and_stops.py
python preprocess/05_build_basemap.py
python preprocess/06_build_slow_and_safety.py   # 要先把 172969 事故 ZIP 解壓到 01_Data/raw/crash_113_20261104/unzipped/
python preprocess/07_build_metro_lines.py
```

## 待改進（正式版）

- 臺北捷運、機場捷運車站目前讀教師備援快照，要改用自己的金鑰重抓。
- 公車站牌要改用 TDX `/v2/Bus/Stop/City/Taipei`，才有 `StopUID` 可以查預估到站。
- 用官方標線型人行道（145867）、TDX 自行車道檢查 OSM 慢行路網的完整度。
- 捷運路線是車站之間的直線（示意）；要畫實際線形可改用 TDX `/v2/Rail/Metro/Shape/TRTC`。
- 自行車路網沒有考慮單行道；機車速度只依道路等級假設，沒有號誌。
