"""前處理的共用設定：換城市或擴大範圍，只要改這個檔。"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORK = ROOT / "01_Data" / "processed" / "work"      # 中間檔（不上傳）
APP = ROOT / "01_Data" / "processed" / "app"        # App 讀的成果（上傳）

CITY_NAME = "臺北市"        # 鄉鎮市區界的 COUNTYNAME
TDX_CITY = "Taipei"

# 研究範圍（南, 西, 北, 東）：臺北市中心，涵蓋中正、大同、中山、松山、大安、萬華、信義區大部分
BBOX = (25.010, 121.495, 25.085, 121.585)

# 原始資料：課程資料夾 115-1_GISprog/data/raw（唯讀）
COURSE_RAW = Path("H:/我的雲端硬碟/115-1_GISprog/data/raw")
RAIL_FILES = [                                       # (檔案, 系統名稱)
    (COURSE_RAW / "tdx" / "rail_TRA_20261029.json", "臺鐵"),            # 自己的金鑰
    (COURSE_RAW / "tdx" / "rail_THSR_20261029.json", "高鐵"),           # 自己的金鑰
    (COURSE_RAW / "tdx_rail_20261023" / "metro_TRTC.json", "捷運"),     # 教師快照
    (COURSE_RAW / "tdx_rail_20261023" / "metro_TYMC.json", "機場捷運"), # 教師快照
]
# 貓空纜車不算通勤軌道（HW7 決策點 2）；臺鐵的「臺北-環島」不是上下車地點
EXCLUDE_NAMES = ("-", "基地")
BIKE_FILE = COURSE_RAW / "tdx" / "station_Taipei_20261023.json"   # HW6 自己的金鑰取得
TOWN_SHP = COURSE_RAW / "Taiwan_boundaries" / "Town" / "Taiwan_town.shp"

SYSTEM_ORDER = {"臺鐵": 0, "高鐵": 1, "捷運": 2, "機場捷運": 2}   # 共站時選代表點的順序
MERGE_M = 100                # 相距 100 公尺內合併成一站（HW7）
STATION_SIDE_M = 350         # 車站端 YouBike 的範圍（HW7）

# 示範地點：用 Nominatim 查座標（地標名稱找得到；完整中文門牌找不到）
EXAMPLES = ["國立臺灣大學", "臺北101", "臺北市政府", "國立臺灣師範大學", "松山文創園區", "西門紅樓",
            "華山1914文化創意產業", "臺北市立動物園"]

USER_AGENT = "NCUE-GIS-course-final-project/0.1 (student project, low volume)"
OVERPASS = ["https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter"]
