"""📅 考試提醒：新增 / 刪除考試，並顯示倒數時間。

考試可以連結課表裡的科目（exam["course_id"]），卡片會顯示該課程的顏色與教授，
課表上也會標出這門課的考試。
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime

import streamlit as st

from config import WEEKDAYS
from core.storage import load_json, save_json
from core.ui import badge, esc, hero, html
from features.base import Feature
from features.timetable import course_colors, load_data as load_timetable

DATA_FILE = "exams.json"
WARN_DAYS = 3  # 幾天內的考試用警示色標示


# ---------- 資料邏輯（可被其他頁面重複使用） ----------
def load_exams() -> list[dict]:
    data = load_json(DATA_FILE, [])
    return data if isinstance(data, list) else []


def save_exams(exams: list[dict]) -> None:
    save_json(DATA_FILE, exams)


def exam_datetime(exam: dict) -> datetime:
    return datetime.fromisoformat(exam["datetime"])


def _valid(exam) -> bool:
    """手動改壞的資料直接略過，不讓整頁當掉。"""
    try:
        exam_datetime(exam)
        return bool(exam.get("subject")) and bool(exam.get("id"))
    except (KeyError, TypeError, ValueError, AttributeError):
        return False


def get_upcoming_exams(now: datetime | None = None) -> list[dict]:
    now = now or datetime.now()
    upcoming = [e for e in load_exams() if _valid(e) and exam_datetime(e) >= now]
    return sorted(upcoming, key=exam_datetime)


def countdown_text(target: datetime, now: datetime | None = None) -> str:
    now = now or datetime.now()
    delta = target - now
    days = delta.days
    hours = delta.seconds // 3600
    minutes = (delta.seconds % 3600) // 60
    if days > 0:
        return f"{days} 天 {hours} 小時"
    return f"{hours} 小時 {minutes} 分"


def course_html(exam: dict, timetable: dict | None = None) -> str:
    """連結的課表科目：課程色標籤 + 教授。課程被刪掉就不顯示。"""
    timetable = timetable or load_timetable()
    course = next((c for c in timetable["courses"] if c["id"] == exam.get("course_id")), None)
    if not course:
        return ""
    teacher = f'<span class="muted">　👤 {esc(course["teacher"])}</span>' if course.get("teacher") else ""
    return (f'<div style="margin:2px 0 4px">{badge("📚 " + course["name"], course_colors(timetable)[course["id"]])}'
            f'{teacher}</div>')


def exam_card(exam: dict, now: datetime, timetable: dict | None = None) -> str:
    dt = exam_datetime(exam)
    urgent = (dt - now).days < WARN_DAYS
    place = f"　📍{esc(exam['place'])}" if exam.get("place") else ""
    when = f"{dt:%Y/%m/%d}（{WEEKDAYS[dt.weekday()]}）{dt:%H:%M}"
    tag = badge(f"⏳ 剩 {countdown_text(dt, now)}", "#E5486F" if urgent else "#6C63FF")
    return (f'<div class="card exam {"urgent" if urgent else ""}"><div class="card-head">'
            f'<span class="card-title">{esc(exam["subject"])}</span>{tag}</div>'
            f'{course_html(exam, timetable)}<div class="muted">🗓️ {when}{place}</div>{links_html(exam)}</div>')


def parse_links(text: str) -> tuple[list[str], list[str]]:
    """把多行文字拆成連結清單，回傳 (合法連結, 格式錯誤的項目)。"""
    good, bad = [], []
    for item in re.split(r"[\s,，]+", text or ""):
        item = item.strip()
        if not item:
            continue
        if re.match(r"^https?://[^\s<>\"']+$", item, re.I):
            if item not in good:
                good.append(item)
        else:
            bad.append(item)
    return good, bad


def links_html(exam: dict) -> str:
    """考古題連結做成可點的小膠囊，另開新分頁。"""
    links = [u for u in exam.get("links") or [] if isinstance(u, str) and u.lower().startswith(("http://", "https://"))]
    if not links:
        return ""
    chips = "".join(
        f'<a class="link-chip" href="{esc(u)}" target="_blank" rel="noopener noreferrer" title="{esc(u)}">'
        f'📄 考古題{"" if len(links) == 1 else f" {i}"}</a>'
        for i, u in enumerate(links, 1))
    return f'<div class="links">{chips}</div>'


# ---------- 頁面 ----------
def render() -> None:
    hero("考試提醒", "新增考試，隨時掌握倒數", "📅")

    timetable = load_timetable()
    courses = {c["id"]: c for c in timetable["courses"]}
    course_opts = [""] + sorted(courses, key=lambda i: courses[i]["name"].casefold())
    course_fmt = lambda i: courses[i]["name"] if i in courses else (i or "不連結（自行輸入科目）")

    with st.expander("➕ 新增考試", expanded=False):
        with st.form("add_exam", clear_on_submit=True):
            cid = st.selectbox("課表科目（選填）", course_opts, format_func=course_fmt,
                               help="連結後，考試卡片會顯示課程顏色與教授，課表上也會標出這場考試")
            subject = st.text_input("考試名稱", placeholder="例如：期中考（有選課表科目時，會自動加上科目名稱）")
            c1, c2 = st.columns(2)
            d = c1.date_input("日期")
            t = c2.time_input("時間", step=300)
            place = st.text_input("地點（選填，連結科目時留空會用上課教室）")
            links_raw = st.text_area("歷屆考古題連結（選填，一行一個）", height=90,
                                     placeholder="https://drive.google.com/...\nhttps://...")
            if st.form_submit_button("新增", type="primary"):
                when = datetime.combine(d, t)
                links, bad = parse_links(links_raw)
                course = courses.get(cid)
                subject = subject.strip()
                if course and course["name"] not in subject:
                    subject = f"{course['name']} {subject or '考試'}"
                place = place.strip() or (course.get("room", "") if course else "")
                if not subject:
                    st.warning("請選擇課表科目或輸入考試名稱")
                elif when < datetime.now():
                    st.warning("這個時間已經過了，請確認日期與時間")
                elif bad:
                    st.warning("以下連結格式不正確（需以 http:// 或 https:// 開頭）：" + "、".join(bad))
                else:
                    exams = load_exams()
                    exams.append({"id": uuid.uuid4().hex, "subject": subject,
                                  "datetime": when.isoformat(), "place": place,
                                  "links": links, "course_id": cid if course else ""})
                    save_exams(exams)
                    st.toast(f"已新增：{subject}", icon="✅")

    now = datetime.now()
    upcoming = get_upcoming_exams(now)

    if not upcoming:
        st.info("目前沒有即將到來的考試 🎉　點上方「新增考試」加入第一場吧！")
        return

    st.caption(f"共 {len(upcoming)} 場即將到來　·　{WARN_DAYS} 天內的考試會以紅色標示")
    for exam in upcoming:
        c1, c2, c3 = st.columns([12, 1, 1], vertical_alignment="center")
        with c1:
            html(exam_card(exam, now, timetable))
        with c2.popover("🔗", help="連結課表科目"):
            cur = exam.get("course_id") if exam.get("course_id") in courses else ""
            st.selectbox("課表科目", course_opts, index=course_opts.index(cur), format_func=course_fmt,
                         key=f"link_{exam['id']}", on_change=_relink, args=(exam,))
        c3.button("🗑️", key=f"del_{exam['id']}", help="刪除", on_click=_delete, args=(exam,))


def _relink(exam: dict) -> None:
    cid = st.session_state.get(f"link_{exam['id']}", "")
    exams = load_exams()
    for e in exams:
        if e.get("id") == exam["id"]:
            e["course_id"] = cid
    save_exams(exams)
    st.toast("已更新連結的課表科目", icon="🔗")


def _delete(exam: dict) -> None:
    save_exams([e for e in load_exams() if e.get("id") != exam["id"]])
    st.toast(f"已刪除：{exam['subject']}", icon="🗑️")


FEATURE = Feature(title="考試提醒", icon="📅", render=render, slug="exams")
