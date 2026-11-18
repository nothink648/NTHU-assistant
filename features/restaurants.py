"""🍱 校園餐廳：顯示各餐廳營業時間、現在是否營業，並提供「隨機選一間」轉盤。

資料來源：NTHU Data API 的 /dining（整理自清華總務處經營管理組「餐廳及服務性廠商」頁面），
每小時自動更新；API 連不上時改用最後一次成功的暫存，再不行才用 data/restaurants.json（離線備份）。

營業時間是官網的自由文字（例如「週一至週五7:30-19:30,假日8:30-14:30」、
「11月每周六暫停營業」），這裡盡量解析成「現在營業中 / 休息中 / 今日公休」，
但國定假日、寒暑假等無法判斷，實際以店家公告為準。

「我的餐廳」：每個帳號可以貼 Google 地圖連結加入自己的校外餐廳（存在 data/users/<id>/my_restaurants.json）。
有 Google Maps API 金鑰時自動帶入營業時間、地址、電話、評分（core/places.py），沒有金鑰時營業時間自己填。
"""
from __future__ import annotations

import random
import re
import uuid
from datetime import date, datetime, timedelta

import streamlit as st

from core.i18n import t, weekday
from core import nthu_api, places
from core.storage import load_json, load_user_json, save_user_json
from core.icons import has, icon, label
from core.nav import scroll_to
from core.ui import badge, esc, hero, html
from features.base import Feature

DATA_FILE = "restaurants.json"  # 離線備份（API 與暫存都沒有資料時才用）
API_TTL = 3600  # 秒
SOURCE_URL = "https://ddfm.site.nthu.edu.tw/p/404-1494-256455.php?Lang=zh-tw"
SERVICE_WORDS = ("眼鏡", "洗衣", "理髮", "打字", "書苑", "書局", "郵局", "影印")  # 非餐廳，不參加轉盤
HIDDEN_NAMES = {"straight a"}  # 不想顯示的店家（小寫）；從官網更新後也會被排除
SPIN_SECONDS = 4.2  # 轉盤轉動時間
ROW_PX = 58  # 轉盤每一列高度
MY_FILE = "my_restaurants.json"  # 個人的校外餐廳
MY_REFRESH_DAYS = 7  # 從 Google 抓的資料幾天更新一次

CN_DAYS = "一二三四五六日"
_D = f"[{CN_DAYS}]"
TIME_RANGE = re.compile(r"(\d{1,2})[:：](\d{1,2})\s*[-~～－–:]\s*(\d{1,2})[:：](\d{1,2})")
SEG_SPLIT = re.compile(r"[,，;；]|、(?=[週周])")

STATUS_STYLE = {  # key -> 顏色
    "open": "#2E9E6A", "closing": "#E08A1E", "later": "#2C8BC9",
    "done": "#8A8A9A", "closed": "#E5486F", "unknown": "#8A8A9A",
}

