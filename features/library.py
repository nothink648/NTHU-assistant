"""📚 圖書館：空間即時使用狀況、各館開館時間、最新消息、失物招領（資料來自 NTHU Data API 的 /libraries）。"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from email.utils import parsedate_to_datetime

import pandas as pd
import streamlit as st

from core import nthu_api
from core.i18n import is_en, t, tr
from core.icons import before_css, icon, label, tab_css
from core.ui import badge, card, empty, esc, hero, html
from features.base import Feature
from features.school_calendar import CAL_COLOR, day_label, load_events

BRANCHES = [("library-main", "總圖書館", "Main Library"), ("library-hss", "人社分館", "HSS Library"),
            ("library-nanda", "南大分館", "Nanda Library")]
RSS_TYPES = {"news": ("最新消息", "News"), "eresources": ("電子資源", "E-resources"),
             "exhibit": ("展覽活動", "Exhibitions & events"), "branches": ("分館消息", "Branch news")}
# 空間類型的英文名稱（API 只有中文）；區域名稱裡出現的類型名稱也會一起換掉
SPACE_EN = {"人社分館享時小間": "HSS Library Study Pods", "人社分館討論室": "HSS Library Discussion Rooms",
            "電腦共學區及語言學習區": "Computer & Language Learning Area", "簡報練習室": "Presentation Practice Room",
            "研究小間": "Research Carrel", "討論室": "Discussion Room", "聆賞席": "Listening Seats", "團體室": "Group Room",
            "享時小間": "Study Pod", "夜讀區": "Night Study Area", "資訊島": "Info Island", "單人": "Single ",
            "雙人": "Double ", "多人": "Group ", "小舞台": "Small Stage", "人社": "HSS ", "科管院": "CTM "}
LOST_COLS = {"拾獲時間": "Found on", "拾獲地點": "Location", "描述": "Description"}


def space_name(text: str) -> str:
    """空間 / 區域名稱：英文介面把已知的中文詞換成英文（例如 3F-討論室 → 3F-Discussion Room）。"""
    if not is_en():
        return text
    for zh in sorted(SPACE_EN, key=len, reverse=True):
        text = text.replace(zh, SPACE_EN[zh])
    return text.strip()
HOURS_DAYS = 7  # 開館時間列出今天起幾天
BOOKING_URL = "https://libsms.lib.nthu.edu.tw/"  # 圖書館空間管理系統（讀者登入後預約研究小間、討論室等）

CSS = """<style>
.lib-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px;align-items:stretch}
.lib-grid>.card{margin:0;height:100%}
.lib-grid .row .t{font-weight:600}
.lib-today{font-weight:700;line-height:1.5;margin-bottom:6px}
.lib-today div{padding:2px 0}
.rss-body{white-space:pre-wrap;line-height:1.65;font-size:.92rem}
.lib-grid.two{grid-template-columns:repeat(2,minmax(0,1fr));margin-top:14px}
/* 總圖：整列寬，分成「總圖」「夜讀區」兩區，各自一條 24 小時時間軸 */
.card.lib-main{margin:0}
.zp-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px;margin-top:6px}
.zp{border:1px solid var(--line);border-radius:14px;padding:12px 14px;
  background:linear-gradient(135deg,color-mix(in srgb,var(--zc) 10%,transparent),transparent 70%)}
