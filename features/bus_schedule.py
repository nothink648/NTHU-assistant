"""🚌 公車班表：班表放在 data/bus_schedule.json，直接編輯該檔即可更新。

JSON 結構（每條路線有一到多個「方向」，每個方向有自己的出發地與時刻表）：
{
  "routes": [
    {"name": "校內線 1", "type": "campus", "note": "",
     "directions": [
       {"name": "上山", "origin": "校門口", "weekday": "07:30, 08:00"},
       {"name": "下山", "origin": "台積館", "weekday": "07:45, 08:15"}
     ]},
    {"name": "校外線", "type": "offcampus",
     "directions": [{"name": "發車", "origin": "校門口", "weekday": "..."}]}
  ]
}
weekday 可以寫成「逗號或空格分隔的字串」，也可以寫成陣列。
目前公車只有平日；之後要加假日，在 SERVICE_DAYS 加 "weekend": "假日"，
並在各方向補上 weekend 欄位即可。
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
SERVICE_DAYS = {"weekday": "平日"}  # 目前有班次的日子
DIR_ICONS = {"上山": "⬆️", "下山": "⬇️"}
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


def get_next_buses(direction: dict, now: datetime | None = None,
                   day: str | None = None, n: int = 3) -> list[tuple[str, int]]:
    """回傳 [(發車時間, 幾分鐘後), ...]，最多 n 班。direction 為一個方向（含 weekday 欄位）。"""
    now = now or datetime.now()
    day = day or day_key(now)
    if day not in SERVICE_DAYS:
        return []
    result = []
    for hhmm in parse_times(direction.get(day, [])):
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
def route_card(route: dict, now: datetime, default_origin: str) -> str:
    head = (f'<div class="card-head"><span class="card-title">🚌 {esc(route.get("name", "未命名"))}</span>'
            f'{kind_badge(route)}</div>')
    note = f'<div class="muted">{esc(route["note"])}</div>' if route.get("note") else ""
    parts = []
    for d in get_directions(route, default_origin):
        icon = DIR_ICONS.get(d.get("name", ""), "🚌")
        origin = f'📍 {esc(d["origin"])}' if d.get("origin") else ""
        parts.append(f'<div class="sub"><span>{icon} {esc(d.get("name", ""))}</span>'
                     f'<span class="muted">{origin}</span></div>')
        if not is_service_day(now):
            parts.append('<div class="muted">假日無班次</div>')
        elif not parse_times(d.get("weekday", [])):
            parts.append('<div class="muted">尚未填寫班表</div>')
        else:
            nxt = get_next_buses(d, now)
            parts.append("".join(f'<div class="row"><span class="t">{hhmm}</span>'
                                 f'<span class="e">{eta_text(m)}</span></div>' for hhmm, m in nxt)
                         or '<div class="muted">今天已無班次</div>')
    return card(head + note + "".join(parts))


def render() -> None:
    data, err = load_bus_data()
    default_origin = data.get("origin", "")
    hero("公車班表", "目前僅提供平日班表　·　編輯 data/bus_schedule.json 更新", "🚌")

    if err:
        st.error(err)
    routes = data.get("routes", [])
    if not routes:
        st.warning("找不到班表，請編輯 data/bus_schedule.json")
        return

    for r in routes:  # 提醒填錯的時間格式
        for d in get_directions(r, default_origin):
            _, bad = _parse(d.get("weekday", []))
            if bad:
                st.warning(f"{r.get('name', '?')} {d.get('name', '')} 有無法辨識的時間："
                           f"{'、'.join(bad)}，請用 07:30 這種格式")

    now = datetime.now()
    if not is_service_day(now):
        st.info("今天是假日，目前只有平日班表。")

    tab_next, tab_all = st.tabs(["⏱️ 即將發車", "📋 完整時刻表"])

    with tab_next:
        for col, r in zip(st.columns(len(routes)), routes):
            with col:
                html(route_card(r, now, default_origin))

    with tab_all:
        for r in routes:
            html(f'<div class="card-head"><span class="card-title">🚌 {esc(r.get("name", ""))}</span>'
                 f'{kind_badge(r)}</div>')
            dirs = get_directions(r, default_origin)
            for col, d in zip(st.columns(len(dirs)), dirs):
                with col:
                    icon = DIR_ICONS.get(d.get("name", ""), "🚌")
                    origin = f"　📍{d['origin']}" if d.get("origin") else ""
                    st.markdown(f"**{icon} {d.get('name', '')}**{origin}")
                    times = parse_times(d.get("weekday", []))
                    if times:
                        st.dataframe(pd.DataFrame({"發車時間": times}), hide_index=True,
                                     use_container_width=True)
                    else:
                        st.caption("尚未填寫")


FEATURE = Feature(title="公車班表", icon="🚌", render=render, slug="bus")
