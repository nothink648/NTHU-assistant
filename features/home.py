"""🏠 首頁：整合各功能的摘要。"""
from datetime import datetime

import streamlit as st

from config import APP_ICON, APP_TITLE, WEEKDAYS
from core.ui import badge, card, esc, hero, html
from features.base import Feature
from features.bus_schedule import eta_text, get_next_buses, load_routes
from features.exam_reminder import countdown_text, exam_datetime, get_upcoming_exams
from features.timetable import to_min, today_classes


def exam_summary(now: datetime) -> str:
    head = '<div class="card-head"><span class="card-title">📅 下一場考試</span></div>'
    exams = get_upcoming_exams(now)
    if not exams:
        return card(head + '<div class="muted">目前沒有考試 🎉</div>')
    e = exams[0]
    dt = exam_datetime(e)
    return card(head + f'<div class="big">{esc(e["subject"])}</div>'
                f'<div>{badge("⏳ 剩 " + countdown_text(dt, now))}</div>'
                f'<div class="muted" style="margin-top:6px">{dt:%Y/%m/%d %H:%M}</div>')


def bus_summary(now: datetime) -> str:
    head = '<div class="card-head"><span class="card-title">🚌 最近一班公車</span></div>'
    rows = []
    for r in load_routes():
        nxt = get_next_buses(r, now, n=1)
        if nxt:
            rows.append(f'<div class="row"><span class="t">{esc(r.get("name", ""))}　{nxt[0][0]}</span>'
                        f'<span class="e">{eta_text(nxt[0][1])}</span></div>')
    return card(head + ("".join(rows) or '<div class="muted">今天已無班次（或尚未填寫班表）</div>'))


def class_summary(now: datetime) -> str:
    head = f'<div class="card-head"><span class="card-title">📆 今日課程</span>{badge(WEEKDAYS[now.weekday()])}</div>'
    items = today_classes(now)
    if not items:
        return card(head + '<div class="muted">今天沒有課 😎</div>')
    cur = now.hour * 60 + now.minute
    rows = []
    for s, c in items:
        done = to_min(s["end"]) <= cur
        live = to_min(s["start"]) <= cur < to_min(s["end"])
        room = f"　📍{esc(s['room'])}" if s.get("room") else ""
        tag = badge("上課中", "#2E7D4F", "#DDF5E7") if live else ""
        rows.append(f'<div class="row {"dim" if done else ""}"><span class="t">{esc(c["name"])}{room}</span>'
                    f'<span class="e">{s["start"]}–{s["end"]} {tag}</span></div>')
    return card(head + "".join(rows))


def render() -> None:
    now = datetime.now()
    hero(APP_TITLE, f"{now:%Y/%m/%d}（{WEEKDAYS[now.weekday()]}）　{now:%H:%M}", APP_ICON)

    c1, c2, c3 = st.columns(3)
    with c1:
        html(exam_summary(now))
    with c2:
        html(bus_summary(now))
    with c3:
        html(class_summary(now))


FEATURE = Feature(title="首頁", icon="🏠", render=render, slug="home", default=True)
