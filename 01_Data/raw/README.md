# 原始資料（不上傳 GitHub）

原始資料檔案大、部分有授權限制，這個資料夾只上傳本說明。**原始資料唯讀：不修改、不覆寫。**
前處理目前直接讀課程資料夾 `115-1_GISprog/data/raw/`（路徑設定在 `preprocess/settings.py`）。

| 資料 | 來源 | 目前使用的檔案 | 授權 |
|---|---|---|---|
| 臺鐵、高鐵車站 | TDX `/v3/Rail/TRA/Station`、`/v2/Rail/THSR/Station` | `tdx/rail_TRA_20261029.json`、`tdx/rail_THSR_20261029.json`（自己的金鑰） | 政府資料開放授權條款 |
| 臺北捷運、機場捷運車站 | TDX `/v2/Rail/Metro/Station/TRTC`、`/TYMC` | `tdx_rail_20261023/`（教師快照，待改用自己的金鑰） | 同上 |
| YouBike 站點 | TDX `/v2/Bike/Station/City/Taipei` | `tdx/station_Taipei_20261023.json`（HW6 自己的金鑰） | 同上 |
| YouBike 即時車位 | TDX `/v2/Bike/Availability/City/Taipei` | GitHub Actions 定時寫入資料庫 | 同上 |
| 公車站牌、預估到站 | TDX `/v2/Bus/Stop/City/Taipei`、公車預估到站 API | 站牌待抓；到站由使用者查詢時才抓 | 同上 |
| 鄉鎮市區界 | 內政部（課程 `Taiwan_town.shp`，2019 年 6 月版） | 課程資料夾 | 政府資料開放授權條款 |
| 村里人口 | 內政部戶政司 ODRP014（`COUNTY=臺北市`） | `ris/ODRP014_11509_臺北市.json`（HW6） | 政府資料開放授權條款 |
| 路網、公車站牌位置、水域公園 | OpenStreetMap（Overpass API） | `preprocess/02_download_osm.py` 下載 | ODbL，需標示 © OpenStreetMap contributors |
| 雨量 | 中央氣象署開放資料平臺 | 授權碼；GitHub Actions 定時寫入資料庫 | 政府資料開放授權條款 |

## 慢行環境、安全、碳排

| 資料 | 來源 | 目前使用的檔案 | 授權 |
|---|---|---|---|
| 人行道、步道、自行車道 | OpenStreetMap（`footway`、`sidewalk=*`、`highway=cycleway`、`cycleway*=lane/track`、`bicycle=designated`） | 與路網同一份 `work/osm/ways.json` | ODbL |
| 交通事故逐案（含經緯度） | 政府資料開放平臺「113 年傷亡道路交通事故資料」[172969](https://data.gov.tw/dataset/172969)（內政部警政署，A1＋A2，一列＝一位當事者） | `crash_113_20261104/`（2026-11-04 下載，ZIP 40 MB，解壓約 560 MB） | 政府資料開放授權條款 |
| 捷運碳排係數 | 臺北捷運旅客運輸服務碳足跡：每人公里 75 g CO₂e（2025） | 寫在 `backend/config.py` | — |
| 臺鐵碳排係數 | 臺鐵碳足跡標籤：自強 36、莒光 50、區間 55 g CO₂e／人公里 | 同上（取區間 55） | — |
| 機車、市區公車碳排係數 | 交通部運輸研究所（2014）《車輛動態能源消耗與溫室氣體排放特性之研究—以機車為例》表 5.3-4：臺北市機車 164、市區公車 1,441 g CO₂／車公里；乘載率見表 5.2-3 註（公車 17 人） | `02_Document/運研所_2014_車輛動態能耗與溫室氣體排放_機車.pdf`；數字寫在 `backend/config.py` | 著作權屬運研所，PDF 不上傳 |
| 高鐵碳排係數 | [台灣高鐵旅客運輸服務碳足跡](https://www.thsrc.com.tw/ArticleContent/5a1f4c72-b564-4706-bcdd-efbda93c3d93)：114 年 29 g CO₂e／人公里（碳標字第 2014910001-01 號；歷次 103 年 38、106 年 34、109 年 32） | 寫在 `backend/config.py` | — |
- 官方人行道資料：政府資料開放平臺 [145867](https://data.gov.tw/dataset/145867) 標線型人行道（含寬度）；官方自行車道：TDX `/v2/Cycling/Shape/City/Taipei`。可用來檢查 OSM 的完整度。

每份快照的檔名要含取得日期（臺灣時間），並在本表補上實際取得時間。
