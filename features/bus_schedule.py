"""🚌 公車班表：班表放在 data/bus_schedule.json，直接編輯該檔即可更新。

JSON 結構（每條路線有一到多個「方向」，每個方向有自己的出發地與時刻表）：
{
  "routes": [
    {"name": "綠線", "type": "campus", "color": "#2E9E6A", "note": "Green Line",
     "directions": [
       {"name": "上山", "origin": "校門口", "weekday": "07:30, 08:00"},
       {"name": "下山", "origin": "台積館", "weekday": "07:45, 08:15"}
     ]},
    {"name": "南大線一", "type": "nanda", "color": "#2F7FD8", "note": "經台積館",
     "directions": [
       {"name": "往南大", "origin": "北校門口", "stops": ["北校門口", "…", "南大校區"],
        "weekday": "07:30※, 10:55♦", "weekend": "09:00"}
     ]}
  ]
}
weekday（平日）/ weekend（假日）可以寫成「逗號或空格分隔的字串」，也可以寫成陣列。
時間後面可加註記：♦ 週五停駛、※ 付費市區公車 83 號（見 MARKS）。
color（選填，#RRGGBB）是路線在頁面上的標示顏色；沒寫就依 type 決定。
stops（選填）是停靠站，會顯示在完整時刻表。
"""
from __future__ import annotations

import json
import re
from datetime import datetime

import pandas as pd
import streamlit as st

from config import DATA_DIR
from core.ui import badge, empty, esc, hero, html
from features.base import Feature

DATA_FILE = "bus_schedule.json"
MARKS = {"♦": "週五停駛", "※": "付費 83 號"}  # 時間後面的註記
TIME_RE = re.compile(r"^(\d{1,2})[:：](\d{2})([" + "".join(MARKS) + r"]*)$")
SERVICE_DAYS = {"weekday": "平日", "weekend": "假日"}
DIR_ICONS = {"上山": "⬆️", "下山": "⬇️", "往南大": "➡️", "往校本部": "⬅️"}
KINDS = {  # type -> (顯示文字, 主色)
    "campus": ("校內", "#6C63FF"),
    "offcampus": ("校外", "#E08A1E"),
    "nanda": ("南大校區", "#2F7FD8"),
}
PER_ROW = 3  # 「即將發車」每列最多幾張卡片


# ---------- 資料邏輯 ----------
def _parse(value) -> tuple[list[tuple[str, str]], list[str]]:
    """回傳 ([(時間 'HH:MM', 註記), ...] 已排序去重, 無法辨識的項目)。"""
    if isinstance(value, str):
        value = re.split(r"[,\s，、;；]+", value.strip())
    good, bad = {}, []
    for item in value or []:
        item = str(item).strip()
        if not item:
            continue
        m = TIME_RE.match(item)
        if m and int(m.group(1)) < 24 and int(m.group(2)) < 60:
            hhmm = f"{int(m.group(1)):02d}:{m.group(2)}"
            good[hhmm] = "".join(sorted(set(good.get(hhmm, "") + m.group(3))))
        else:
            bad.append(item)
    return sorted(good.items()), bad


def parse_entries(value) -> list[tuple[str, str]]:
    return _parse(value)[0]


def parse_times(value) -> list[str]:
    return [t for t, _ in parse_entries(value)]


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


def get_directions(route: dict, default_origin: str = "") -> list[dict]:
    """回傳路線的各方向。相容舊格式（路線底下直接放 weekday，視為單一方向）。"""
    dirs = route.get("directions")
    if isinstance(dirs, list) and dirs:
        return [d for d in dirs if isinstance(d, dict)]
    return [{"name": "發車", "origin": route.get("origin", default_origin),
             "weekday": route.get("weekday", [])}]


def day_key(now: datetime) -> str:
    return "weekday" if now.weekday() < 5 else "weekend"


def is_service_day(now: datetime) -> bool:
    return day_key(now) in SERVICE_DAYS


