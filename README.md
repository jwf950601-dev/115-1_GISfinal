# Last Mile 綠行臺北

115-1 地理資訊系統運用程式 期末專題。

設定出發地、目的地與中繼站，網站把大眾運輸拆成「首段 → 搭軌道 → 末段」，算出每一段的時間，並和騎機車比較；首末段可選走路、YouBike 或公車。YouBike 會顯示借車站「此刻可借」與還車站「此刻可還」、15 分鐘後預估、過去兩週的可靠度；下雨時自動改建議公車。走路與騎車的段落會標出有幾成在人行道／自行車道上、沿線一年發生過幾件行人或自行車事故；整趟另外估算大眾運輸與機車的碳排。地圖可開「人行道與自行車道」「行人、自行車事故」兩個圖層。

> **研究動機：** 臺北是全國大眾運輸市占率最高的城市，卻從 100 年的 43.5% 降到 113 年的 38.3%，私人機動運具仍占 37.0%（交通部 113 年民眾日常使用運具狀況調查）。軌道與 YouBike 已經很密，問題可能出在首末段：時間輸給機車，而且走路、騎車都不夠安全。本專題回答「首末段在哪裡接不上、差多少」，不證明「改善接駁就會少騎機車」。

## 架構

```
使用者 ──► 前端（frontend/，Leaflet + OSM 圖磚）──► 後端 API（backend/，FastAPI，Render）
            │                                     │  ├─ 路徑分析：查最短路徑樹、機車路網 Dijkstra
            └─► 地理編碼：瀏覽器直接查 Nominatim   │  └─ 公車到站：按了才查 TDX、快取 60 秒
                （Render 的 IP 會被擋；每秒 1 次、快取）
                                                  ▼
                       Supabase（PostgreSQL）◄── 抓取程式（fetcher/，GitHub Actions）
                       尖峰快照歷史                 平日尖峰每 15 分鐘：TDX YouBike、氣象署雨量
```

## 資料夾

```
115-1_GISfinal/
├── README.md                  本說明
├── requirements.txt           Python 套件
├── render.yaml                Render 部署設定
├── .env.example               環境變數範本（複製成 .env 填金鑰；.env 不上傳）
├── .github/workflows/
│   └── fetch.yml              GitHub Actions：尖峰定時抓資料
├── backend/                   後端（FastAPI）
│   ├── main.py                API 路由，並提供前端網頁
│   ├── config.py              城市、環境變數、速度與時間假設
│   ├── routing.py             最短路徑樹查詢、機車路徑、整趟行程、碳排
│   ├── safety.py              路線的人行道／自行車道比例、沿線事故；地圖圖層
│   ├── geocode.py             Nominatim 地址拆解與查詢
│   ├── live.py                YouBike 最新快照、15 分鐘預估、可靠度
│   ├── weather.py             氣象署雨量
│   ├── bus.py                 公車預估到站（按了才查）
│   ├── tdx.py                 TDX token 快取與呼叫紀錄
│   └── db.py                  資料庫連線
├── fetcher/
│   └── fetch_snapshot.py      寫入 YouBike 與雨量快照
├── frontend/                  前端網頁（index.html、css/、js/）
├── db/
│   └── schema.sql             資料表（在 Supabase SQL Editor 執行一次）
├── preprocess/                前處理（settings.py 設定城市與範圍，01～06 依序執行）
├── 01_Data/
│   ├── raw/                   原始資料（不上傳，只有 README 說明來源）
│   └── processed/app/         App 讀的前處理成果（route_data.json、v3_data.json、safety_data.json）
├── 02_Document/               文獻與課程文件（PDF 不上傳）
├── prototype/
│   └── lastmile_demo.html     純前端 demo（假資料，可直接用瀏覽器開）
└── tests/                     pytest 測試
```

## 本機執行

```bash
python -m venv .venv
.venv\Scripts\activate          # macOS／Linux：source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env          # 填入自己的金鑰；沒有金鑰也能跑，只是沒有即時資料
uvicorn backend.main:app --reload
# 開 http://127.0.0.1:8000
pytest
```

## 部署

1. **Supabase**：建立專案 → SQL Editor 貼上 `db/schema.sql` 執行 → 按「Connect」複製 **Connection pooler** 的連線字串（直接連線可能只支援 IPv6，GitHub Actions 與 Render 會連不上）。
2. **GitHub**：Settings → Secrets and variables → Actions，新增 `TDX_CLIENT_ID`、`TDX_CLIENT_SECRET`、`CWA_API_KEY`、`DATABASE_URL`。Actions 頁面可以手動執行 `fetch-snapshot` 測試一次。
3. **Render**：New → Blueprint，選這個 repo（讀 `render.yaml`）→ 在 Environment 填入同樣四個值。
4. **自訂網域（選用）**：GitHub Student Developer Pack 的免費網域 → Render 的 Settings → Custom Domains。

## 金鑰與點數

- 金鑰只放在 `.env`（本機）、GitHub Secrets、Render Environment，**不寫進程式碼、不 commit**。
- 全系統只有 GitHub Actions 定時呼叫 TDX：平日 6 小時 × 每小時 4 次 × 22 天 ≈ 528 次／月。公車到站是使用者按了才查，次數另計；每次都記在 `api_log`，每週與 TDX 會員中心對帳。

## 資料來源與授權

TDX 運輸資料流通服務、中央氣象署開放資料平臺、內政部戶政司、內政部鄉鎮市區界、臺北市資料大平臺：政府資料開放授權條款。
交通事故：內政部警政署「113 年傷亡道路交通事故資料」（政府資料開放平臺 172969）。碳排：臺北捷運、臺鐵、台灣高鐵公開的旅客運輸碳足跡；交通部運輸研究所（2014）機車與市區公車實測排放。
路網、人行道、自行車道與公車站牌位置、地址查詢：© OpenStreetMap contributors（ODbL）、Nominatim。
詳細清單見 `01_Data/raw/README.md`。

## 已知限制

- 軌道車上時間用車站直線距離估計，公車搭乘時間用站牌直線距離估計；正式版改用 TDX 時刻表與路線站序。
- 機車速度依道路等級假設，沒有號誌；自行車路網沒有考慮單行道。
- 示範地點以外的地址查詢依賴 Nominatim；完整中文門牌用自由文字常找不到，所以先拆成「區、路、號」做結構化查詢，仍可能只定位到路。
- 研究範圍目前是臺北市中心（`preprocess/settings.py` 的 `BBOX`）。
- 人行道、自行車道用 OSM，標註可能不完整；「在設施上」是用路線離設施 12 公尺內判斷，不是逐路段比對。
- 事故是點位計數，沒有除以行人或騎車流量，不能直接解讀成「危險程度」。
- 碳排：機車 164、公車 85 g／人公里取自運研所（2014）臺北市實測。捷運、臺鐵、高鐵係數含生命週期、機車只算排氣管，比較對機車有利，所以「改搭大眾運輸少排多少」是保守估計。