_CSS = """
<style>
.food-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:14px;margin-top:6px}
.food-grid .card{margin:0;display:flex;flex-direction:column;gap:6px}
.food-grid .card.food-focus{border-color:var(--acc);box-shadow:0 0 0 3px color-mix(in srgb,var(--acc) 35%%,transparent);
  animation:foodFocus 1s ease-in-out 3}
@keyframes foodFocus{from,to{transform:none}50%%{transform:scale(1.03)}}
.food-grid .card:nth-child(n+2){animation-delay:.03s}.food-grid .card:nth-child(n+4){animation-delay:.06s}
.food-grid .card:nth-child(n+7){animation-delay:.09s}.food-grid .card:nth-child(n+10){animation-delay:.12s}
.fhead{display:flex;gap:12px;align-items:center}
.fimg{width:52px;height:52px;border-radius:12px;object-fit:cover;flex:none;background:var(--acc-soft)}
.fname{font-weight:800;font-size:1.02rem;line-height:1.25}
.farea{opacity:.6;font-size:.78rem}
.ftoday{font-weight:700;font-size:.9rem}
.fweek{font-size:.78rem;opacity:.7;line-height:1.5}
.fweek b{font-weight:600;opacity:.85;margin-right:4px}
.fnote{font-size:.78rem;color:#E5486F;opacity:.9}
.fphone{font-size:.76rem;opacity:.55}
.fextra{font-size:.78rem;display:flex;flex-wrap:wrap;gap:4px 12px;align-items:center}
.fextra .ico{width:1em;height:1em;vertical-align:-.15em;margin-right:3px}
.fextra a{color:var(--acc-text);text-decoration:none;font-weight:600}
.fextra a:hover{text-decoration:underline}
.frate{font-weight:700;color:#E08A1E}
.frate small{font-weight:500;opacity:.7;color:var(--text-color, inherit)}
.card.is-off>*{opacity:.6;transition:opacity .2s}
.card.is-off:hover>*{opacity:1}

.reel-win{position:relative;height:%(win)spx;overflow:hidden;border-radius:18px;border:1px solid var(--line);background:var(--card-bg);
  -webkit-mask-image:linear-gradient(transparent,#000 28%%,#000 72%%,transparent);mask-image:linear-gradient(transparent,#000 28%%,#000 72%%,transparent)}
.reel-frame{position:absolute;left:10px;right:10px;top:%(row)spx;height:%(row)spx;border-radius:14px;border:2px solid var(--acc);
  background:var(--acc-soft);box-shadow:0 0 0 4px rgba(108,99,255,.08);z-index:0}
.reel{position:relative;z-index:1;will-change:transform}
.reel-item{height:%(row)spx;display:flex;align-items:center;justify-content:center;gap:10px;font-weight:800;font-size:1.15rem}
.reel-item small{font-weight:500;font-size:.75rem;opacity:.55}
@keyframes framePulse{0%%{transform:scale(1)}40%%{transform:scale(1.04);box-shadow:0 0 0 10px rgba(108,99,255,.0),0 0 24px rgba(108,99,255,.45)}100%%{transform:scale(1)}}
@keyframes winGlow{from{color:inherit}to{color:var(--acc-text);letter-spacing:.5px}}
.reel-win.anim .reel-frame{animation:framePulse .6s ease %(dur)ss 2 both}
.reel-win.anim .win{animation:winGlow .4s ease %(dur)ss both}
.reel-win:not(.anim) .win{color:var(--acc-text)}
.spin-result{margin-top:14px}
.spin-result.anim{animation:popIn .5s var(--spring) %(dur2)ss both}
/* 轉盤按鈕前的骰子 icon（本頁只有這一個主要按鈕） */
.st-key-food_spin_btn button p::before{content:"";display:inline-block;width:1.1em;height:1.1em;
  margin-right:6px;vertical-align:-.18em;background:currentColor;-webkit-mask:url(app/static/icons/dice.png) center/contain no-repeat;
  mask:url(app/static/icons/dice.png) center/contain no-repeat}
.st-key-my_food_cta{background:linear-gradient(135deg,rgba(108,99,255,.16),rgba(179,157,255,.08)),var(--card-bg);
  border-color:var(--acc-line)!important;height:100%%;justify-content:center}
/* 和左邊「今天吃什麼？」方框一樣高（欄位本身已等高，撐滿外層包裝即可） */
[data-testid="stLayoutWrapper"]:has(> .st-key-my_food_cta){height:100%%}
.cta-h{font-weight:800;font-size:1.05rem;display:flex;align-items:center;gap:6px;color:var(--acc-text)}
.cta-h .ico{width:1.2em;height:1.2em}
.cta-s{font-size:.82rem;opacity:.75;margin:2px 0 4px}
.my-row{font-weight:700;line-height:1.3}.my-row small{display:block;font-weight:400;opacity:.6;font-size:.75rem}
.spin-result .card{border:1.5px solid var(--acc-line);background:linear-gradient(135deg,rgba(108,99,255,.10),rgba(179,157,255,.06)),var(--solid)}
</style>
""" % {"win": ROW_PX * 3, "row": ROW_PX, "dur": SPIN_SECONDS, "dur2": SPIN_SECONDS + 0.1}


# ---------- 資料 ----------
def load_data(refresh: bool = False) -> dict:
    """{buildings: [{building, restaurants: [...]}], error: 提示訊息或 None, offline: 是否用離線備份}。"""
    buildings, err = nthu_api.get("/dining", ttl=API_TTL, refresh=refresh)
    if isinstance(buildings, list) and buildings:
        return {"buildings": buildings, "error": err, "offline": False}
    data = load_json(DATA_FILE, {})
    if isinstance(data, list):  # 只有清單時視為 buildings
        data = {"buildings": data}
    data.setdefault("buildings", [])
    data.update(error=err or t("餐廳 API 沒有資料", "The dining API returned no data"), offline=True)
    return data


def building_label(name: str) -> str:
    """「水木生活中心(商場聯絡窗口 …)」→「水木生活中心」。"""
    return re.sub(r"\s*[（(].*?[)）]\s*", "", name).strip() or name


def all_restaurants(data: dict) -> list[dict]:
    out = []
    for b in data["buildings"]:
        for r in b.get("restaurants", []):
            if not isinstance(r, dict) or not r.get("name"):
                continue
            if r["name"].strip().casefold() in HIDDEN_NAMES:
                continue
            r = dict(r)
            r["building"] = building_label(b.get("building", ""))
            r["id"] = f'{r["building"]}|{r.get("area", "")}|{r["name"]}'
            r["is_food"] = not any(w in r["name"] for w in SERVICE_WORDS)
            out.append(r)
    return out


def my_label() -> str:
    return t("我的餐廳", "My places")


def load_mine() -> list[dict]:
    """目前帳號自己加入的校外餐廳（原始資料）。未登入時是空的。"""
    try:
        data = load_user_json(MY_FILE, [])
    except RuntimeError:
        return []
    return [r for r in data if isinstance(r, dict) and r.get("id") and r.get("name")] if isinstance(data, list) else []


def save_mine(items: list[dict]) -> None:
    save_user_json(MY_FILE, items)