def runs_today(mark: str, now: datetime) -> bool:
    """♦ 的班次週五停駛。"""
    return not ("♦" in mark and now.weekday() == 4)


def get_next_buses(direction: dict, now: datetime | None = None,
                   day: str | None = None, n: int = 3) -> list[tuple[str, int, str]]:
    """回傳 [(發車時間, 幾分鐘後, 註記), ...]，最多 n 班。direction 為一個方向（含 weekday / weekend 欄位）。"""
    now = now or datetime.now()
    day = day or day_key(now)
    if day not in SERVICE_DAYS:
        return []
    result = []
    for hhmm, mark in parse_entries(direction.get(day, [])):
        if not runs_today(mark, now):
            continue
        h, m = map(int, hhmm.split(":"))
        dep = now.replace(hour=h, minute=m, second=0, microsecond=0)
        if dep >= now:
            result.append((hhmm, int((dep - now).total_seconds() // 60), mark))
    return result[:n]


def eta_text(mins: int) -> str:
    if mins < 1:
        return "即將發車"
    if mins >= 60:
        return f"{mins // 60} 小時 {mins % 60} 分後"
    return f"{mins} 分鐘後"


def mark_text(mark: str) -> str:
    return "、".join(MARKS[c] for c in mark if c in MARKS)


def mark_html(mark: str) -> str:
    """付費 83 號的班次在時間旁加小標籤（♦ 已經在週五被濾掉，不需標示）。"""
    return f' <span class="muted" style="font-size:.78em">※{MARKS["※"]}</span>' if "※" in mark else ""


def _valid_color(value) -> str | None:
    return value if isinstance(value, str) and re.fullmatch(r"#[0-9A-Fa-f]{6}", value) else None


def route_color(route: dict) -> str:
    """路線顏色：JSON 有寫 color（例如綠線、紅線）就用它，否則依 type 決定。"""
    return _valid_color(route.get("color")) or KINDS.get(route.get("type", "campus"), KINDS["campus"])[1]


def route_title(route: dict, size: str = "") -> str:
    """路線名稱前加上該路線顏色的圓點，名稱本身也套用路線色。"""
    c = route_color(route)
    return (f'<span class="line-dot {size}" style="background:{c};box-shadow:0 0 0 3px {c}33"></span>'
            f'<span style="color:color-mix(in srgb,{c} 85%,currentColor)">{esc(route.get("name", "未命名"))}</span>')


def kind_badge(route: dict) -> str:
    if _valid_color(route.get("color")):  # 有自己顏色的路線：標籤顯示 note（Green Line、經台積館…）
        return badge(route.get("note") or route.get("name", ""), route_color(route))
    text, color = KINDS.get(route.get("type", "campus"), KINDS["campus"])
    return badge(text, color)


# ---------- 頁面 ----------
def route_card(route: dict, now: datetime, default_origin: str) -> str:
    c = route_color(route)
    day = day_key(now)
    head = (f'<div class="card-head"><span class="card-title">{route_title(route)}</span>'
            f'{kind_badge(route)}</div>')
    # 有自己顏色的路線，note 已經顯示在標籤裡，不重複
    note = (f'<div class="muted">{esc(route["note"])}</div>'
            if route.get("note") and not _valid_color(route.get("color")) else "")
    parts = []
    for d in get_directions(route, default_origin):
        icon = DIR_ICONS.get(d.get("name", ""), "🚌")
        origin = f'📍 {esc(d["origin"])}' if d.get("origin") else ""
        parts.append(f'<div class="sub" style="color:color-mix(in srgb,{c} 85%,currentColor)">'
                     f'<span>{icon} {esc(d.get("name", ""))}</span>'
                     f'<span class="muted">{origin}</span></div>')
        if not parse_entries(d.get(day, [])):
            if day == "weekend":
                parts.append(empty("🛌", "假日無班次"))
            elif not parse_entries(d.get("weekend", [])):
                parts.append(empty("📝", "尚未填寫班表"))
            else:
                parts.append(empty("🛌", "平日無班次"))
        else:
            nxt = get_next_buses(d, now)
            parts.append("".join(f'<div class="row"><span class="t">{hhmm}{mark_html(mk)}</span>'
                                 f'<span class="e">{eta_text(m)}</span></div>' for hhmm, m, mk in nxt)
                         or empty("🌃", "今天已無班次"))
    return (f'<div class="card route" style="border-top:4px solid {c}">'
            f'{head}{note}{"".join(parts)}</div>')


def timetable_df(entries: list[tuple[str, str]]) -> pd.DataFrame:
    df = pd.DataFrame({"發車時間": [t for t, _ in entries]})
    if any(mk for _, mk in entries):
        df["備註"] = [mark_text(mk) for _, mk in entries]
    return df


def render() -> None:
    data, err = load_bus_data()
    default_origin = data.get("origin", "")
    hero("公車班表", "校本部綠線、紅線　·　往返南大校區　·　編輯 data/bus_schedule.json 更新", "🚌")

    if err:
        st.error(err)
    routes = data.get("routes", [])
    if not routes:
        st.warning("找不到班表，請編輯 data/bus_schedule.json")
        return

    for r in routes:  # 提醒填錯的時間格式
        for d in get_directions(r, default_origin):
            for day in SERVICE_DAYS:
                _, bad = _parse(d.get(day, []))
                if bad:
                    st.warning(f"{r.get('name', '?')} {d.get('name', '')}（{SERVICE_DAYS[day]}）有無法辨識的時間："
                               f"{'、'.join(bad)}，請用 07:30 這種格式")

    now = datetime.now()
    if day_key(now) == "weekend":
        st.info("今天是假日，只有南大校區路線有少量班次。")
    elif now.weekday() == 4:
        st.info("今天是週五，標 ♦ 的南大線班次停駛，下方已自動略過。")

    tab_next, tab_all = st.tabs(["⏱️ 即將發車", "📋 完整時刻表"])

    with tab_next:
        for i in range(0, len(routes), PER_ROW):
            row = routes[i:i + PER_ROW]
            for col, r in zip(st.columns(PER_ROW), row):
                with col:
                    html(route_card(r, now, default_origin))

    with tab_all:
        for r in routes:
            html(f'<div class="card-head" style="margin-top:8px;padding-bottom:6px;'
                 f'border-bottom:2px solid {route_color(r)}"><span class="card-title">{route_title(r)}</span>'
                 f'{kind_badge(r)}</div>')
            dirs = get_directions(r, default_origin)
            for col, d in zip(st.columns(len(dirs)), dirs):
                with col:
                    icon = DIR_ICONS.get(d.get("name", ""), "🚌")
                    origin = f"　📍{d['origin']}" if d.get("origin") else ""
                    st.markdown(f"**{icon} {d.get('name', '')}**{origin}")
                    if d.get("stops"):
                        st.caption("停靠：" + " → ".join(map(str, d["stops"])))
                    weekend = parse_entries(d.get("weekend", []))
                    for day, label in SERVICE_DAYS.items():
                        entries = parse_entries(d.get(day, []))
                        if day == "weekend" and not entries:
                            continue  # 沒有假日班次的路線就不多佔版面
                        if weekend:
                            st.markdown(f"<small>**{label}**</small>", unsafe_allow_html=True)
                        if entries:
                            st.dataframe(timetable_df(entries), hide_index=True, use_container_width=True)
                        else:
                            st.caption("尚未填寫")
        if any(mk for r in routes for d in get_directions(r, default_origin)
               for day in SERVICE_DAYS for _, mk in parse_entries(d.get(day, []))):
            st.caption("　".join(f"{k} {v}" for k, v in
                                {"♦": "週五停駛（僅週一至週四）", "※": "付費市區公車 83 號"}.items()))


FEATURE = Feature(title="公車班表", icon="🚌", render=render, slug="bus")
