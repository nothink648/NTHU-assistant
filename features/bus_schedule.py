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
「關注路線」（校本部 / 南大校區 / 全部）是個人設定，存在 data/users/<id>/settings.json，決定首頁顯示哪些公車。
"""
from __future__ import annotations

import json
import re
from datetime import datetime

import pandas as pd
import streamlit as st

from config import DATA_DIR
from core import nthu_api
from core.i18n import is_en, t
from core.storage import load_user_json, save_user_json
from core.icons import arrow, before_css, icon, label as icon_label, tab_css
from core.ui import badge, card, empty, esc, hero, html
from features.base import Feature

DATA_FILE = "bus_schedule.json"
MARKS = {"♦": ("週五停駛", "No Friday service"), "※": ("付費 83 號", "Paid bus No. 83")}  # 時間後面的註記
TIME_RE = re.compile(r"^(\d{1,2})[:：](\d{2})([" + "".join(MARKS) + r"]*)$")
SERVICE_DAYS = {"weekday": ("平日", "Weekdays"), "weekend": ("假日", "Weekends")}
DIR_ARROWS = {"上山": 0, "下山": 180, "往南大": 90, "往校本部": 270}  # 方向 -> 箭頭旋轉角度（arrow-up.png）
KINDS = {  # type -> (顯示文字, 主色)
    "campus": (("校內", "Campus"), "#6C63FF"),
    "nanda": (("南大校區", "Nanda Campus"), "#2F7FD8"),
}
SETTINGS_FILE = "settings.json"
FOCUS = {  # 關注路線 -> ((選項文字), (首頁標籤), 包含的 type；None 代表全部)；文字都是 (中文, 英文)
    "campus": (("校本部（綠線、紅線）", "Main campus (Green, Red)"), ("校本部", "Main campus"), {"campus"}),
    "nanda": (("往返南大校區（南大線一、二）", "To/from Nanda (Nanda 1, 2)"), ("南大校區", "Nanda"), {"nanda"}),
    "all": (("全部路線", "All routes"), ("全部", "All"), None),
}
# 路線 / 方向 / 站名的英文（班表 JSON 與 API 都是中文）；完全相同的優先，否則逐段替換（長的先換）
PLACE_EN = {
    "綠線": "Green Line", "紅線": "Red Line", "南大線一": "Nanda Route 1", "南大線二": "Nanda Route 2",
    "經台積館": "via TSMC Building", "經教育大樓": "via COE Building",
    "上山": "Uphill", "下山": "Downhill", "往南大": "To Nanda", "往校本部": "To Main Campus", "發車": "Departs",
    "南大校區校門口右側(食品路校牆邊)": "Nanda Campus Gate (right side)", "南大校區校門口": "Nanda Campus Gate",
    "南大校區": "Nanda Campus", "北校門口": "North Main Gate", "校門口": "Main Gate", "台積館": "TSMC Building",
    "綜二館": "General Building II", "楓林小徑": "Maple Path", "人社院&生科館": "CHSS/CLS Building",
    "人社院/生科館": "CHSS/CLS Building", "奕園停車場": "Yi Pavilion Parking Lot",
    "竹師教育學院大樓/南門停車場": "COE Building/South Gate Parking Lot",
    "教育學院大樓&南門停車場": "COE Building/South Gate Parking Lot", "(經寶山路)": " (via Baoshan Rd.)",
}


def tr_place(text: str) -> str:
    """路線、方向、站名：英文介面換成英文（沒有對照的部分維持原文）。"""
    text = str(text or "")
    if not is_en() or not text:
        return text
    if text in PLACE_EN:
        return PLACE_EN[text]
    for zh in sorted(PLACE_EN, key=len, reverse=True):
        text = text.replace(zh, PLACE_EN[zh])
    return text


def focus_label(key: str) -> str:
    return t(*FOCUS[key][0])


def focus_short(key: str) -> str:
    return t(*FOCUS[key][1])


def route_dir_label(route: dict, direction: dict) -> str:
    """首頁用：「綠線・上山」/ "Green Line · Uphill"（單一方向的舊格式只顯示路線名）。"""
    name = tr_place(route.get("name", ""))
    if direction.get("name") == "發車":
        return name
    return name + t("・", " · ") + tr_place(direction.get("name", ""))
DEFAULT_FOCUS = "campus"
PER_ROW = 3  # 「即將發車」每列最多幾張卡片

# 「到站時間」分頁：資料來自 NTHU Data API 的 /buses/schedule?stop=...（依官方時刻表推算，不是 GPS）
API_LINES = {  # API 的 line -> (名稱, 顏色)
    "main_green": ("綠線", "#2E9E6A"),  # 名稱顯示時經 tr_place 翻譯
    "main_red": ("紅線", "#E5486F"),
    "nanda_route_1": ("南大線一", "#2F7FD8"),
    "nanda_route_2": ("南大線二", "#9B59D0"),
}
BUS_TYPES = {"large-sized_bus": ("大型巴士", "Large bus"), "middle-sized_bus": ("中型巴士", "Mid-size bus")}
DEFAULT_STOPS = ["北校門口", "綜二館", "楓林小徑", "人社院&生科館", "台積館", "奕園停車場",
                 "教育學院大樓&南門停車場", "南大校區校門口右側(食品路校牆邊)"]
ARRIVAL_ROWS = 8  # 到站時間最多列幾班


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
        return empty, t(f"找不到 data/{DATA_FILE}", f"data/{DATA_FILE} not found")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return empty, t(f"data/{DATA_FILE} 格式錯誤（第 {e.lineno} 行）：請檢查逗號與引號是否為半形",
                         f"data/{DATA_FILE} has a format error (line {e.lineno}): check commas and quotes")
    if isinstance(raw, list):  # 相容舊格式
        raw = {"routes": raw}
    return raw, None


def get_focus() -> str:
    data = load_user_json(SETTINGS_FILE, {})
    focus = data.get("bus_focus") if isinstance(data, dict) else None
    return focus if focus in FOCUS else DEFAULT_FOCUS


def set_focus(focus: str) -> None:
    data = load_user_json(SETTINGS_FILE, {})
    data = data if isinstance(data, dict) else {}
    data["bus_focus"] = focus
    save_user_json(SETTINGS_FILE, data)


def get_stop() -> str | None:
    """使用者在「到站時間」選的站點（個人設定）。"""
    data = load_user_json(SETTINGS_FILE, {})
    return data.get("bus_stop") if isinstance(data, dict) else None


def set_stop(stop: str) -> None:
    data = load_user_json(SETTINGS_FILE, {})
    data = data if isinstance(data, dict) else {}
    data["bus_stop"] = stop
    save_user_json(SETTINGS_FILE, data)


def list_stops() -> list[str]:
    data, _ = nthu_api.get("/buses/stops", ttl=86400)
    names = [s["name"] for s in data or [] if isinstance(s, dict) and s.get("name")]
    return names or DEFAULT_STOPS


def _hhmm_min(text: str) -> int | None:
    m = re.fullmatch(r"(\d{1,2}):(\d{2})", str(text or "").strip())
    return int(m.group(1)) * 60 + int(m.group(2)) if m else None


def stop_arrivals(stop: str, now: datetime) -> tuple[list[dict], str | None]:
    """接下來會到 stop 的公車，依抵達時間排序。每筆：line、名稱、顏色、抵達時間、幾分鐘後、往哪、沿途各站時間。"""
    data, err = nthu_api.get("/buses/schedule", {"stop": stop, "day": "current", "details": "true",
                                                 "limit": ARRIVAL_ROWS + 6}, ttl=60)
    cur = now.hour * 60 + now.minute
    result = []
    for b in data or []:
        if not isinstance(b, dict):
            continue
        info = b.get("dep_info") or {}
        arrive = _hhmm_min(b.get("arrive_time"))
        if arrive is None or arrive < cur:
            continue  # 已經過站
        stops = [s for s in b.get("stops_time") or [] if isinstance(s, dict) and s.get("stop")]
        name, color = API_LINES.get(info.get("line"), (info.get("line") or t("公車", "Bus"), "#6C63FF"))
        result.append({"name": name, "color": color, "arrive": b.get("arrive_time"), "mins": arrive - cur,
                       "dest": stops[-1]["stop"] if stops else "", "origin": stops[0]["stop"] if stops else "",
                       "dep": info.get("time") or "",
                       "bus_type": t(*BUS_TYPES[info["bus_type"]]) if info.get("bus_type") in BUS_TYPES else "",
                       "stops": stops, "note": info.get("description") or ""})
    result.sort(key=lambda x: x["mins"])
    return result[:ARRIVAL_ROWS], err


def arrival_text(mins: int) -> str:
    if mins < 1:
        return t("即將到站", "Arriving")
    if mins >= 60:
        return t(f"{mins // 60} 小時 {mins % 60} 分後", f"in {mins // 60}h {mins % 60}m")
    return t(f"{mins} 分鐘後", f"in {mins} min")


def focus_routes(routes: list[dict], focus: str | None = None) -> list[dict]:
    """只留下關注的路線種類（首頁用）。"""
    types = FOCUS[focus or get_focus()][2]
    return [r for r in routes if types is None or r.get("type", "campus") in types]


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
        return t("即將發車", "Leaving now")
    if mins >= 60:
        return t(f"{mins // 60} 小時 {mins % 60} 分後", f"in {mins // 60}h {mins % 60}m")
    return t(f"{mins} 分鐘後", f"in {mins} min")


def mark_text(mark: str) -> str:
    return t("、", ", ").join(t(*MARKS[c]) for c in mark if c in MARKS)


def mark_html(mark: str) -> str:
    """付費 83 號的班次在時間旁加小標籤（♦ 已經在週五被濾掉，不需標示）。"""
    return f' <span class="muted" style="font-size:.78em">※{t(*MARKS["※"])}</span>' if "※" in mark else ""


def _valid_color(value) -> str | None:
    return value if isinstance(value, str) and re.fullmatch(r"#[0-9A-Fa-f]{6}", value) else None


def route_color(route: dict) -> str:
    """路線顏色：JSON 有寫 color（例如綠線、紅線）就用它，否則依 type 決定。"""
    return _valid_color(route.get("color")) or KINDS.get(route.get("type", "campus"), KINDS["campus"])[1]


def route_title(route: dict, size: str = "") -> str:
    """路線名稱前加上該路線顏色的圓點，名稱本身也套用路線色。"""
    c = route_color(route)
    return (f'<span class="line-dot {size}" style="background:{c};box-shadow:0 0 0 3px {c}33"></span>'
            f'<span style="color:color-mix(in srgb,{c} 85%,currentColor)">{esc(tr_place(route.get("name", "")) or t("未命名", "Unnamed"))}</span>')


def kind_badge(route: dict) -> str:
    if _valid_color(route.get("color")):  # 有自己顏色的路線：標籤顯示 note（Green Line、經台積館…）
        return badge(tr_place(route.get("note") or route.get("name", "")), route_color(route))
    text, color = KINDS.get(route.get("type", "campus"), KINDS["campus"])
    return badge(t(*text), color)


# ---------- 頁面 ----------
def route_card(route: dict, now: datetime, default_origin: str) -> str:
    c = route_color(route)
    day = day_key(now)
    head = (f'<div class="card-head"><span class="card-title">{route_title(route)}</span>'
            f'{kind_badge(route)}</div>')
    # 有自己顏色的路線，note 已經顯示在標籤裡，不重複
    note = (f'<div class="muted">{esc(tr_place(route["note"]))}</div>'
            if route.get("note") and not _valid_color(route.get("color")) else "")
    parts = []
    for d in get_directions(route, default_origin):
        dir_icon = dir_arrow(d)
        origin = f'{icon("pin")} {esc(tr_place(d["origin"]))}' if d.get("origin") else ""
        parts.append(f'<div class="sub" style="color:color-mix(in srgb,{c} 85%,currentColor)">'
                     f'<span>{dir_icon} {esc(tr_place(d.get("name", "")))}</span>'
                     f'<span class="muted">{origin}</span></div>')
        if not parse_entries(d.get(day, [])):
            if day == "weekend":
                parts.append(empty(icon("night-sleeping") or "🛌", t("假日無班次", "No weekend service")))
            elif not parse_entries(d.get("weekend", [])):
                parts.append(empty(icon("edit") or "📝", t("尚未填寫班表", "No timetable yet")))
            else:
                parts.append(empty(icon("night-sleeping") or "🛌", t("平日無班次", "No weekday service")))
        else:
            nxt = get_next_buses(d, now)
            parts.append("".join(f'<div class="row"><span class="t">{hhmm}{mark_html(mk)}</span>'
                                 f'<span class="e">{eta_text(m)}</span></div>' for hhmm, m, mk in nxt)
                         or empty(icon("night-sleeping") or "🌃", t("今天已無班次", "No more buses today")))
    return (f'<div class="card route" style="border-top:4px solid {c}">'
            f'{head}{note}{"".join(parts)}</div>')


ARRIVAL_CSS = """<style>
.arr .row{align-items:flex-start}
.arr .t{flex:1;min-width:0}
.arr .path{display:block;font-weight:400;font-size:.78rem;opacity:.62;margin-top:3px;line-height:1.5}
.arr .path b{opacity:1;color:var(--acc-text)}
.arr .e{flex:none;text-align:right}
.arr .at{display:block;font-size:1.15rem;font-weight:800}
</style>"""


def arrivals_tab(now: datetime) -> None:
    stops = list_stops()
    saved = get_stop()
    if st.session_state.get("bus_stop") not in stops:  # 第一次進來：帶入上次選的站
        st.session_state["bus_stop"] = saved if saved in stops else stops[0]
    st.selectbox(icon_label("pin", t("我在哪一站", "Where are you?")), stops, key="bus_stop", on_change=_save_stop, format_func=tr_place)
    stop = st.session_state["bus_stop"]

    items, err = stop_arrivals(stop, now)
    if err:
        st.warning(err)
    head = (f'<div class="card-head"><span class="card-title">{icon("pin")} {esc(tr_place(stop))}</span>'
            f'{badge(t("接下來到站", "Arriving next"), "#2E9E6A", live=True)}</div>')
    if not items:
        msg = (t("今天已沒有公車會經過這一站", "No more buses at this stop today") if not err
               else t("暫時查不到到站資料", "Arrival data unavailable right now"))
        html(ARRIVAL_CSS + card(head + empty(icon("night-sleeping") or "🌃", msg), "arr"))
    else:
        rows = []
        for b in items:
            dot = f'<span class="line-dot sm" style="background:{b["color"]}"></span>'
            title = f'{dot}<span style="color:color-mix(in srgb,{b["color"]} 85%,currentColor)">{esc(tr_place(b["name"]))}</span>'
            dest = (f"　{t('往', 'to')} {esc(tr_place(b['dest']))}" if b["dest"] and b["dest"] != stop
                    else "　" + t("終點站", "Terminal"))
            first = b["origin"] == stop
            path = f" {arrow()} ".join(
                f"<b>{esc(tr_place(s['stop']))} {esc(s.get('arrive_time', ''))}</b>" if s["stop"] == stop
                else f"{esc(tr_place(s['stop']))} {esc(s.get('arrive_time', ''))}" for s in b["stops"])
            dep = (t(f"{esc(b['origin'])} {esc(b['dep'])} 發車", f"Departs {esc(tr_place(b['origin']))} at {esc(b['dep'])}")
                   if b["dep"] else "")
            parts = [t("本站發車", "Starts here") if first else dep]
            for x in (b["bus_type"], esc(b["note"])):  # 班表的備註常常也寫「大型巴士」，不重複顯示
                if x and x not in parts:
                    parts.append(x)
            extra = "　·　".join(x for x in parts if x)
            soon = "#E5486F" if b["mins"] <= 3 else "#2E9E6A"
            rows.append(f'<div class="row"><span class="t">{title}{dest}<span class="path">{extra}<br>{path}</span></span>'
                        f'<span class="e"><span class="at">{esc(b["arrive"])}</span>'
                        f'{badge(arrival_text(b["mins"]), soon, live=b["mins"] <= 3)}</span></div>')
        html(ARRIVAL_CSS + card(head + "".join(rows), "arr"))
    st.caption(t("到站時間依官方時刻表推算，並非 GPS 即時位置；尖峰時段或下雨時可能誤點幾分鐘。資料來源：NTHU Data API",
                 "Arrival times are estimated from the official timetable, not live GPS; buses may run a few minutes late "
                 "at peak hours or in rain. Source: NTHU Data API"))


def timetable_df(entries: list[tuple[str, str]]) -> pd.DataFrame:
    df = pd.DataFrame({t("發車時間", "Departure"): [hhmm for hhmm, _ in entries]})
    if any(mk for _, mk in entries):
        df[t("備註", "Note")] = [mark_text(mk) for _, mk in entries]
    return df


def render() -> None:
    data, err = load_bus_data()
    default_origin = data.get("origin", "")
    hero(t("公車班表", "Campus Bus"), t("校本部綠線、紅線　·　往返南大校區　·　編輯 data/bus_schedule.json 更新",
                                     "Green & Red lines　·　Nanda campus shuttle　·　Edit data/bus_schedule.json to update"), "bus")

    if err:
        st.error(err)
    routes = data.get("routes", [])
    if not routes:
        st.warning(t("找不到班表，請編輯 data/bus_schedule.json", "No timetable found; edit data/bus_schedule.json"))
        return

    for r in routes:  # 提醒填錯的時間格式
        for d in get_directions(r, default_origin):
            for day in SERVICE_DAYS:
                _, bad = _parse(d.get(day, []))
                if bad:
                    st.warning(t(f"{r.get('name', '?')} {d.get('name', '')}（{SERVICE_DAYS[day][0]}）有無法辨識的時間："
                                 f"{'、'.join(bad)}，請用 07:30 這種格式",
                                 f"{tr_place(r.get('name', '?'))} {tr_place(d.get('name', ''))} ({SERVICE_DAYS[day][1]}) "
                                 f"has unreadable times: {', '.join(bad)}. Use the 07:30 format"))

    with st.container(border=True):
        html(_focus_icon_css())
        html(f'<div style="font-weight:700">{icon("star")} {t("關注路線", "Favorite routes")}'
             f'<span class="muted">{t("（決定首頁顯示哪些公車）", " (which buses the home page shows)")}</span></div>')
        st.radio(t("關注路線", "Favorite routes"), list(FOCUS), index=list(FOCUS).index(get_focus()),
                 label_visibility="collapsed", format_func=focus_label, horizontal=True, key="bus_focus", on_change=_save_focus)

    now = datetime.now()
    if day_key(now) == "weekend":
        st.info(t("今天是假日，只有南大校區路線有少量班次。", "It's the weekend: only a few Nanda campus buses run."))
    elif now.weekday() == 4:
        st.info(t("今天是週五，標 ♦ 的南大線班次停駛，下方已自動略過。", "It's Friday: Nanda buses marked ♦ do not run and are skipped below."))

    html("<style>" + tab_css("bus_tabs", ["pin", "clock", "time-list"]) + "</style>")
    with st.container(key="bus_tabs"):
        tab_stop, tab_next, tab_all = st.tabs([icon_label("pin", t("到站時間", "Arrivals")),
                                               icon_label("clock", t("即將發車", "Next departures")),
                                               icon_label("time-list", t("完整時刻表", "Full timetable"))])

    with tab_stop:
        arrivals_tab(now)

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
                    dir_icon = dir_arrow(d)
                    origin = f"　{icon('pin')}{esc(tr_place(d['origin']))}" if d.get("origin") else ""
                    st.markdown(f"**{dir_icon} {esc(tr_place(d.get('name', '')))}**{origin}", unsafe_allow_html=True)
                    if d.get("stops"):
                        st.caption(t("停靠：", "Stops: ") + f" {arrow()} ".join(esc(tr_place(s)) for s in d["stops"]),
                                   unsafe_allow_html=True)
                    weekend = parse_entries(d.get("weekend", []))
                    for day, (day_zh, day_en) in SERVICE_DAYS.items():
                        entries = parse_entries(d.get(day, []))
                        if day == "weekend" and not entries:
                            continue  # 沒有假日班次的路線就不多佔版面
                        if weekend:
                            st.markdown(f"<small>**{t(day_zh, day_en)}**</small>", unsafe_allow_html=True)
                        if entries:
                            st.dataframe(timetable_df(entries), hide_index=True, use_container_width=True)
                        else:
                            st.caption(t("尚未填寫", "Not filled in"))
        if any(mk for r in routes for d in get_directions(r, default_origin)
               for day in SERVICE_DAYS for _, mk in parse_entries(d.get(day, []))):
            st.caption("　".join(f"{k} {v}" for k, v in
                                {"♦": t("週五停駛（僅週一至週四）", "No Friday service (Mon–Thu only)"),
                                 "※": t("付費市區公車 83 號", "Paid city bus No. 83")}.items()))


def _focus_icon_css() -> str:
    """「關注路線」的校本部、南大校區選項前面畫上 school icon（選項文字不能放 HTML，用 ::before）；全部路線不放。"""
    return ("<style>" + before_css(".st-key-bus_focus label:has(input[value='0']) p", "school")
            + before_css(".st-key-bus_focus label:has(input[value='1']) p", "school") + "</style>")


def dir_arrow(direction: dict) -> str:
    """方向名稱前的箭頭：上山 ↑、下山 ↓、往南大 →、往校本部 ←；其他方向用公車。"""
    rot = DIR_ARROWS.get(direction.get("name", ""))
    return arrow(rot) if rot is not None else "🚌"


def _save_focus() -> None:
    focus = st.session_state.get("bus_focus", DEFAULT_FOCUS)
    set_focus(focus)
    st.toast(t(f"首頁將顯示：{focus_short(focus)}的公車", f"Home page will show: {focus_short(focus)} buses"), icon=":material/star:")


def _save_stop() -> None:
    stop = st.session_state.get("bus_stop")
    if stop:
        set_stop(stop)
        st.toast(t(f"已記住你的站點：{stop}", f"Saved your stop: {tr_place(stop)}"), icon=":material/location_on:")


FEATURE = Feature(title="公車班表", icon="🚌", render=render, slug="bus", ico="bus", title_en="Campus Bus")
