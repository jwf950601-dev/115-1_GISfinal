"""TDX：換 token（效期內重複使用）、呼叫 API、記錄每一次呼叫。"""
import threading
import time

import requests

from . import config

AUTH_URL = "https://tdx.transportdata.tw/auth/realms/TDXConnect/protocol/openid-connect/token"
API_BASE = "https://tdx.transportdata.tw/api/basic"

_token = {"value": None, "expires": 0.0}
_lock = threading.Lock()
call_log = []   # 每呼叫一次記一筆，抓取程式會寫進資料庫的 api_log


def has_key():
    return bool(config.TDX_CLIENT_ID and config.TDX_CLIENT_SECRET)


def get_token():
    """回傳 access token；還沒過期就沿用，不要每次呼叫都重新換。"""
    with _lock:
        if _token["value"] and time.time() < _token["expires"] - 60:
            return _token["value"]
        r = requests.post(AUTH_URL, data={
            "grant_type": "client_credentials",
            "client_id": config.TDX_CLIENT_ID,
            "client_secret": config.TDX_CLIENT_SECRET,
        }, timeout=20)
        r.raise_for_status()
        j = r.json()
        _token["value"] = j["access_token"]
        _token["expires"] = time.time() + j.get("expires_in", 86400)
        return _token["value"]


def get_json(path, params=None):
    """呼叫 TDX 基礎服務；失敗時直接丟出錯誤，不吞掉。"""
    p = {"$format": "JSON", **(params or {})}
    r = requests.get(API_BASE + path, params=p, timeout=30,
                     headers={"authorization": f"Bearer {get_token()}", "Accept-Encoding": "gzip"})
    r.raise_for_status()
    data = r.json()
    call_log.append({"time": time.time(), "path": path, "bytes": len(r.content),
                     "n": len(data) if isinstance(data, list) else None})
    return data
