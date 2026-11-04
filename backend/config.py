"""設定：金鑰一律從環境變數讀取，不寫進程式碼。"""
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")          # 本機開發用；Render 與 GitHub Actions 直接用環境變數

APP_DATA = ROOT / "01_Data" / "processed" / "app"   # 前處理產生、App 要讀的檔案
FRONTEND = ROOT / "frontend"

TDX_CLIENT_ID = os.getenv("TDX_CLIENT_ID", "")
TDX_CLIENT_SECRET = os.getenv("TDX_CLIENT_SECRET", "")
CWA_API_KEY = os.getenv("CWA_API_KEY", "")
DATABASE_URL = os.getenv("DATABASE_URL", "")
NOMINATIM_UA = os.getenv("NOMINATIM_USER_AGENT", "lastmile-taipei-course-project")

CITY = "Taipei"            # TDX 的縣市代碼
CITY_ZH = "臺北市"          # 地址結構化查詢用

# 速度與時間假設（寫進方法說明；改這裡就會改全部計算）
WALK_M_PER_MIN = 80        # 步行每分鐘 80 公尺
BIKE_M_PER_MIN = 250       # 自行車時速 15 公里
DOCK_MIN = 2               # 借車加還車
MOTO_PARK_MIN = 3          # 機車每段停車
BUS_M_PER_MIN = 20000 / 60 # 公車時速 20 公里（正式版改用 TDX 時刻表）
RAIL_M_PER_MIN = 35000 / 60
RAIL_WAIT_MIN = {"捷運": 3, "機場捷運": 6, "臺鐵": 8, "高鐵": 10}   # 班距的一半（假設值，正式版改用 TDX 時刻表）
TRANSFER_MIN = 5

# 碳排係數（公克 CO₂e／人公里）。走路、YouBike 算 0。
# 捷運：臺北捷運旅客運輸服務碳足跡 75（2025）；機場捷運沒有公開數字，暫用同值。
# 臺鐵：自強 36、莒光 50、區間 55（臺鐵碳足跡標籤），通勤多搭區間車，取 55。
# 機車、公車：運研所（2014）《車輛動態能源消耗與溫室氣體排放特性之研究—以機車為例》
#   表 5.3-4 臺北市實測、依道路里程加權：機車 164、市區公車 1,441 g CO₂／車公里。
#   機車以一人騎乘計 164；公車 ÷ 乘載率 17 人（同書表 5.2-3 註）≈ 85。
# 高鐵：台灣高鐵旅客運輸服務碳足跡標籤 29（114 年，碳標字第 2014910001-01 號，含生命週期）。
# 範圍不同：捷運 75 含生命週期，機車、公車只算排氣管 CO₂。這樣比對機車有利，
# 所以「改搭大眾運輸少排多少」是保守估計。
CARBON_G_PER_KM = {"捷運": 75, "機場捷運": 75, "臺鐵": 55, "高鐵": 29, "公車": 85, "機車": 164}
CARBON_TODO = ()

LIVE_CACHE_SEC = 15 * 60   # 沒有資料庫時，App 自己抓 TDX 的快取時間
