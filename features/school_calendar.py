"""🗓️ 學校行事曆：清華大學行事曆與圖書館開館日曆（資料來自 NTHU Data API 的 /calendars）。

也提供首頁跑馬燈用的 next_event() / marquee_html()。
"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta

import streamlit as st

from config import WEEKDAYS
from core import nthu_api
from core.ui import badge, card, empty, esc, hero, html
from features.base import Feature

MAIN_CAL = "academic"  # 學校行事曆；首頁跑馬燈用它
PAST_DAYS = 180  # 「顯示已結束」最多往回看幾天
PAGE_SIZE = 60  # 一次列出幾筆，按「顯示更多」再加
SOON_DAYS = 14  # 幾天內的事件顯示倒數標籤
DEFAULT_CALS = [{"id": "academic", "name": "國立清華大學行事曆"}, {"id": "library-main", "name": "總圖書館開館行事曆"},
                {"id": "library-hss", "name": "人社分館開館行事曆"}, {"id": "library-nanda", "name": "南大分館開館行事曆"}]
CAL_COLOR = {"academic": "#6C63FF", "library-main": "#2C8BC9", "library-hss": "#E08A1E", "library-nanda": "#2E9E6A"}

CSS = """<style>
.cal-en{display:block;font-weight:400;font-size:.8rem;opacity:.6;margin-top:2px}
.cal-row .t{flex:1;min-width:0}
.cal-row .e{flex:none}
.cal-next .big{margin:2px 0 6px}
</style>"""

# 首頁跑馬燈樣式
MARQUEE_CSS = """<style>
.mq{display:flex;align-items:center;gap:12px;margin:4px 0 14px;padding:9px 14px;border-radius:14px;
  background:var(--card-bg);border:1px solid var(--line);box-shadow:0 6px 22px rgba(30,20,90,.07);animation:fadeUp .45s var(--ease) both}