def my_restaurants(items: list[dict] | None = None) -> list[dict]:
    """轉成和校內餐廳一樣的格式，可以直接放進卡片、轉盤、首頁。"""
    out = []
    for rec in load_mine() if items is None else items:
        r = dict(rec)
        r.update(building=my_label(), area=rec.get("address") or t("校外", "Off campus"), id="my|" + rec["id"],
                 my_id=rec["id"], is_food=True, custom=True)
        if rec.get("business_status") == "CLOSED_TEMPORARILY":
            r["note"] = t("Google 地圖顯示暫停營業", "Temporarily closed on Google Maps")
        elif rec.get("business_status") == "CLOSED_PERMANENTLY":
            r["note"] = t("Google 地圖顯示已永久歇業", "Permanently closed on Google Maps")
        out.append(r)
    return out


def _auto_refresh(items: list[dict]) -> list[dict]:
    """從 Google 抓的店家資料超過 MY_REFRESH_DAYS 天就重新抓一次（營業時間可能改了）。"""
    if not places.api_key():
        return items
    changed = False
    limit = (datetime.now() - timedelta(days=MY_REFRESH_DAYS)).isoformat(timespec="minutes")
    for rec in items:
        if rec.get("place_id") and rec.get("fetched", "") < limit:
            p, err = places.refresh(rec["place_id"])
            rec["fetched"] = datetime.now().isoformat(timespec="minutes")  # 失敗也等下一輪，避免每次開頁都重試
            if p and not err:
                rec.update({k: v for k, v in places.to_record(p).items() if v not in (None, "")})
            changed = True
    if changed:
        save_mine(items)
    return items


# ---------- 營業時間解析 ----------
def _to_min(h: str, m: str) -> int:
    return int(h) * 60 + int(m)


def day_set(text: str) -> set[int] | None:
    """從「週一至週五」「週六、日」「假日」這類文字取出星期（0=週一）。沒有指定星期則回傳 None。"""
    t = text
    for w in ("國定假日", "寒暑假", "寒假", "暑假"):
        t = t.replace(w, "")
    days: set[int] = set()
    found = False
    if "假日" in t:
        days |= {5, 6}
        found = True
        t = t.replace("假日", "")
    for a, b in re.findall(rf"[週周]({_D})\s*[至到~～\-－]\s*[週周]?({_D})", t):
        i, k = CN_DAYS.index(a), CN_DAYS.index(b)
        days |= set(range(i, k + 1)) if i <= k else set(range(i, 7)) | set(range(0, k + 1))
        found = True
    t = re.sub(rf"[週周]{_D}\s*[至到~～\-－]\s*[週周]?{_D}", "", t)
    for grp in re.findall(rf"[週周]({_D}(?:\s*[、及和,，]\s*{_D})*)", t):
        days |= {CN_DAYS.index(c) for c in grp if c in CN_DAYS}
        found = True
    return days if found else None


def day_field(weekday: int) -> str:
    return "weekday" if weekday < 5 else ("saturday" if weekday == 5 else "sunday")


def parse_hours(text: str, weekday: int) -> tuple[list[tuple[int, int]], bool]:
    """回傳 (今天的營業區間[(開始分, 結束分)], 今天是否明寫公休)。"""
    text = text or ""
    if "24小時" in text or "24 小時" in text:
        return [(0, 1440)], False
    ranges, closed, last_days = [], False, None
    for seg in SEG_SPLIT.split(text):
        if not seg.strip():
            continue
        first_digit = re.search(r"\d", seg)
        prefix = seg[:first_digit.start()] if first_digit else seg
        days = day_set(prefix)
        if days is None:
            days = last_days  # 沒寫星期 → 沿用前一段（例如「週一至週五11:00-13:00,16:30-19:00」）
        else:
            last_days = days
        applies = days is None or weekday in days
        if not applies:
            continue
        if re.search(r"暫停|公休|休息", seg) and not TIME_RANGE.search(seg):
            closed = True
            continue
        for h1, m1, h2, m2 in TIME_RANGE.findall(seg):
            s, e = _to_min(h1, m1), _to_min(h2, m2)
            if e <= s:
                e += 1440
            ranges.append((s, e))
    return sorted(ranges), closed


