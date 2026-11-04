"""路徑分析的測試：軌道估計用手造的車站；整趟行程用真實的前處理成果（檔案不在就略過）。"""
import pytest

from backend import config, routing

HAS_DATA = (config.APP_DATA / "route_data.json").exists() and (config.APP_DATA / "v3_data.json").exists()


def test_不同系統要轉乘():
    A = {"name": "甲", "sys": ["臺鐵"], "lat": 25.05, "lon": 121.52}
    B = {"name": "乙", "sys": ["捷運"], "lat": 25.04, "lon": 121.52}
    r = routing.rail_leg(A, B)
    assert r["transfer"] == config.TRANSFER_MIN and r["sys"] == "臺鐵轉捷運"


def test_同系統不用轉乘():
    A = {"name": "甲", "sys": ["捷運", "臺鐵"], "lat": 25.05, "lon": 121.52}
    B = {"name": "乙", "sys": ["捷運"], "lat": 25.04, "lon": 121.52}
    r = routing.rail_leg(A, B)
    assert r["transfer"] == 0 and r["sys"] == "捷運"
    assert r["wait"] == config.RAIL_WAIT_MIN["捷運"]          # 等車取兩個系統中較短的班距


def test_距離換算():
    # 緯度差 0.01 度約 1,105 公尺
    assert abs(routing.meters(25.04, 121.52, 25.05, 121.52) - 1105.4) < 1


@pytest.mark.skipif(not HAS_DATA, reason="沒有前處理成果")
def test_整趟行程():
    t = routing.trip([{"lat": 25.0173, "lon": 121.5398, "label": "國立臺灣大學"},
                      {"lat": 25.0375, "lon": 121.5637, "label": "臺北市政府"}])
    assert len(t["legs"]) == 1
    assert t["moto"] > 0 and t["total"] > 0
    assert abs(t["total"] - (t["mile"] + t["ride"])) < 1e-6   # 總時間＝最初最後一哩＋搭車
    c = t["carbon"]
    assert c["transit_g"] >= 0 and c["moto_g"] > 0 and c["saved_g"] == c["moto_g"] - c["transit_g"]


def test_碳排係數():
    A = {"name": "甲", "sys": ["捷運"], "lat": 25.05, "lon": 121.52}
    B = {"name": "乙", "sys": ["捷運"], "lat": 25.04, "lon": 121.52}
    r = routing.rail_leg(A, B)
    assert abs(r["co2"] - r["km"] * config.CARBON_G_PER_KM["捷運"]) < 1e-6


HAS_SAFETY = (config.APP_DATA / "safety_data.json").exists()


@pytest.mark.skipif(not HAS_SAFETY, reason="沒有前處理成果")
def test_慢行比例():
    from backend import safety
    s = safety.profile([[25.0173, 121.5398], [25.0180, 121.5420]], "walk")
    assert 0 <= s["share"] <= 1 and s["crashes"] >= 0 and s["km"] > 0
    assert safety.profile([[25.0173, 121.5398]], "walk") is None   # 只有一個點不算


@pytest.mark.skipif(not HAS_DATA, reason="沒有前處理成果")
def test_範圍外的點要報錯():
    t = routing.trip([{"lat": 25.0173, "lon": 121.5398}, {"lat": 24.90, "lon": 121.30}])
    assert "error" in t["legs"][0]
