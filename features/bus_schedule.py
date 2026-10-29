"""🚌 公車班表：班表放在 data/bus_schedule.json，直接編輯該檔即可更新。"""
from datetime import datetime

import pandas as pd
import streamlit as st

from core.storage import load_json
from features.base import Feature

DATA_FILE = "bus_schedule.json"


# ---------- 資料邏輯 ----------
def load_routes() -> list[dict]:
    return load_json(DATA_FILE, [])


def day_key(now: datetime) -> str:
    return "weekday" if now.weekday() < 5 else "weekend"


def get_next_buses(route: dict, now: datetime | None = None,
                   day: str | None = None, n: int = 3) -> list[tuple[str, int]]:
    """回傳 [(發車時間, 幾分鐘後), ...]，最多 n 班。"""
    now = now or datetime.now()
    day = day or day_key(now)
    result = []
    for hhmm in route.get(day, []):
        h, m = map(int, hhmm.split(":"))
        dep = now.replace(hour=h, minute=m, second=0, microsecond=0)
        if dep >= now:
            result.append((hhmm, int((dep - now).total_seconds() // 60)))
    return result[:n]


# ---------- 頁面 ----------
def render() -> None:
    st.title("🚌 公車班表")

    routes = load_routes()
    if not routes:
        st.warning("找不到班表，請編輯 data/bus_schedule.json")
        return

    now = datetime.now()
    names = [r["name"] for r in routes]
    route = routes[names.index(st.selectbox("路線", names))]

    labels = {"weekday": "平日", "weekend": "假日"}
    day = st.radio("班表類型", list(labels), index=list(labels).index(day_key(now)),
                   format_func=labels.get, horizontal=True)

    if route.get("note"):
        st.caption(route["note"])

    nxt = get_next_buses(route, now, day)
    if nxt:
        cols = st.columns(len(nxt))
        for col, (hhmm, mins) in zip(cols, nxt):
            col.metric(f"發車 {hhmm}", f"{mins} 分鐘後")
    else:
        st.info("今天已無班次")

    with st.expander("📋 完整時刻表"):
        st.dataframe(pd.DataFrame({"發車時間": route.get(day, [])}),
                     hide_index=True, use_container_width=True)


FEATURE = Feature(title="公車班表", icon="🚌", render=render, slug="bus")