def note_rules(note: str, today: date) -> tuple[bool, str | None, bool]:
    """解析備註裡的公休規則。回傳 (今天整天公休, 只停 'lunch'/'dinner', 有無法判斷的規則)。"""
    closed, meal, irregular = False, None, False
    for sent in re.split(r"[。.]", note or ""):
        if not re.search(r"暫停營業|公休|休息", sent):
            continue
        # 特定日期：11/14、11/23-11/28、11/13晚餐
        for m in re.finditer(r"(\d{1,2})/(\d{1,2})(?:\s*[-~～至]\s*(?:(\d{1,2})/)?(\d{1,2}))?\s*(午餐|晚餐)?", sent):
            m1, d1 = int(m[1]), int(m[2])
            m2 = int(m[3]) if m[3] else m1
            d2 = int(m[4]) if m[4] else d1
            try:
                start, end = date(today.year, m1, d1), date(today.year, m2, d2)
            except ValueError:
                continue
            if start <= today <= end:
                if m[5]:
                    meal = "lunch" if m[5] == "午餐" else "dinner"
                else:
                    closed = True
        sent = re.sub(r"\d{1,2}/\d{1,2}(?:\s*[-~～至]\s*(?:\d{1,2}/)?\d{1,2})?\s*(午餐|晚餐)?", "", sent)
        if re.search(r"第[\d、,，\s]+[週周]", sent):  # 第2、4週… 無法可靠判斷
            irregular = True
            continue
        mm = re.match(r"\s*(\d{1,2})月", sent)
        if mm:
            if int(mm[1]) != today.month:
                continue
            sent = sent[mm.end():]
        days = day_set(sent)
        if days and today.weekday() in days:
            closed = True
    return closed, meal, irregular


def fmt_min(m: int) -> str:
    if m == 1440:
        return "24:00"
    m %= 1440  # 跨夜的結束時間
    return f"{m // 60:02d}:{m % 60:02d}"


def fmt_ranges(ranges: list[tuple[int, int]]) -> str:
    if ranges == [(0, 1440)]:
        return t("24 小時", "24 hours")
    return t("、", ", ").join(f"{fmt_min(s)}–{fmt_min(e)}" for s, e in ranges)


def day_text(r: dict, wd: int) -> str:
    """某一天的營業時間文字：Google 的資料是一週 7 天各一筆（days），校內餐廳是平日 / 週六 / 週日。"""
    if r.get("days"):
        return r["days"][wd] or ""
    return (r.get("schedule") or {}).get(day_field(wd), "")


def has_hours(r: dict) -> bool:
    return bool(r.get("days")) or any((r.get("schedule") or {}).values())


def status(r: dict, now: datetime) -> dict:
    """計算這間店此刻的狀態。"""
    wd = now.weekday()
    if not has_hours(r):  # 自己加的店沒有營業時間資料
        return {"key": "unknown", "label": t("營業時間未提供", "Hours not available"), "today": "—",
                "irregular": False, "allday": False, "end": None, "is_open": False}
    ranges, closed = parse_hours(day_text(r, wd), wd)
    # 前一天營業到半夜以後（例如 18:00–02:00），凌晨時仍算營業中
    prev, _ = parse_hours(day_text(r, (wd - 1) % 7), (wd - 1) % 7)
    carry = [(s - 1440, e - 1440) for s, e in prev if e > 1440 and (s, e) != (0, 1440)]
    n_closed, meal, irregular = note_rules(r.get("note", ""), now.date())
    if meal == "lunch":
        ranges = [x for x in ranges if x[0] >= 15 * 60]
    elif meal == "dinner":
        ranges = [x for x in ranges if x[0] < 15 * 60]
    cur = now.hour * 60 + now.minute
    allday, end = False, None  # 首頁用：是否 24 小時、營業中的打烊時間
    carry_live = next((x for x in carry if x[0] <= cur < x[1]), None)
    if r.get("business_status") in ("CLOSED_TEMPORARILY", "CLOSED_PERMANENTLY"):
        key, label = "closed", t("暫停營業", "Closed")
    elif carry_live:
        left = carry_live[1] - cur
        key = "closing" if left <= 30 else "open"
        end = fmt_min(carry_live[1])
        label = (t(f"即將打烊 · {end}", f"Closing soon · {end}") if key == "closing"
                 else t(f"營業中 · 至 {end}", f"Open · until {end}"))
    elif closed or n_closed:
        key, label = "closed", t("今日公休", "Closed today")
    elif not ranges:
        key, label = "closed", t("今日未營業", "Not open today")
    else:
        live = next((x for x in ranges if x[0] <= cur < x[1]), None)
        upcoming = next((x for x in ranges if x[0] > cur), None)
        if live and live == (0, 1440):
            key, label, allday = "open", t("24 小時營業", "24 hours open"), True
        elif live:
            left = live[1] - cur
            key = "closing" if left <= 30 else "open"
            end = fmt_min(live[1])
            label = (t(f"即將打烊 · {end}", f"Closing soon · {end}") if key == "closing"
                     else t(f"營業中 · 至 {end}", f"Open · until {end}"))
        elif upcoming:
            key, label = "later", t(f"{fmt_min(upcoming[0])} 開始營業", f"Opens at {fmt_min(upcoming[0])}")
        else:
            key, label = "done", t("今日已打烊", "Closed for today")
    today = t("今日公休", "Closed today") if key == "closed" else fmt_ranges(ranges)
    return {"key": key, "label": label, "today": today, "irregular": irregular, "allday": allday, "end": end,
            "is_open": key in ("open", "closing")}


def _day_hours(text: str) -> str:
    if not text:
        return t("公休", "Closed")
    if "24小時" in text:
        return t("24 小時", "24 hours")
    return text.replace(",", ", ").replace("-", "–")


