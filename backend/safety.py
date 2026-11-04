"""慢行環境與安全：一段走路或騎車的路線，有幾成在人行道／自行車道上，沿線一年發生過幾件相關事故。

做法：把人行道、自行車道線段每 10 公尺打一個點建 KD-tree；路線也每 10 公尺取樣，
離設施 12 公尺內就算「走在設施上」（OSM 人行道常畫在路邊，與路網中線有幾公尺落差）。
事故：路線 30 公尺內、涉及行人（走路段）或自行車（騎車段）的案件。
"""
import json
import math
from functools import lru_cache

import numpy as np
from scipy.spatial import cKDTree

from . import config

KX = 111320 * math.cos(math.radians(25.04))
KY = 110540
STEP_M, NEAR_M, CRASH_M = 10, 12, 30
PED, BIKE_FLAG, A1 = 1, 2, 4


def _densify(lines):
    out = []
    for line in lines:
        xy = np.array([[lo * KX, la * KY] for la, lo in line])
        for a, b in zip(xy, xy[1:]):
            n = max(1, int(np.hypot(*(b - a)) // STEP_M))
            out.extend(a + (b - a) * t for t in np.linspace(0, 1, n, endpoint=False))
        out.append(xy[-1])
    return np.array(out)


@lru_cache(maxsize=1)
def data():
    S = json.loads((config.APP_DATA / "safety_data.json").read_text(encoding="utf-8"))
    crash = np.array(S["crash"])
    cxy = np.c_[crash[:, 1] * KX, crash[:, 0] * KY]
    flags = crash[:, 2].astype(int)
    return {
        "raw": S,
        "walk_kd": cKDTree(_densify(S["walk"])), "cycle_kd": cKDTree(_densify(S["cycle"])),
        "ped_kd": cKDTree(cxy[flags & PED > 0]), "bike_kd": cKDTree(cxy[flags & BIKE_FLAG > 0]),
    }


def profile(pts, mode):
    """pts：[[lat, lon], ...]；mode：walk 或 bike。回傳設施比例、沿線事故數。"""
    if not pts or len(pts) < 2:
        return None
    d = data()
    samples = _densify([pts])
    infra = d["walk_kd"] if mode == "walk" else d["cycle_kd"]
    on = infra.query(samples, distance_upper_bound=NEAR_M)[0] < math.inf
    crash_kd = d["ped_kd"] if mode == "walk" else d["bike_kd"]
    hits = set()
    for ks in crash_kd.query_ball_point(samples, CRASH_M):
        hits.update(ks)
    length = float(np.sum(np.hypot(*np.diff(samples, axis=0).T)))
    return {"share": round(float(on.mean()), 3), "crashes": len(hits), "km": round(length / 1000, 2),
            "label": "人行道" if mode == "walk" else "自行車道", "year": d["raw"]["crash_year"]}


def layers():
    """給前端畫圖層：慢行路網＋事故點（只回傳涉及行人或自行車的事故）。"""
    S = data()["raw"]
    return {"walk": S["walk"], "cycle": S["cycle"], "year": S["crash_year"],
            "crash": [c for c in S["crash"] if c[2] & (PED | BIKE_FLAG)]}
