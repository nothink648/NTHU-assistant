"""🏠 首頁：整合各功能的摘要。"""
from datetime import datetime

import streamlit as st

from config import APP_ICON, APP_TITLE
from features.base import Feature
from features.bus_schedule import get_next_buses, load_routes
from features.exam_reminder import countdown_text, exam_datetime, get_upcoming_exams


def render() -> None:
    now = datetime.now()
    st.title(f"{APP_ICON} {APP_TITLE}")
    st.caption(f"{now:%Y/%m/%d %H:%M}")

    c1, c2 = st.columns(2)

    with c1:
        st.subheader("📅 下一場考試")
        exams = get_upcoming_exams(now)
        if exams:
            e = exams[0]
            st.metric(e["subject"], countdown_text(exam_datetime(e), now),
                      help=f"{exam_datetime(e):%Y/%m/%d %H:%M}")
        else:
            st.write("目前沒有考試 🎉")

    with c2:
        st.subheader("🚌 最近一班公車")
        routes = load_routes()
        shown = False
        for r in routes[:2]:
            nxt = get_next_buses(r, now, n=1)
            if nxt:
                st.metric(r["name"], f"{nxt[0][1]} 分鐘後", help=f"發車 {nxt[0][0]}")
                shown = True
        if not shown:
            st.write("今天已無班次")


FEATURE = Feature(title="首頁", icon="🏠", render=render, slug="home", default=True)