def week_lines(r: dict) -> str:
    if r.get("days"):  # 一週 7 天：相同時間的連續幾天合併成一行（週一–週五 11:00–21:00）
        lines, d = [], 0
        while d < 7:
            k = d
            while k + 1 < 7 and r["days"][k + 1] == r["days"][d]:
                k += 1
            name = weekday(d) if k == d else f"{weekday(d)}–{weekday(k)}"
            lines.append(f"<b>{esc(name)}</b> {esc(_day_hours(r['days'][d]))}")
            d = k + 1
        return "<br>".join(lines)
    s = r.get("schedule") or {}
    wk, sa, su = s.get("weekday", ""), s.get("saturday", ""), s.get("sunday", "")
    if r.get("custom"):  # 自己填的：留空代表公休
        wk, sa, su = (x or t("公休", "Closed") for x in (wk, sa, su))
    if wk == sa == su:
        label = t("時間", "Hours ") if re.search(r"[週周]|假日", wk) else t("每日", "Daily ")  # 文字已寫星期就不加「每日」
        return f"<b>{label}</b>{esc(wk)}"
    return (f"<b>{t('平日', 'Weekdays ')}</b>{esc(wk)}<br><b>{t('週六', 'Sat ')}</b>{esc(sa)}"
            f"<br><b>{t('週日', 'Sun ')}</b>{esc(su)}")


# ---------- 卡片 ----------
def restaurant_card(r: dict, st_: dict, extra_cls: str = "") -> str:
    img = f'<img class="fimg" src="{esc(r["image"])}" alt="" loading="lazy">' if r.get("image") else '<div class="fimg"></div>'
    area = esc(r.get("area") or r.get("building", ""))
    note = f'<div class="fnote">{icon("warning") or "⚠️"} {esc(r["note"])}</div>' if r.get("note") else ""
    phone = f'<div class="fphone">{icon("telephone") or "☎"} {esc(r["phone"])}</div>' if r.get("phone") else ""
    off = "" if st_["is_open"] else "is-off"
    week = f'<div class="fweek">{week_lines(r)}</div>' if has_hours(r) else ""
    return (f'<div class="card {off} {extra_cls}"><div class="fhead">{img}<div>'
            f'<div class="fname">{esc(r["name"])}</div><div class="farea">{icon("pin")} {area}</div></div></div>'
            f'<div>{badge(st_["label"], STATUS_STYLE[st_["key"]], live=st_["is_open"])}</div>'
            f'<div class="ftoday">{t("今日", "Today")}　{esc(st_["today"])}</div>'
            f'{week}{note}{phone}{_extra_html(r) if r.get("custom") else ""}</div>')


def _extra_html(r: dict) -> str:
    """我的餐廳：Google 評分、地圖與網站連結。"""
    parts = []
    if r.get("rating"):
        n = f"（{r['rating_count']:,}）" if r.get("rating_count") else ""
        parts.append(f'<span class="frate">{icon("star") or "⭐"}{float(r["rating"]):.1f}<small>{esc(n)}</small></span>')
    link = r.get("google_url") or r.get("map_url")
    if link:
        parts.append(f'<a href="{esc(link)}" target="_blank" rel="noopener">{icon("map") or "🗺️"}{t("Google 地圖", "Google Maps")}</a>')
    if r.get("website"):
        parts.append(f'<a href="{esc(r["website"])}" target="_blank" rel="noopener">{icon("web") or "🌐"}{t("網站", "Website")}</a>')
    return f'<div class="fextra">{"".join(parts)}</div>' if parts else ""


# ---------- 新增 / 管理我的餐廳 ----------
def _hours_ok(text: str) -> bool:
    return not text.strip() or bool(TIME_RANGE.search(text)) or "24" in text


def _add_mine(url: str, name: str, manual: dict | None) -> tuple[bool, str]:
    """manual：沒有 API 金鑰時使用者自己填的 {weekday, saturday, sunday, phone}。"""
    if not url.strip():
        return False, t("請貼上 Google 地圖連結", "Please paste a Google Maps link")
    info, err = places.resolve(url)
    if err:
        return False, err
    now = datetime.now().isoformat(timespec="minutes")
    if manual is None:  # 有金鑰：向 Google 查詢
        p, err = places.lookup(info, name)
        if err:
            return False, err
        rec = {"source": "google", "map_url": info["map_url"], "fetched": now, **places.to_record(p)}
    else:
        name = name.strip() or info.get("name", "")
        if not name:
            return False, t("連結裡沒有店名，請在「店名」欄位填上店名", "The link has no place name; please type the name")
        sched = {k: manual[k].strip() for k in ("weekday", "saturday", "sunday")}
        bad = [v for v in sched.values() if not _hours_ok(v)]
        if bad:
            return False, t(f"看不懂營業時間「{bad[0]}」，請寫成 11:00-14:00, 17:00-21:00 這樣的格式",
                            f"Couldn't read the hours “{bad[0]}”. Use a format like 11:00-14:00, 17:00-21:00")
        rec = {"source": "manual", "map_url": info["map_url"], "name": name, "address": "", "phone": manual["phone"].strip(),
               "lat": info.get("lat"), "lng": info.get("lng"), "schedule": sched, "fetched": now}
    items = load_mine()
    old = next((x for x in items if (rec.get("place_id") and x.get("place_id") == rec["place_id"])
                or x["name"].casefold() == rec["name"].casefold()), None)
    if old:  # 同一間店：更新資料，不重複加入
        old.update(rec)
        save_mine(items)
        return True, t(f"已更新「{rec['name']}」", f"Updated “{rec['name']}”")
    items.append({"id": uuid.uuid4().hex, **rec})
    save_mine(items)
    return True, t(f"已加入「{rec['name']}」", f"Added “{rec['name']}”")


