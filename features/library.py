"""📚 圖書館：空間即時使用狀況、各館開館時間、最新消息、失物招領（資料來自 NTHU Data API 的 /libraries）。"""
from __future__ import annotations

from datetime import date, timedelta
from email.utils import parsedate_to_datetime

import pandas as pd
import streamlit as st

from core import clock
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
@media (max-width:900px){.lib-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media (max-width:640px){.lib-grid{grid-template-columns:1fr}}
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


# ---------- 開館時間 ----------
def hours_tab() -> None:
    today = clock.today()
    st.caption(t("各館開館行事曆（含國定假日、考試週延長開放等）。",
                 "Opening hours of each library (including holidays and extended exam-week hours)."))
    cards = []
    for cal_id, name_zh, name_en in BRANCHES:
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
    html(f'<div class="lib-grid">{"".join(cards)}</div>')


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
