"""📅 考試提醒：新增 / 刪除考試，並顯示倒數時間。"""
import uuid
from datetime import datetime

import streamlit as st

from core.storage import load_json, save_json
from features.base import Feature

DATA_FILE = "exams.json"
WARN_DAYS = 3  # 幾天內的考試用警告色標示


# ---------- 資料邏輯（可被其他頁面重複使用） ----------
def load_exams() -> list[dict]:
    return load_json(DATA_FILE, [])


def save_exams(exams: list[dict]) -> None:
    save_json(DATA_FILE, exams)


def exam_datetime(exam: dict) -> datetime:
    return datetime.fromisoformat(exam["datetime"])


def get_upcoming_exams(now: datetime | None = None) -> list[dict]:
    now = now or datetime.now()
    upcoming = [e for e in load_exams() if exam_datetime(e) >= now]
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


# ---------- 頁面 ----------
def render() -> None:
    st.title("📅 考試提醒")

    with st.expander("➕ 新增考試", expanded=False):
        with st.form("add_exam", clear_on_submit=True):
            subject = st.text_input("科目")
            c1, c2 = st.columns(2)
            d = c1.date_input("日期")
            t = c2.time_input("時間")
            place = st.text_input("地點（選填）")
            if st.form_submit_button("新增") and subject.strip():
                exams = load_exams()
                exams.append({
                    "id": uuid.uuid4().hex,
                    "subject": subject.strip(),
                    "datetime": datetime.combine(d, t).isoformat(),
                    "place": place.strip(),
                })
                save_exams(exams)
                st.success(f"已新增：{subject}")

    now = datetime.now()
    upcoming = get_upcoming_exams(now)

    if not upcoming:
        st.info("目前沒有即將到來的考試 🎉")
        return

    for exam in upcoming:
        dt = exam_datetime(exam)
        left = countdown_text(dt, now)
        place = f"｜📍{exam['place']}" if exam.get("place") else ""
        msg = f"**{exam['subject']}**　{dt:%Y/%m/%d (%a) %H:%M}{place}　⏳ 剩 {left}"

        c1, c2 = st.columns([8, 1])
        if (dt - now).days < WARN_DAYS:
            c1.warning(msg)
        else:
            c1.info(msg)
        if c2.button("🗑️", key=f"del_{exam['id']}", help="刪除"):
            save_exams([e for e in load_exams() if e["id"] != exam["id"]])
            st.rerun()


FEATURE = Feature(title="考試提醒", icon="📅", render=render, slug="exams")
