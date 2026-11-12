"""🏠 首頁：整合各功能的摘要。"""
from __future__ import annotations

from datetime import datetime

import streamlit as st

from config import APP_ICON, APP_TITLE, WEEKDAYS
from core.ui import badge, card, empty, esc, hero, html
from features.base import Feature
from features.bus_schedule import (eta_text, get_directions, get_next_buses, is_service_day, load_bus_data,
                                   mark_html, route_color)
from features.exam_reminder import (WARN_DAYS, countdown_text, course_html, exam_datetime,
                                   get_upcoming_exams, links_html)
from features.timetable import to_min, today_classes


def greeting(now: datetime) -> str:
    h = now.hour
    if h < 5:
        return "夜深了，早點休息 🌙"
    if h < 11:
        return "早安！今天也加油 ☀️"
    if h < 14:
        return "午安，記得吃飯 🍱"
    if h < 18:
        return "下午好 ☕"
    return "晚安，辛苦了 🌆"


def exam_summary(now: datetime) -> str:
    head = '<div class="card-head"><span class="card-title">📅 下一場考試</span></div>'
    exams = get_upcoming_exams(now)
    if not exams:
        return card(head + empty("🎉", "目前沒有考試"))
    e = exams[0]
    dt = exam_datetime(e)
    urgent = (dt - now).days < WARN_DAYS
    more = f'<div class="muted" style="margin-top:6px">之後還有 {len(exams) - 1} 場</div>' if len(exams) > 1 else ""
    return card(head + f'<div class="big">{esc(e["subject"])}</div>{course_html(e)}'
                f'<div style="margin:4px 0">{badge("⏳ 剩 " + countdown_text(dt, now), "#E5486F" if urgent else "#6C63FF")}</div>'
                f'<div class="muted">🗓️ {dt:%Y/%m/%d}（{WEEKDAYS[dt.weekday()]}）{dt:%H:%M}</div>{more}'
                f'{links_html(e)}',
                "exam urgent" if urgent else "exam")


def bus_summary(now: datetime) -> str:
    head = '<div class="card-head"><span class="card-title">🚌 最近一班公車</span></div>'
    if not is_service_day(now):
        return card(head + empty("🛌", "假日無班次"))
    data, _ = load_bus_data()
    rows = []
    for r in data.get("routes", []):
        for d in get_directions(r, data.get("origin", "")):
            nxt = get_next_buses(d, now, n=1)
            if nxt:
                label = r.get("name", "") + ("" if d.get("name") == "發車" else f"・{d.get('name', '')}")
                c = route_color(r)
                dot = f'<span class="line-dot sm" style="background:{c}"></span>'
                rows.append(f'<div class="row"><span class="t">{dot}{esc(label)}　{nxt[0][0]}{mark_html(nxt[0][2])}</span>'
                            f'<span class="e">{eta_text(nxt[0][1])}</span></div>')
    return card(head + ("".join(rows) or empty("🌃", "今天已無班次")))


def class_summary(now: datetime) -> str:
    head = (f'<div class="card-head"><span class="card-title">📆 今日課程</span>'
            f'{badge(WEEKDAYS[now.weekday()])}</div>')
    items = today_classes(now)
    if not items:
        return card(head + empty("😎", "今天沒有課"))
    cur = now.hour * 60 + now.minute
    rows = []
    for s, c in items:
        done = to_min(s["end"]) <= cur
        live = to_min(s["start"]) <= cur < to_min(s["end"])
        room = f'<span class="muted">　📍{esc(s["room"])}</span>' if s.get("room") else ""
        tag = " " + badge("上課中", "#2E9E6A", live=True) if live else ""
        rows.append(f'<div class="row {"dim" if done else ""}"><span class="t">{esc(c["name"])}{room}</span>'
                    f'<span class="e">{s["start"]}–{s["end"]}{tag}</span></div>')
    finished = sum(to_min(s["end"]) <= cur for s, _ in items)
    pct = round(finished / len(items) * 100)
    bar = (f'<div class="progress" title="今日進度 {finished}/{len(items)}"><i style="width:{pct}%"></i></div>'
           f'<div class="muted" style="margin-top:4px">已上完 {finished} / {len(items)} 堂</div>')
    return card(head + "".join(rows) + bar)


def render() -> None:
    now = datetime.now()
    hero(greeting(now), f"{now:%Y/%m/%d}（{WEEKDAYS[now.weekday()]}）　{now:%H:%M}　·　{APP_TITLE}", APP_ICON)

    c1, c2, c3 = st.columns(3)
    with c1:
        html(class_summary(now))
    with c2:
        html(bus_summary(now))
    with c3:
        html(exam_summary(now))


FEATURE = Feature(title="首頁", icon="🏠", render=render, slug="home", default=True)
