"""清華校園資料 API（NTHU Data API，https://api.nthusa.tw）存取工具。

- get(path, params, ttl)：回傳 (資料, 提示訊息)。成功時提示為 None。
- 同一個網址在 ttl 秒內只會真的連線一次（所有使用者共用快取）。
- 每次連線成功都會把結果存一份到 data/api_cache/；之後 API 連不上時改用這份暫存，
  並回傳提示訊息讓頁面顯示「目前是哪個時間的資料」。
- 完整的端點說明：https://api.nthusa.tw/docs
"""
from __future__ import annotations

import hashlib
import json
import time
import urllib.parse
import urllib.request
from datetime import datetime
from typing import Any

import streamlit as st

from config import DATA_DIR
from core.i18n import t

API_BASE = "https://api.nthusa.tw"
CACHE_DIR = DATA_DIR / "api_cache"
TIMEOUT = 20  # 秒
HEADERS = {"User-Agent": "campus-assistant/1.0", "Accept": "application/json"}


def _cache_path(url: str):
    return CACHE_DIR / (hashlib.md5(url.encode("utf-8")).hexdigest() + ".json")


def _save_cache(url: str, data: Any) -> None:
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        path = _cache_path(url)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"url": url, "saved_at": datetime.now().strftime("%Y/%m/%d %H:%M"), "data": data},
                                  ensure_ascii=False), encoding="utf-8")
        tmp.replace(path)
    except OSError:
        pass  # 暫存寫不進去不影響這次顯示


def _load_cache(url: str) -> dict | None:
    try:
        return json.loads(_cache_path(url).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


@st.cache_data(ttl=3600, max_entries=64, show_spinner=False)
def _fetch(url: str, bucket: int) -> Any:
    """真的連線。bucket 每 ttl 秒換一次，用來控制各端點不同的更新頻率；連線失敗會丟出例外（不會被快取）。"""
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    _save_cache(url, data)
    return data


def build_url(path: str, params: dict | None = None) -> str:
    params = {k: v for k, v in (params or {}).items() if v not in (None, "")}
    return API_BASE + path + ("?" + urllib.parse.urlencode(params) if params else "")


def get(path: str, params: dict | None = None, ttl: int = 600, refresh: bool = False) -> tuple[Any, str | None]:
    """呼叫 API。refresh=True 會略過快取、立刻重新抓。"""
    url = build_url(path, params)
    bucket = time.time_ns() if refresh else int(time.time() // ttl)
    try:
        return _fetch(url, bucket), None
    except Exception:  # 網路錯誤、逾時、API 回 4xx/5xx、JSON 格式錯誤
        cached = _load_cache(url)
        if cached is not None:
            saved = cached.get("saved_at", "")
            return cached.get("data"), t(f"暫時連不上校園資料 API，目前顯示 {saved or '先前'} 的資料",
                                         f"Campus data API is unreachable; showing data from {saved or 'earlier'}")
        return None, t("暫時連不上校園資料 API，請稍後再試", "Campus data API is unreachable, please try again later")