def _delete_mine(my_id: str) -> None:
    items = load_mine()
    gone = next((x for x in items if x["id"] == my_id), None)
    save_mine([x for x in items if x["id"] != my_id])
    if gone:
        st.session_state.food_flash_del = t(f"已刪除「{gone['name']}」", f"Removed “{gone['name']}”")
    st.session_state.pop("food_spin", None)


def _refresh_mine(my_id: str) -> None:
    items = load_mine()
    rec = next((x for x in items if x["id"] == my_id), None)
    if not rec or not rec.get("place_id"):
        return
    p, err = places.refresh(rec["place_id"])
    if err:
        st.session_state.food_err = err
        return
    rec.update({k: v for k, v in places.to_record(p).items() if v not in (None, "")},
               fetched=datetime.now().isoformat(timespec="minutes"))
    save_mine(items)
    st.session_state.food_flash = t(f"已更新「{rec['name']}」", f"Updated “{rec['name']}”")


def _my_places_dialog(mine: list[dict]) -> None:
    """彈出視窗：貼 Google 地圖連結新增，下面列出已加入的店（可更新 / 刪除）。"""
    has_key = bool(places.api_key())
    if has_key:
        st.caption(t("在 Google 地圖找到店家 → 分享 → 複製連結，貼到下面。營業時間、地址、電話、評分會自動帶入，"
                     "只有你自己看得到，會出現在「我的餐廳」分頁、轉盤與首頁。",
                     "On Google Maps open the place → Share → Copy link, then paste it below. Hours, address, phone and "
                     "rating are filled in automatically. Only you can see them, under “My places”, in the wheel and on Home."))
    else:
        st.caption(t("在 Google 地圖找到店家 → 分享 → 複製連結，貼到下面，再填上營業時間（格式和校內餐廳一樣，"
                     "例如 11:00-14:00, 17:00-21:00；公休就留空）。只有你自己看得到。",
                     "On Google Maps open the place → Share → Copy link and paste it below, then enter the hours "
                     "(e.g. 11:00-14:00, 17:00-21:00; leave empty if closed). Only you can see them."))
    with st.form("my_food_add", clear_on_submit=True, border=False):
        url = st.text_input(t("Google 地圖連結", "Google Maps link"), key="mf_url",
                            placeholder="https://maps.app.goo.gl/…")
        name = st.text_input(t("店名（選填，連結裡沒有店名時才需要）", "Name (optional, only if the link has none)"),
                             key="mf_name")
        manual = None
        if not has_key:
            c1, c2, c3 = st.columns(3)
            manual = {
                "weekday": c1.text_input(t("平日營業時間", "Weekday hours"), key="mf_wk", placeholder="11:00-14:00, 17:00-21:00"),
                "saturday": c2.text_input(t("週六營業時間", "Saturday hours"), key="mf_sa", placeholder="11:00-21:00"),
                "sunday": c3.text_input(t("週日營業時間", "Sunday hours"), key="mf_su", placeholder=t("公休就留空", "Empty = closed")),
            }
            manual["phone"] = st.text_input(t("電話（選填）", "Phone (optional)"), key="mf_phone")
        if st.form_submit_button(label("add", t("加入我的餐廳", "Add to my places")), type="primary", key="mf_add"):
            with st.spinner(t("正在查詢店家資料…", "Looking up the place…")):
                ok, msg = _add_mine(url, name, manual)
            if ok:
                st.session_state.food_flash = msg
                st.session_state.pop("food_spin", None)
                st.rerun()
            st.error(msg)
    if not has_key:
        st.caption(t("從 Google 地圖自動帶入營業時間的功能還在完善中，目前請先自己填寫。",
                     "Automatically filling in hours from Google Maps is still being improved; please enter them yourself for now."))
    if "food_err" in st.session_state:
        st.error(st.session_state.pop("food_err"))

    if mine:
        st.markdown(f"**{t('我的餐廳', 'My places')}**")
    for r in mine:
        c1, c2, c3 = st.columns([5, 1.2, 1.2], vertical_alignment="center")
        c1.markdown(f'<div class="my-row">{esc(r["name"])}<small>{esc(r.get("address") or "")}</small></div>',
                    unsafe_allow_html=True)
        if r.get("place_id") and has_key:
            c2.button(label("refresh", t("更新", "Refresh")), key=f"mf_ref_{r['my_id']}", on_click=_refresh_mine,
                      args=(r["my_id"],), use_container_width=True)
        c3.button(label("trash", t("刪除", "Delete")), key=f"del_myfood_{r['my_id']}", on_click=_delete_mine,
                  args=(r["my_id"],), use_container_width=True)