.mq .badge{flex:none}
.mq .track{flex:1;min-width:0;overflow:hidden;white-space:nowrap;
  -webkit-mask-image:linear-gradient(90deg,transparent,#000 3%,#000 97%,transparent);
          mask-image:linear-gradient(90deg,transparent,#000 3%,#000 97%,transparent)}
.mq .roll{display:inline-block;padding-left:100%;font-weight:600;animation:mqScroll 20s linear infinite}
.mq:hover .roll{animation-play-state:paused}
.mq .when{color:var(--acc-text);font-weight:800;margin-right:10px}
.mq .en{opacity:.6;font-weight:400;margin-left:10px}
@keyframes mqScroll{from{transform:translateX(0)}to{transform:translateX(-100%)}}
@media (prefers-reduced-motion:reduce){.mq .roll{padding-left:0}}
</style>"""

_CJK = re.compile(r"[　-〿㐀-鿿＀-￯]")
_CLOSERS = ")）】」』"


# ---------- 資料 ----------
def split_title(title: str) -> tuple[str, str]:
    """學校行事曆的標題是「中文English」黏在一起，拆成 (中文, 英文)；拆不出來就 (原標題, "")。"""
    last = None
    for m in _CJK.finditer(title):
        last = m.end()
    if last is None:
        return title, ""
    while last < len(title) and title[last] in _CLOSERS:
        last += 1
    zh, en = title[:last].strip(), title[last:].strip()
    return (zh, en) if re.search(r"[A-Za-z]", en) else (title.strip(), "")


def _parse(value: str) -> datetime | None:
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return dt.astimezone().replace(tzinfo=None) if dt.tzinfo else dt


def _normalize(raw: dict, split: bool) -> dict | None:
    start, end = _parse(raw.get("start")), _parse(raw.get("end"))
    if not start:
        return None
    all_day = bool(raw.get("all_day")) or len(str(raw.get("start"))) == 10
    end = end or start
    if all_day or (end.time() == datetime.min.time() and end.date() > start.date()):
        last = max(start.date(), end.date() - timedelta(days=1))  # 全天事件的 end 是「隔天」，不含當天
    else:
        last = end.date()
    title = str(raw.get("title") or "（無標題）")
    zh, en = split_title(title) if split else (title, "")
    return {"id": raw.get("id"), "title": title, "zh": zh, "en": en, "start": start.date(), "last": last,
            "time": None if all_day else f"{start:%H:%M}–{end:%H:%M}", "description": raw.get("description")}


def list_calendars() -> list[dict]:
    data, _ = nthu_api.get("/calendars", ttl=86400)
    cals = [c for c in data or [] if isinstance(c, dict) and c.get("id")]
    return cals or DEFAULT_CALS


def load_events(cal_id: str, today: date) -> tuple[list[dict], str | None]:
    """從 PAST_DAYS 天前開始的所有事件（依開始日排序）。"""
    data, err = nthu_api.get(f"/calendars/{cal_id}/events",
                             {"start": (today - timedelta(days=PAST_DAYS)).isoformat(), "limit": 1000}, ttl=3600)
    events = [e for e in (_normalize(r, cal_id == MAIN_CAL) for r in data or [] if isinstance(r, dict)) if e]
    events.sort(key=lambda e: (e["start"], e["time"] or "", e["title"]))
    return events, err


def next_event(today: date) -> dict | None:
    """學校行事曆中，今天或之後開始的第一個事件。"""
    events, _ = load_events(MAIN_CAL, today)
    return next((e for e in events if e["start"] >= today), None)


# ---------- 顯示 ----------
def day_label(d: date) -> str:
    return f"{d:%m/%d}（{WEEKDAYS[d.weekday()]}）"


def range_label(e: dict) -> str:
    text = day_label(e["start"])
    if e["last"] != e["start"]:
        text += f" – {day_label(e['last'])}"
    return text + (f" {e['time']}" if e["time"] else "")


def countdown(e: dict, today: date) -> str:
    days = (e["start"] - today).days
    return "今天" if days == 0 else "明天" if days == 1 else f"{days} 天後"


def status_badge(e: dict, today: date) -> str:
    if e["last"] < today:
        return badge("已結束", "#888888")
    if e["start"] <= today:
        return badge("今天" if e["start"] == e["last"] else "進行中", "#2E9E6A", live=True)
    if (e["start"] - today).days <= SOON_DAYS:
        return badge(countdown(e, today), "#E5486F" if (e["start"] - today).days <= 3 else "#6C63FF")
    return ""


def marquee_html(today: date) -> str:
    """首頁跑馬燈：學校行事曆接下來的一個事件。沒有資料時回傳空字串（首頁就不顯示）。"""
    e = next_event(today)
    if not e:
        return ""
    en = f'<span class="en">{esc(e["en"])}</span>' if e["en"] else ""
    return (f'{MARQUEE_CSS}<div class="mq">{badge("行事曆 · " + countdown(e, today), "#6C63FF", live=True)}'
            f'<div class="track"><span class="roll"><span class="when">{esc(range_label(e))}</span>{esc(e["zh"])}{en}</span></div></div>')


def _row(e: dict, today: date) -> str:
    en = f'<span class="cal-en">{esc(e["en"])}</span>' if e["en"] else ""
    desc = f'<span class="cal-en">{esc(e["description"])}</span>' if e.get("description") else ""
    dim = " dim" if e["last"] < today else ""
    return (f'<div class="row cal-row{dim}"><span class="t">{esc(e["zh"])}{en}{desc}</span>'
            f'<span class="e">{esc(range_label(e))} {status_badge(e, today)}</span></div>')


def render() -> None:
    today = date.today()
    html(CSS)
    hero("學校行事曆", "清華大學行事曆　·　圖書館開館日曆　·　資料來源 NTHU Data API", "🗓️")

    cals = list_calendars()
    names = {c["id"]: c.get("name") or c["id"] for c in cals}
    cal_id = st.radio("行事曆", list(names), format_func=names.get, horizontal=True, label_visibility="collapsed")
    events, err = load_events(cal_id, today)
    if err:
        st.warning(err)
    color = CAL_COLOR.get(cal_id, "#6C63FF")

    nxt = next((e for e in events if e["start"] >= today), None)
    if nxt:
        en = f'<div class="muted">{esc(nxt["en"])}</div>' if nxt["en"] else ""
        html(card(f'<div class="card-head"><span class="card-title">⏭️ 接下來</span>'
                  f'{badge(countdown(nxt, today), color, live=True)}</div>'
                  f'<div class="big">{esc(nxt["zh"])}</div>{en}'
                  f'<div class="muted" style="margin-top:6px">🗓️ {esc(range_label(nxt))}</div>', "cal-next"))

    c1, c2 = st.columns([3, 1])
    keyword = c1.text_input("搜尋", placeholder="搜尋事件，例如：選課、期中、放假", label_visibility="collapsed")
    show_past = c2.toggle("顯示已結束", value=False)

    shown = [e for e in events if (show_past or e["last"] >= today)
             and (not keyword.strip() or keyword.strip().lower() in (e["title"] + (e["description"] or "")).lower())]
    if not shown:
        html(card(empty("🔍" if keyword else "📭", "找不到符合的事件" if keyword else "目前沒有事件")))
        return

    key = f"cal_limit_{cal_id}"
    limit = st.session_state.get(key, PAGE_SIZE)
    months: dict[tuple[int, int], list[dict]] = {}
    for e in shown[:limit]:
        months.setdefault((e["start"].year, e["start"].month), []).append(e)
    for (y, m), items in months.items():
        head = (f'<div class="card-head"><span class="card-title">{y} 年 {m} 月</span>'
                f'{badge(f"{len(items)} 件", color)}</div>')
        html(card(head + "".join(_row(e, today) for e in items)))

    if len(shown) > limit:
        if st.button(f"顯示更多（還有 {len(shown) - limit} 件）", use_container_width=True):
            st.session_state[key] = limit + PAGE_SIZE
            st.rerun()


FEATURE = Feature(title="學校行事曆", icon="🗓️", render=render, slug="school-calendar")
