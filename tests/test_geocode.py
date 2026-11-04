"""地址拆解的測試：用手寫的地址，正確答案一看就知道。"""
from backend.geocode import parse_address


def test_完整地址():
    p = parse_address("臺北市大安區羅斯福路四段1號")
    assert p["road"] == "羅斯福路四段" and p["no"] == "1", p


def test_沒有行政區():
    p = parse_address("市府路1號")
    assert p["district"] is None and p["road"] == "市府路" and p["no"] == "1", p


def test_有巷弄():
    p = parse_address("信義區松仁路100巷5弄2號")
    assert p["road"] == "松仁路100巷5弄" and p["no"] == "2", p


def test_地址中間有空白():
    p = parse_address("中正區 重慶南路一段 122 號")
    assert p is not None and p["no"] == "122", p


def test_地標不是地址():
    assert parse_address("國立臺灣大學") is None


def test_路口不是地址():
    assert parse_address("忠孝東路與復興南路口") is None
