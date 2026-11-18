"""Google 地圖連結 → 店家資訊（營業時間、地址、電話、評分、網站、照片）。

- 有設定 Google Maps API 金鑰時（.streamlit/secrets.toml 的 GOOGLE_MAPS_API_KEY，或同名環境變數），
  用 Places API (New) 查詢店家資料；金鑰只在伺服器端使用，不會出現在網頁上。
- 沒有金鑰時只能從連結本身讀出店名與座標，營業時間由使用者自己填。
- 只接受 Google 地圖的網址（google.com/maps、maps.app.goo.gl 等），避免被拿來連到其他網站。
"""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request

import streamlit as st

from core.i18n import lang, t

PLACES_API = "https://places.googleapis.com/v1"
TIMEOUT = 15
UA = {"User-Agent": "Mozilla/5.0 (campus-assistant)"}
FIELDS = ["id", "displayName", "formattedAddress", "location", "regularOpeningHours", "nationalPhoneNumber",
          "internationalPhoneNumber", "rating", "userRatingCount", "googleMapsUri", "websiteUri", "photos",
          "businessStatus", "priceLevel"]
SHORT_HOSTS = ("maps.app.goo.gl", "goo.gl")  # 短網址：要先展開才看得到店名（goo.gl 只接受 /maps/…）
GOOGLE_HOST = re.compile(r"^(www\.|maps\.)?google\.(com|[a-z]{2}|com?\.[a-z]{2})$")  # google.com、google.com.tw…


def api_key() -> str:
    try:
        key = st.secrets.get("GOOGLE_MAPS_API_KEY", "")
    except Exception:  # 沒有 secrets.toml
        key = ""
    return str(key or os.environ.get("GOOGLE_MAPS_API_KEY", "")).strip()


# ---------- 連結 ----------
def _host(url: str) -> str:
    return (urllib.parse.urlsplit(url).hostname or "").lower()


def is_maps_url(url: str) -> bool:
    host = _host(url)
    if host == "maps.app.goo.gl":
        return True
    if host == "goo.gl":
        return urllib.parse.urlsplit(url).path.startswith("/maps")
    return bool(GOOGLE_HOST.match(host)) and ("/maps" in urllib.parse.urlsplit(url).path or host.startswith("maps."))


@st.cache_data(ttl=86400, max_entries=256, show_spinner=False)
def expand(url: str) -> str:
    """展開 maps.app.goo.gl 這類短網址；只回傳最後的網址，不讀內容。"""
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return resp.geturl()


def parse_link(url: str) -> dict:
    """從 Google 地圖網址讀出 {name, lat, lng, place_id}（讀不到的就是空值）。"""
    parts = urllib.parse.urlsplit(url)
    q = urllib.parse.parse_qs(parts.query)
    out = {"name": "", "lat": None, "lng": None, "place_id": ""}
    m = re.search(r"/maps/place/([^/@?]+)", parts.path)
    if m:
        out["name"] = urllib.parse.unquote_plus(m[1]).strip()
    elif q.get("q") or q.get("query"):
        out["name"] = (q.get("q") or q.get("query"))[0].strip()
    if q.get("query_place_id"):
        out["place_id"] = q["query_place_id"][0]
    m = re.search(r"!3d(-?\d+\.\d+)!4d(-?\d+\.\d+)", url) or re.search(r"@(-?\d+\.\d+),(-?\d+\.\d+)", url)
    if m:
        out["lat"], out["lng"] = float(m[1]), float(m[2])
    if re.fullmatch(r"-?\d+\.\d+,\s*-?\d+\.\d+", out["name"]):  # q=24.79,120.99 只是座標
        out["name"] = ""
    return out


def resolve(url: str) -> tuple[dict | None, str | None]:
    """貼上的連結 → ({map_url, name, lat, lng, place_id}, 錯誤訊息)。"""
    url = url.strip()
    if not re.match(r"^https?://", url):
        url = "https://" + url
    if not is_maps_url(url):
        return None, t("請貼上 Google 地圖的網址（例如 https://maps.app.goo.gl/…）",
                       "Please paste a Google Maps link (e.g. https://maps.app.goo.gl/…)")
    full = url
    if _host(url) in SHORT_HOSTS:
        try:
            full = expand(url)
        except (urllib.error.URLError, OSError, ValueError):
            return None, t("短網址展開失敗，請確認連結是否正確", "Couldn't open the short link; please check it")
        if not is_maps_url(full):
            return None, t("這個短網址不是 Google 地圖的店家", "That short link isn't a Google Maps place")
    info = parse_link(full)
    info["map_url"] = url
    return info, None