def _open_dialog(mine: list[dict]) -> None:
    st.dialog(t("新增我的校外餐廳", "Add my own off-campus places"), width="large")(_my_places_dialog)(mine)


def _add_box(mine: list[dict]) -> None:
    """轉盤右邊的醒目入口：按了跳出新增視窗。"""
    with st.container(border=True, key="my_food_cta"):
        html(f'<div class="cta-h">{icon("food") or "🍜"} {t("想吃校外的？", "Eating off campus?")}</div>'
             f'<div class="cta-s">{t("貼上 Google 地圖連結，加入你自己的餐廳", "Paste a Google Maps link to add your own places")}</div>')
        if st.button(label("add", t("新增餐廳", "Add a place")), type="primary", key="mf_open", use_container_width=True):
            _open_dialog(mine)
        if mine:
            st.caption(t(f"已加入 {len(mine)} 間，按上面的按鈕可管理", f"{len(mine)} added; use the button above to manage them"))


# ---------- 轉盤 ----------
def _spin(cands: list[dict]) -> None:
    if not cands:
        return
    winner = random.choice(cands)
    reel = [random.choice(cands) for _ in range(30)]
    for k in range(1, len(reel)):  # 盡量不要連續出現同一間
        if len(cands) > 1 and reel[k]["id"] == reel[k - 1]["id"]:
            reel[k] = random.choice([c for c in cands if c["id"] != reel[k - 1]["id"]])
    tail = [random.choice(cands) for _ in range(2)]
    st.session_state.food_spin = {"nonce": uuid.uuid4().hex[:8], "reel": reel + [winner] + tail,
                                  "win_idx": len(reel), "winner_id": winner["id"]}
    st.session_state.food_anim = True  # 只有按下按鈕的那一次播放動畫


def reel_html(spin: dict, animate: bool) -> str:
    items = "".join(
        f'<div class="reel-item{" win" if i == spin["win_idx"] else ""}">{esc(r["name"])}'
        f'<small>{esc(r.get("area") or r.get("building", ""))}</small></div>'
        for i, r in enumerate(spin["reel"]))
    offset = (spin["win_idx"] - 1) * ROW_PX  # 讓得獎者停在中間那一列
    style, anim_css = f"transform:translateY(-{offset}px);", ""
    if animate:
        name = f"reel_{spin['nonce']}"  # 每次不同名稱，保證動畫重新播放
        anim_css = (f"<style>@keyframes {name}{{0%{{transform:translateY(0);filter:blur(0)}}"
                    f"10%{{filter:blur(1.6px)}}75%{{filter:blur(.5px)}}"
                    f"100%{{transform:translateY(-{offset}px);filter:blur(0)}}}}</style>")
        style += f"animation:{name} {SPIN_SECONDS}s cubic-bezier(.12,.8,.16,1) both;"
    return (f'{anim_css}<div class="reel-win{" anim" if animate else ""}"><div class="reel-frame"></div>'
            f'<div class="reel" style="{style}">{items}</div></div>')


def _roulette(rests: list[dict], stats: dict[str, dict], buildings: list[str]) -> None:
    ss = st.session_state
    with st.container(border=True):
        html(f'<div style="font-weight:700">{icon("dice")} {t("今天吃什麼？", "What should I eat?")}'
             f'<span class="muted">　{t("讓轉盤幫你決定", "Let the wheel decide")}</span></div>')
        c1, c2 = st.columns([3, 2], vertical_alignment="bottom")
        picked = c1.multiselect(t("抽選範圍", "Areas"), buildings, default=buildings, key="food_areas",
                                placeholder=t("全部區域", "All areas"))
        only_open = c2.toggle(t("只抽現在營業中的", "Only places open now"), value=True, key="food_only_open")
        areas = set(picked or buildings)
        cands = [r for r in rests if r["is_food"] and r["building"] in areas
                 and (not only_open or stats[r["id"]]["is_open"])]
        st.button(("" if has("dice") else "🎲 ") + t(f"隨機選一間（{len(cands)} 間候選）", f"Pick one ({len(cands)} candidates)"),
                  type="primary", on_click=_spin, args=(cands,),
                  disabled=not cands, key="food_spin_btn")
        if not cands:
            st.caption(t("目前沒有符合條件的餐廳，試著關掉「只抽現在營業中的」或放寬範圍。",
                         "No matching restaurants. Try turning off “Only places open now” or choosing more areas."))

        spin = ss.get("food_spin")
        if spin:
            animate = ss.pop("food_anim", False)
            html(reel_html(spin, animate))
            winner = next((r for r in rests if r["id"] == spin["winner_id"]), None)
            if winner:
                html(f'<div class="spin-result{" anim" if animate else ""}">'
                     f'{restaurant_card(winner, stats[winner["id"]])}</div>')