.zp .card-title .ico{color:var(--zc)}
.zp-today{font-size:1.35rem;font-weight:800;margin:4px 0 2px;display:flex;align-items:baseline;gap:8px}
.zp-today small{font-size:.75rem;font-weight:600;opacity:.6}
.zp-note{font-size:.8rem;color:#E5486F;margin-bottom:4px}
.zp-note .ico{width:1em;height:1em;vertical-align:-.15em}
.tl{position:relative;height:10px;border-radius:999px;background:color-mix(in srgb,currentColor 9%,transparent);overflow:hidden}
.tl.big{height:18px;margin-top:8px}
.tl .seg{position:absolute;top:0;bottom:0;border-radius:999px;opacity:.85}
.tl .seg.carry{opacity:.45}
.tl .now{position:absolute;top:-2px;bottom:-2px;width:2px;margin-left:-1px;background:#E5486F;border-radius:2px;
  box-shadow:0 0 0 2px color-mix(in srgb,#E5486F 25%,transparent)}
.tl-axis{display:flex;justify-content:space-between;font-size:.68rem;opacity:.5;margin:2px 1px 8px}
.zp-row{display:grid;grid-template-columns:92px minmax(0,1fr) max-content;gap:10px;align-items:center;padding:5px 0;
  border-top:1px dashed var(--line);font-size:.82rem}
.zp-d{font-weight:600;white-space:nowrap}
.zp-h{text-align:right;line-height:1.3}
.zp-tag{display:block;font-size:.7rem;color:#E08A1E}
@media (max-width:900px){.lib-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.zp-grid{grid-template-columns:1fr}}
@media (max-width:640px){.lib-grid,.lib-grid.two{grid-template-columns:1fr}.zp-row{grid-template-columns:70px minmax(0,1fr) max-content}}
</style>"""


# ---------- 空間使用 ----------
def spaces_tab() -> None:
    c1, c2 = st.columns([4, 1])
    c1.caption(t("各區目前可使用的數量，資料即時取自圖書館空間系統（約每分鐘更新）。",
                 "Available spaces right now, live from the library space system (updated about every minute)."))
    refresh = c2.button(label("refresh", t("重新整理", "Refresh")), use_container_width=True, key="lib_space_refresh")
    data, err = nthu_api.get("/libraries/spaces", ttl=60, refresh=refresh)
    if err:
        st.warning(err)
    rows = [r for r in data or [] if isinstance(r, dict)]
    if not rows:
        html(card(empty(icon("mail-box") or "📭", t("目前查不到空間資料", "No space data available"))))
        return

    groups: dict[str, list[dict]] = {}
    for r in sorted(rows, key=lambda r: (r.get("spacetype") or 0, str(r.get("zoneid") or ""))):
        groups.setdefault(str(r.get("spacetypename") or t("其他", "Other")), []).append(r)
    cards = []
    for name, zones in groups.items():
        total = sum(int(z.get("count") or 0) for z in zones)
        head = (f'<div class="card-head"><span class="card-title">{esc(space_name(name))}</span>'
                f'{badge(t(f"共 {total} 可用", f"{total} available"), "#2E9E6A" if total else "#888888")}</div>')
        lines = ""
        for z in zones:
            n = int(z.get("count") or 0)
            lines += (f'<div class="row"><span class="t">{esc(space_name(z.get("zonename") or z.get("zoneid") or ""))}</span>'
                      f'<span class="e">{badge(t(f"可用 {n}", f"{n} free"), "#2E9E6A" if n else "#888888")}</span></div>')
        cards.append(card(head + lines))
    html(f'<div class="lib-grid">{"".join(cards)}</div>')


# ---------- 開館時間：總圖（總圖 / 夜讀區 時間軸） ----------
# 夜讀區的行事曆常只寫「～隔日 09:00」，沒寫開始時間時用館方規定的 17:00～隔日 09:00
NIGHT_START, NIGHT_END = 17 * 60, 9 * 60
_TM = r"(\d{1,2})[:：](\d{2})"
ZONES = {"main": ("總圖", "Main Library", "book", "#2C8BC9"),
         "night": ("夜讀區", "Moonlight Study Area", "night", "#7B61FF")}


def _zone(title: str) -> str:
    return "night" if ("夜讀" in title or "moonlight" in title.lower()) else "main"


def _mins(h: str, m: str) -> int:
    return int(h) * 60 + int(m)


def parse_lib_title(title: str) -> tuple[list[tuple[int, int]], bool]:
    """行事曆標題 → (開放區間[(開始分, 結束分)]，結束超過 1440 代表開到隔日；今天是否閉館)。

    例：「總圖 Main Library 08:00-22:00」「夜讀區～隔日(Next Day)09:00」「夜讀區_期末考 13:30～隔日12:00」
        「夜讀區_17:00恢復服務」「❌夜讀區_09:00起閉館 CLOSED-端午節」
    """
    s = title.replace("～", "~")
    if "恢復" in s or "resume" in s.lower():  # 閉館後恢復：從那個時間開到隔天早上
        m = re.search(_TM, s)
        start = _mins(*m.groups()) if m else NIGHT_START
        end = 12 * 60 if re.search(r"期[中末]考|season", s, re.I) else NIGHT_END  # 考試週開到隔天中午
        return [(start, end + 1440)], False
    if "❌" in s or re.search(r"closed", s, re.I):
        return [], True
    if "~" in s:
        left, right = s.split("~", 1)
        lt, rt = re.findall(_TM, left), re.findall(_TM, right)
        start = _mins(*lt[-1]) if lt else NIGHT_START
        end = _mins(*rt[0]) if rt else NIGHT_END
        if "隔日" in right or "next" in right.lower() or end <= start:
            end += 1440
        return [(start, end)], False
    m = re.search(_TM + r"\s*[-–]\s*" + _TM, s)
    if m:
        a, b = _mins(m[1], m[2]), _mins(m[3], m[4])
        return [(a, b if b > a else b + 1440)], False
    return [], False


def _note(title: str, closed: bool) -> str:
    """特別說明：考試週延長、閉館原因。"""
    if "期末考" in title:
        return t("期末考延長開放", "Finals season hours")
    if "期中考" in title:
        return t("期中考延長開放", "Midterm season hours")
    if closed:
        if is_en():
            m = re.search(r"\(([^)]*)\)?", title)
            return m[1].strip() if m else "Closed"
        m = re.search(r"(?:CLOSED|閉館)[\s\-_－]*([一-鿿][一-鿿\-－]*)", title)
        return m[1] if m else ""
    return ""


def zone_day(events: list[dict], zone: str, d: date) -> dict:
    """某一區某一天：{iv: 開放區間, closed, note, raw: 看不懂的標題}。"""
    iv, closed, notes, raw = [], False, [], []
    for e in events:
        if e["start"] <= d <= e["last"] and _zone(e["title"]) == zone:
            ivs, c = parse_lib_title(e["title"])
            iv += ivs
            closed = closed or c
            if n := _note(e["title"], c):
                notes.append(n)
            if not ivs and not c:
                raw.append(e["title"])
    return {"iv": sorted(iv), "closed": closed and not iv, "note": "、".join(dict.fromkeys(notes)), "raw": raw}


def _hm(m: int) -> str:
    nxt = m > 1440  # 隔天的時間（24:00 本身算當天）
    m = m - 1440 if nxt else m
    text = "24:00" if m == 1440 else f"{m // 60:02d}:{m % 60:02d}"
    return t(f"隔日 {text}", f"{text} next day") if nxt else text


def _hours_text(day: dict) -> str:
    if day["iv"]:
        return t("、", ", ").join(f"{_hm(s)}–{_hm(e)}" for s, e in day["iv"])
    if day["closed"]:
        return t("閉館", "Closed")
    return " / ".join(day["raw"]) or "—"


def _segments(today: dict, yesterday: dict) -> list[tuple[int, int, bool]]:
    """畫在 0–24 時間軸上的區段 (開始, 結束, 是否為前一天延續過來)。"""
    seg = [(0, e - 1440, True) for s, e in yesterday["iv"] if e > 1440]
    seg += [(s, min(e, 1440), False) for s, e in today["iv"]]
    return seg


def _bar(segs: list[tuple[int, int, bool]], color: str, now: int | None = None, big: bool = False) -> str:
    parts = "".join(
        f'<i class="seg{" carry" if carry else ""}" style="left:{s / 14.4:.2f}%;width:{max(e - s, 0) / 14.4:.2f}%;'
        f'background:{color}"></i>' for s, e, carry in segs)
    if now is not None:
        parts += f'<i class="now" style="left:{now / 14.4:.2f}%"></i>'
    return f'<div class="tl{" big" if big else ""}">{parts}</div>'


def _status(day: dict, prev: dict, cur: int) -> tuple[str, str, bool]:
    """(文字, 顏色, 是否開放中)。"""
    live = [(0, e - 1440) for s, e in prev["iv"] if e > 1440 and cur < e - 1440]
    live += [(s, e) for s, e in day["iv"] if s <= cur < e]
    if live:
        end = max(e for _, e in live)
        color = "#E08A1E" if end - cur <= 30 else "#2E9E6A"
        return t(f"開放中 · 至 {_hm(end)}", f"Open · until {_hm(end)}"), color, True
    later = [s for s, _ in day["iv"] if s > cur]
    if later:
        return t(f"{_hm(min(later))} 開放", f"Opens at {_hm(min(later))}"), "#2C8BC9", False
    if day["closed"]:
        return t("今日閉館", "Closed today"), "#E5486F", False
    return t("今日已關閉", "Closed for today"), "#8A8A9A", False


def _zone_panel(events: list[dict], zone: str, today: date, cur: int) -> str:
    zh, en, ico, color = ZONES[zone]
    days = [zone_day(events, zone, today + timedelta(days=i)) for i in range(-1, HOURS_DAYS)]
    prev, now_day = days[0], days[1]
    text, scolor, live = _status(now_day, prev, cur)
    note = f'<div class="zp-note">{icon("warning") or "⚠️"} {esc(now_day["note"])}</div>' if now_day["note"] else ""
    axis = "".join(f"<span>{h}</span>" for h in (0, 6, 12, 18, 24))
    rows = ""
    for i in range(1, HOURS_DAYS):
        d, prv = days[i + 1], days[i]
        tag = f'<span class="zp-tag">{esc(d["note"])}</span>' if d["note"] else ""
        rows += (f'<div class="zp-row"><span class="zp-d">{day_label(today + timedelta(days=i))}</span>'
                 f'{_bar(_segments(d, prv), color)}<span class="zp-h">{esc(_hours_text(d))}{tag}</span></div>')
    return (f'<div class="zp" style="--zc:{color}"><div class="card-head"><span class="card-title">{icon(ico)}{t(zh, en)}</span>'
            f'{badge(text, scolor, live=live)}</div>'
            f'<div class="zp-today"><small>{t("今天", "Today")}</small>{esc(_hours_text(now_day))}</div>{note}'
            f'{_bar(_segments(now_day, prev), color, now=cur, big=True)}<div class="tl-axis">{axis}</div>'
            f'<div class="sub"><span>{icon("event")}{t("接下來幾天", "Next few days")}</span></div>{rows}</div>')


def main_library_card(events: list[dict], err: str | None, today: date) -> str:
    head = f'<div class="card-head"><span class="card-title">{icon("book")}{t("總圖書館", "Main Library")}</span></div>'
    if err and not events:
        return card(head + empty(icon("warning") or "⚠️", t("暫時查不到", "Unavailable right now")))
    now = datetime.now()
    cur = now.hour * 60 + now.minute
    panels = "".join(_zone_panel(events, z, today, cur) for z in ZONES)
    return card(head + f'<div class="zp-grid">{panels}</div>', cls="lib-main")


# ---------- 開館時間 ----------
def hours_tab() -> None:
    today = date.today()
    st.caption(t("各館開館行事曆（含國定假日、考試週延長開放等）。",
                 "Opening hours of each library (including holidays and extended exam-week hours)."))
    events, err = load_events("library-main", today)
    html(main_library_card(events, err, today))
    cards = []
    for cal_id, name_zh, name_en in BRANCHES[1:]:
        name = t(name_zh, name_en)
        events, err = load_events(cal_id, today)
        color = CAL_COLOR.get(cal_id, "#6C63FF")
        if err and not events:
            cards.append(card(f'<div class="card-head"><span class="card-title">{icon("book")}{name}</span></div>'
                              + empty(icon("warning") or "⚠️", t("暫時查不到", "Unavailable right now"))))
            continue

        def on(d: date) -> list[str]:
            return [e["title"] for e in events if e["start"] <= d <= e["last"]]

        now_titles = on(today)
        head = f'<div class="card-head"><span class="card-title">{icon("book")}{name}</span>{badge(t("今天", "Today"), color, live=True)}</div>'
        today_html = ('<div class="lib-today">' + "".join(f"<div>{esc(x)}</div>" for x in now_titles) + "</div>"
                      if now_titles else empty(icon("mail-box") or "📭", t("今天沒有登錄的開館資訊", "No hours listed for today")))
        rows = []
        for i in range(1, HOURS_DAYS):
            d = today + timedelta(days=i)
            titles = on(d)
            rows.append(f'<div class="row"><span class="t">{day_label(d)}</span>'
                        f'<span class="e">{"<br>".join(esc(x) for x in titles) or "—"}</span></div>')
        nxt = t("接下來幾天", "Next few days")
        cards.append(card(head + today_html + f'<div class="sub"><span>{icon("event")}{nxt}</span></div>' + "".join(rows)))
    html(f'<div class="lib-grid two">{"".join(cards)}</div>')


# ---------- 最新消息 ----------
def _pub_date(text: str) -> str:
    try:
        return f"{parsedate_to_datetime(text):%Y/%m/%d}"
    except (TypeError, ValueError):
        return ""


def _links(text) -> list[str]:
    """link 可能是「逗號分隔的多個網址」，只留下 http(s) 開頭的。"""
    return [u.strip() for u in str(text or "").split(",") if u.strip().lower().startswith(("http://", "https://"))]


def news_tab() -> None:
    kind = st.radio(t("類別", "Category"), list(RSS_TYPES), format_func=lambda k: t(*RSS_TYPES[k]), horizontal=True, label_visibility="collapsed")
    data, err = nthu_api.get(f"/libraries/rss/{kind}", ttl=1800)
    if err:
        st.warning(err)
    items = [x for x in data or [] if isinstance(x, dict) and x.get("title")]
    if not items:
        html(card(empty(icon("mail-box") or "📭", t("目前沒有消息", "No news"))))
        return
    for x in items:
        day = _pub_date(x.get("pubDate"))
        with st.expander(f"{day}　{x['title']}" if day else x["title"]):
            meta = " ".join(b for b in (badge(x["category"], "#2C8BC9") if x.get("category") else "",
                                        f'<span class="muted">{esc(x["author"])}</span>' if x.get("author") else "") if b)
            if meta:
                html(meta)
            img = (x.get("image") or {}).get("url") if isinstance(x.get("image"), dict) else None
            if img and str(img).lower().startswith("https://"):
                st.image(img, width=360)
            if x.get("description"):
                html(f'<div class="rss-body">{esc(x["description"])}</div>')
            links = _links(x.get("link"))
            if links:
                html('<div class="links">' + "".join(
                    f'<a class="link-chip" href="{esc(u)}" target="_blank" rel="noopener">{icon("link") or "🔗"} {t("連結", "Link")} {i}</a>'
                    for i, u in enumerate(links, 1)) + "</div>")


# ---------- 失物招領 ----------
def lost_tab() -> None:
    st.caption(t("圖書館近六個月拾獲的物品。", "Items found in the library over the past six months."))
    data, err = nthu_api.get("/libraries/lost-and-found", ttl=600)
    if err:
        st.warning(err)
    rows = [r for r in data or [] if isinstance(r, dict)]
    if not rows:
        html(card(empty(icon("mail-box") or "📭", t("目前沒有失物資料", "No lost items"))))
        return
    df = pd.DataFrame(rows).reindex(columns=["拾獲時間", "拾獲地點", "描述"]).fillna("")
    c1, c2 = st.columns([2, 1])
    keyword = c1.text_input(t("搜尋物品", "Search items"),
                            placeholder=t("例如：水壺、外套、悠遊卡", "Item descriptions are in Chinese, e.g. 水壺 (bottle)"))
    places = [t("全部地點", "All locations")] + sorted(p for p in df["拾獲地點"].unique() if p)
    place = c2.selectbox(t("拾獲地點", "Location"), places)
    if keyword.strip():
        df = df[df["描述"].str.contains(keyword.strip(), case=False, regex=False)]
    if place != places[0]:
        df = df[df["拾獲地點"] == place]
    html(badge(t(f"{len(df)} 件", f"{len(df)} items"), "#E08A1E"))
    st.dataframe(df.rename(columns={k: tr(v) for k, v in LOST_COLS.items()}) if is_en() else df, hide_index=True, use_container_width=True)


def render() -> None:
    html(CSS + "<style>" + before_css(".st-key-lib_space_refresh button p", "refresh", size="1em")
         + before_css(".st-key-lib_booking a p", "event")
         + tab_css("lib_tabs", ["chair", "clock", "news", "search"]) + "</style>")
    hero(t("圖書館", "Library"), t("空間使用　·　開館時間　·　最新消息　·　失物招領　·　資料來源 NTHU Data API",
                                  "Spaces　·　Hours　·　News　·　Lost & found　·　Source: NTHU Data API"), "book")
    c1, c2 = st.columns([3, 1], vertical_alignment="center")
    c1.caption(t("研究小間、討論室、簡報練習室等空間需登入圖書館空間管理系統預約。",
                 "Research carrels, discussion rooms and practice rooms are booked through the library space system."))
    with c2.container(key="lib_booking"):
        st.link_button(label("event", t("前往預約空間", "Book a space")), BOOKING_URL, type="primary",
                       use_container_width=True)
    with st.container(key="lib_tabs"):
        t1, t2, t3, t4 = st.tabs([label("chair", t("空間使用", "Spaces")), label("clock", t("開館時間", "Hours")),
                                  label("news", t("最新消息", "News")), label("search", t("失物招領", "Lost & found"))])
    with t1:
        spaces_tab()
    with t2:
        hours_tab()
    with t3:
        news_tab()
    with t4:
        lost_tab()


FEATURE = Feature(title="圖書館", icon="📚", render=render, slug="library", ico="book", title_en="Library")
