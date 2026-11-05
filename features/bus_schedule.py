"""🚌 公車班表：班表放在 data/bus_schedule.json，直接編輯該檔即可更新。

JSON 結構：
{
  "origin": "出發地點（三條路線共用）",
  "routes": [
    {"name": "校內線 1", "type": "campus",    "note": "", "weekday": "07:30, 08:00", "weekend": ""},
    {"name": "校外線",   "type": "offcampus", "note": "", "weekday": "...",          "weekend": "..."}
  ]
}
weekday / weekend 可以寫成「逗號或空格分隔的字串」，也可以寫成陣列。
"""
import json
import re
from datetime import datetime

import pandas as pd
import streamlit as st

from config import DATA_DIR
from core.ui import badge, card, esc, hero, html
from features.base import Feature

DATA_FILE = "bus_schedule.json"
TIME_RE = re.compile(r"^(\d{1,2})[:：](\d{2})$")
DAY_LABELS = {"weekday": "平日", "weekend": "假日"}
KINDS = {  # type -> (顯示文字, 文字色, 背景色)
    "campus": ("校內", "#4B43D6", "#ECEAFF"),
    "offcampus": ("校外", "#C25E00", "#FFF0DC"),
}


# ---------- 資料邏輯 ----------
def _parse(value) -> tuple[list[str], list[str]]:
    """回傳 (合法時間 'HH:MM' 已排序去重, 無法辨識的項目)。"""
    if isinstance(value, str):
        value = re.split(r"[,\s，、;；]+", value.strip())
    good, bad = set(), []
    for item in value or []:
        item = str(item).strip()
        if not item:
            continue
        m = TIME_RE.match(item)
        if m and int(m.group(1)) < 24 and int(m.group(2)) < 60:
            good.add(f"{int(m.group(1)):02d}:{m.group(2)}")
        else:
            bad.append(item)
    return sorted(good), bad


def parse_times(value) -> list[str]:
    return _parse(value)[0]


def load_bus_data() -> tuple[dict, str | None]:
    """回傳 (資料, 錯誤訊息)。JSON 寫錯時給出明確提示，而不是靜默失敗。"""
    empty = {"origin": "", "routes": []}
    path = DATA_DIR / DATA_FILE
    if not path.exists():
        return empty, f"找不到 data/{DATA_FILE}"
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return empty, f"data/{DATA_FILE} 格式錯誤（第 {e.lineno} 行）：請檢查逗號與引號是否為半形"
    if isinstance(raw, list):  # 相容舊格式
        raw = {"routes": raw}
    return raw, None


def load_routes() -> list[dict]:
    return load_bus_data()[0].get("routes", [])


def day_key(now: datetime) -> str:
    return "weekday" if now.weekday() < 5 else "weekend"


def get_next_buses(route: dict, now: datetime | None = None,
                   day: str | None = None, n: int = 3) -> list[tuple[str, int]]:
    """回傳 [(發車時間, 幾分鐘後), ...]，最多 n 班。"""
    now = now or datetime.now()
    day = day or day_key(now)
    result = []
    for hhmm in parse_times(route.get(day, [])):
        h, m = map(int, hhmm.split(":"))
        dep = now.replace(hour=h, minute=m, second=0, microsecond=0)
        if dep >= now:
            result.append((hhmm, int((dep - now).total_seconds() // 60)))
    return result[:n]


def eta_text(mins: int) -> str:
    if mins < 1:
        return "即將發車"
    if mins >= 60:
        return f"{mins // 60} 小時 {mins % 60} 分後"
    return f"{mins} 分鐘後"


def kind_badge(route: dict) -> str:
    text, fg, bg = KINDS.get(route.get("type", "campus"), KINDS["campus"])
    return badge(text, fg, bg)


# ---------- 頁面 ----------
def route_card(route: dict, now: datetime, day: str) -> str:
    head = (f'<div class="card-head"><span class="card-title">🚌 {esc(route.get("name", "未命名"))}</span>'
            f'{kind_badge(route)}</div>')
    note = f'<div class="muted">{esc(route["note"])}</div>' if route.get("note") else ""
    if not parse_times(route.get(day, [])):
        body = '<div class="muted">尚未填寫班表，請編輯 data/bus_schedule.json</div>'
    else:
        nxt = get_next_buses(route, now, day)
        if nxt:
            body = "".join(f'<div class="row"><span class="t">{hhmm}</span>'
                           f'<span class="e">{eta_text(m)}</span></div>' for hhmm, m in nxt)
        else:
            body = '<div class="muted">今天已無班次</div>'
    return card(head + note + body)


def render() -> None:
    data, err = load_bus_data()
    origin = data.get("origin", "")
    hero("公車班表", f"📍 出發地：{origin}" if origin else "編輯 data/bus_schedule.json 更新班表", "🚌")

    if err:
        st.error(err)
    routes = data.get("routes", [])
    if not routes:
        st.warning("找不到班表，請編輯 data/bus_schedule.json")
        return

    for r in routes:  # 提醒填錯的時間格式
        for key in DAY_LABELS:
            _, bad = _parse(r.get(key, []))
            if bad:
                st.warning(f"{r.get('name', '?')}（{DAY_LABELS[key]}）有無法辨識的時間：{'、'.join(bad)}，請用 07:30 這種格式")

    now = datetime.now()
    day = st.radio("班表類型", list(DAY_LABELS), index=list(DAY_LABELS).index(day_key(now)),
                   format_func=DAY_LABELS.get, horizontal=True)

    tab_next, tab_all = st.tabs(["⏱️ 即將發車", "📋 完整時刻表"])

    with tab_next:
        for col, r in zip(st.columns(len(routes)), routes):
            with col:
                html(route_card(r, now, day))

    with tab_all:
        cols = st.columns(len(routes))
        for col, r in zip(cols, routes):
            with col:
                html(f'<div class="card-head"><span class="card-title">{esc(r.get("name", ""))}</span>'
                     f'{kind_badge(r)}</div>')
                times = parse_times(r.get(day, []))
                if times:
                    st.dataframe(pd.DataFrame({"發車時間": times}), hide_index=True,
                                 use_container_width=True)
                else:
                    st.caption("尚未填寫")


FEATURE = Feature(title="公車班表", icon="🚌", render=render, slug="bus")