# ---------- Places API ----------
def _call(method: str, path: str, key: str, body: dict | None = None, mask: str | None = None) -> dict:
    headers = {"X-Goog-Api-Key": key, "Content-Type": "application/json"}
    if mask:
        headers["X-Goog-FieldMask"] = mask
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(PLACES_API + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:  # 把 Google 的錯誤訊息帶出來（金鑰錯誤、沒開 API…）
        try:
            msg = json.loads(e.read().decode("utf-8")).get("error", {}).get("message", "")
        except (ValueError, OSError):
            msg = ""
        raise RuntimeError(f"Google Places API {e.code}: {msg or e.reason}") from None


def _lang() -> str:
    """Google 回傳資料（店名、地址）的語言，跟著介面語言。"""
    return {"zh": "zh-TW", "id": "id", "vi": "vi"}.get(lang(), "en")


def _photo_uri(photo_name: str, key: str) -> str:
    """照片的公開網址（不含金鑰）。"""
    try:
        data = _call("GET", f"/{photo_name}/media?maxWidthPx=200&skipHttpRedirect=true", key)
        return data.get("photoUri", "")
    except (RuntimeError, urllib.error.URLError, OSError):
        return ""


def lookup(info: dict, name_hint: str = "") -> tuple[dict | None, str | None]:
    """用 place_id，或店名 + 座標找店家。回傳 (Places API 的原始資料, 錯誤訊息)。"""
    key = api_key()
    if not key:
        return None, t("尚未設定 Google Maps API 金鑰", "No Google Maps API key configured")
    try:
        if info.get("place_id"):
            return _call("GET", f"/places/{info['place_id']}?languageCode={_lang()}", key, mask=",".join(FIELDS)), None
        name = (name_hint or info.get("name") or "").strip()
        if not name:
            return None, t("連結裡沒有店名，請在「店名」欄位填上店名", "The link has no place name; please type the name")
        body = {"textQuery": name, "languageCode": _lang(), "pageSize": 1}
        if info.get("lat") is not None:
            body["locationBias"] = {"circle": {"center": {"latitude": info["lat"], "longitude": info["lng"]},
                                               "radius": 500.0}}
        res = _call("POST", "/places:searchText", key, body, mask=",".join("places." + f for f in FIELDS))
        places = res.get("places") or []
        if not places:
            return None, t(f"Google 地圖找不到「{name}」", f"Google Maps found nothing for “{name}”")
        return places[0], None
    except RuntimeError as e:
        return None, str(e)
    except (urllib.error.URLError, OSError, ValueError) as e:
        return None, t(f"連不上 Google：{e}", f"Couldn't reach Google: {e}")


def refresh(place_id: str) -> tuple[dict | None, str | None]:
    return lookup({"place_id": place_id})


def _hhmm(m: int) -> str:
    m %= 1440
    return f"{m // 60:02d}:{m % 60:02d}"


def week_hours(opening: dict | None) -> list[str]:
    """regularOpeningHours.periods → 週一到週日 7 個字串（"11:00-14:00,17:00-21:00"；"" 表示公休；"24小時"）。"""
    days: list[list[str]] = [[] for _ in range(7)]
    for p in (opening or {}).get("periods") or []:
        o, c = p.get("open") or {}, p.get("close")
        if "day" not in o:
            continue
        if c is None:  # 只有 open、沒有 close：全年 24 小時
            return ["24小時"] * 7
        d = (o["day"] - 1) % 7  # Google：0 = 週日
        s = o.get("hour", 0) * 60 + o.get("minute", 0)
        e = c.get("hour", 0) * 60 + c.get("minute", 0) + ((c.get("day", o["day"]) - o["day"]) % 7) * 1440
        if s == 0 and e >= 1440:
            days[d].append("24小時")
        else:
            days[d].append(f"{_hhmm(s)}-{_hhmm(e)}")
    return ["24小時" if "24小時" in x else ",".join(x) for x in days]


def to_record(p: dict) -> dict:
    """Places API 資料 → 存在個人檔案裡的欄位。"""
    loc = p.get("location") or {}
    photos = p.get("photos") or []
    return {
        "place_id": p.get("id", ""),
        "name": (p.get("displayName") or {}).get("text", ""),
        "address": p.get("formattedAddress", ""),
        "phone": p.get("nationalPhoneNumber") or p.get("internationalPhoneNumber") or "",
        "website": p.get("websiteUri", ""),
        "rating": p.get("rating"),
        "rating_count": p.get("userRatingCount"),
        "google_url": p.get("googleMapsUri", ""),
        "lat": loc.get("latitude"), "lng": loc.get("longitude"),
        "days": week_hours(p.get("regularOpeningHours")) if p.get("regularOpeningHours") else None,
        "business_status": p.get("businessStatus", ""),
        "image": _photo_uri(photos[0]["name"], api_key()) if photos else "",
    }