# ---------- 頁面 ----------
def render() -> None:
    html(_CSS)
    hero(t("校園餐廳", "Restaurants"), t("營業時間一覽　·　選擇困難就交給轉盤", "Opening hours　·　Can't decide? Spin the wheel"), "food")
    if "food_flash" in st.session_state:
        st.toast(st.session_state.pop("food_flash"), icon=":material/check_box:")
    if "food_flash_del" in st.session_state:
        st.toast(st.session_state.pop("food_flash_del"), icon=":material/delete:")
    data = load_data()
    mine = my_restaurants(_auto_refresh(load_mine()))
    rests = all_restaurants(data) + mine
    if data.get("error"):
        st.warning(data["error"] + (t("（目前顯示離線備份資料）", " (showing offline backup data)") if data.get("offline") and rests else ""))
    if not rests:
        st.info(t("目前沒有餐廳資料，請稍後再試。", "No restaurant data right now. Please try again later."))
    now = datetime.now()
    stats = {r["id"]: status(r, now) for r in rests}
    buildings = list(dict.fromkeys(r["building"] for r in rests))
    focus = st.session_state.pop("food_focus", None)  # 從首頁點了某間餐廳：在「全部」分頁標出來並捲過去
    if focus not in stats:
        focus = None
    elif st.session_state.get("food_q"):
        st.session_state.food_q = ""  # 清掉搜尋字，避免那間店被篩掉

    left, right = st.columns([3, 1.1])
    with right:
        _add_box(mine)
    if rests:
        with left:
            _roulette(rests, stats, buildings)

        n_open = sum(stats[r["id"]]["is_open"] for r in rests if r["is_food"])
        n_food = sum(r["is_food"] for r in rests)
        open_txt = t(f"現在營業 {n_open} / {n_food} 間餐廳", f"{n_open} of {n_food} open now")
        st.markdown(f"#### {icon('clock') or '🕘'} {t('營業時間', 'Opening hours')}　{badge(open_txt, '#2E9E6A', live=n_open > 0)}",
                    unsafe_allow_html=True)
        f1, f2, f3 = st.columns([3, 1.3, 1.3], vertical_alignment="bottom")
        q = f1.text_input(t("搜尋", "Search"), placeholder=t("店名或位置，例如：咖哩、風雲2樓", "Name or location (in Chinese), e.g. 咖哩"),
                          key="food_q",
                          label_visibility="collapsed")
        open_only = f2.toggle(t("只看營業中", "Open now only"), key="food_open_only")
        show_service = f3.toggle(t("顯示服務類店家", "Show services"), key="food_service")

        def match(r: dict) -> bool:
            if not show_service and not r["is_food"]:
                return False
            if open_only and not stats[r["id"]]["is_open"]:
                return False
            if q.strip():
                hay = f'{r["name"]} {r.get("area", "")} {r["building"]}'.casefold()
                return all(w in hay for w in q.casefold().split())
            return True

        order = {"open": 0, "closing": 1, "later": 2, "done": 3, "closed": 4, "unknown": 5}
        tabs = st.tabs([t("全部", "All")] + buildings)
        for tab, bname in zip(tabs, [None] + buildings):
            with tab:
                items = [r for r in rests if (bname is None or r["building"] == bname) and match(r)]
                items.sort(key=lambda r: order[stats[r["id"]]["key"]])
                if not items:
                    st.info(t("沒有符合條件的店家。", "No matching places."))
                    continue
                html('<div class="food-grid">' + "".join(
                    restaurant_card(r, stats[r["id"]], "food-focus" if bname is None and r["id"] == focus else "")
                    for r in items) + "</div>")
        if focus:
            scroll_to(".food-focus")

    with st.container(key="food_info"), st.expander(label("info", t("資料來源與更新", "Data source & updates"))):
        st.markdown(t(f"資料來自 [NTHU Data API](https://api.nthusa.tw/docs)（整理自 [清華總務處經營管理組 — 餐廳及服務性廠商]({SOURCE_URL})），每小時自動更新。",
                      f"Data from the [NTHU Data API](https://api.nthusa.tw/docs) (based on [NTHU General Affairs — Restaurants & services]({SOURCE_URL})), refreshed hourly."))
        st.caption(t("營業狀態是從營業時間文字推算的；國定假日、寒暑假與臨時公休請以店家公告為準。",
                     "Open/closed status is inferred from the listed hours; check with each shop for holidays and closures."))
        if st.button(label("refresh", t("立即更新", "Refresh now")), key="food_refresh"):
            new = load_data(refresh=True)
            st.session_state.pop("food_spin", None)
            if not new.get("offline"):
                n = sum(len(b.get("restaurants", [])) for b in new["buildings"])
                st.session_state.food_flash = t(f"已更新 {n} 間店家", f"Updated {n} places")
            st.rerun()


FEATURE = Feature(title="校園餐廳", icon="🍱", render=render, slug="food", ico="food", title_en="Restaurants")
