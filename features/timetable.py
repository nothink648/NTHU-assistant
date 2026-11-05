"""📆 課表：依學校節次（或自訂時間）填入課程；同一門課第二次起可直接選用已填過的資料。

資料存在 data/timetable.json：
  courses：課程資料（名稱、教授、預設教室、學分、備註）
  slots  ：上課時段（哪一門課、星期幾、起訖時間）；一門課可以有很多個時段
節次時間定義在 config.py 的 PERIODS。
"""
import uuid
from datetime import datetime, time

import streamlit as st

from config import PERIODS, WEEKDAYS
from core.storage import load_json, save_json
from core.ui import esc, hero, html
from features.base import Feature

DATA_FILE = "timetable.json"
NEW = "__new__"
MODE_P, MODE_C = "依學校節次", "自訂時間"
PERIOD_TIME = {label: (start, end) for label, start, end in PERIODS}
PERIOD_LABELS = [p[0] for p in PERIODS]
PALETTE = [  # (背景, 強調色)
    ("#E8E6FF", "#6C63FF"), ("#FFE8EE", "#E5486F"), ("#E3F6EC", "#2E9E6A"),
    ("#FFF1DC", "#E08A1E"), ("#E1F1FB", "#2C8BC9"), ("#F3E8FF", "#9B51E0"),
    ("#FDF5CF", "#B89A0B"), ("#E0F5F3", "#1E9E94"),
]


# ---------- 資料邏輯（可被其他頁面重複使用） ----------
def load_data() -> dict:
    data = load_json(DATA_FILE, {})
    if not isinstance(data, dict):
        data = {}
    data.setdefault("courses", [])
    data.setdefault("slots", [])
    return data


def save_data(data: dict) -> None:
    save_json(DATA_FILE, data)


def to_min(hhmm: str) -> int:
    h, m = map(int, hhmm.split(":"))
    return h * 60 + m


def overlaps(a_start: str, a_end: str, b_start: str, b_end: str) -> bool:
    return to_min(a_start) < to_min(b_end) and to_min(a_end) > to_min(b_start)


def find_course(data: dict, course_id: str) -> dict | None:
    return next((c for c in data["courses"] if c["id"] == course_id), None)


def slot_label(slot: dict) -> str:
    p = slot.get("periods")
    if p:
        period = f"第{p[0]}節" if p[0] == p[1] else f"第{p[0]}–{p[1]}節"
    else:
        period = "自訂"
    return f"{WEEKDAYS[slot['day']]}　{period}　{slot['start']}–{slot['end']}"


def today_classes(now: datetime | None = None) -> list[tuple[dict, dict]]:
    """今天的課：[(slot, course), ...]，依開始時間排序。"""
    now = now or datetime.now()
    data = load_data()
    courses = {c["id"]: c for c in data["courses"]}
    items = [(s, courses[s["course_id"]]) for s in data["slots"]
             if s["day"] == now.weekday() and s["course_id"] in courses]
    return sorted(items, key=lambda x: to_min(x[0]["start"]))


# ---------- 新增表單的狀態與 callback ----------
def _init_state() -> None:
    ss = st.session_state
    ss.setdefault("tt_course", NEW)
    for k in ("tt_name", "tt_teacher", "tt_room", "tt_note"):
        ss.setdefault(k, "")
    ss.setdefault("tt_credits", 2.0)
    ss.setdefault("tt_days", [])
    ss.setdefault("tt_mode", MODE_P)
    ss.setdefault("tt_p_start", PERIODS[0][0])
    ss.setdefault("tt_p_end", PERIODS[0][0])
    ss.setdefault("tt_c_start", time(8, 0))
    ss.setdefault("tt_c_end", time(9, 0))
    ss.setdefault("tt_msgs", [])


def _on_course_change() -> None:
    """選了已填過的課程 → 自動帶入資料；選「新課程」→ 清空。"""
    ss = st.session_state
    course = find_course(load_data(), ss.tt_course)
    ss.tt_name = course["name"] if course else ""
    ss.tt_teacher = course.get("teacher", "") if course else ""
    ss.tt_room = course.get("room", "") if course else ""
    ss.tt_credits = float(course.get("credits", 0)) if course else 2.0
    ss.tt_note = course.get("note", "") if course else ""


def _on_start_change() -> None:
    ss = st.session_state
    if PERIOD_LABELS.index(ss.tt_p_end) < PERIOD_LABELS.index(ss.tt_p_start):
        ss.tt_p_end = ss.tt_p_start


def _add_slots() -> None:
    ss = st.session_state
    err = lambda text: ss.tt_msgs.append(("error", text))
    name = ss.tt_name.strip()
    if not name:
        return err("請輸入課程名稱")
    if not ss.tt_days:
        return err("請至少選一個星期")

    if ss.tt_mode == MODE_P:
        a, b = ss.tt_p_start, ss.tt_p_end
        if PERIOD_LABELS.index(b) < PERIOD_LABELS.index(a):
            return err("結束節次不能早於開始節次")
        start, end, periods = PERIOD_TIME[a][0], PERIOD_TIME[b][1], [a, b]
    else:
        if ss.tt_c_end <= ss.tt_c_start:
            return err("結束時間必須晚於開始時間")
        start, end, periods = f"{ss.tt_c_start:%H:%M}", f"{ss.tt_c_end:%H:%M}", None

    data = load_data()
    picked = find_course(data, ss.tt_course)
    if picked and picked["name"].casefold() == name.casefold():
        course = picked  # 沿用已填過的課程（教授、學分、備註可順手更新）
    else:  # 新課程，或改了名字 → 以名字比對，沒有就建立（改名請到「課程管理」）
        course = next((c for c in data["courses"] if c["name"].casefold() == name.casefold()), None)
        if course is None:
            course = {"id": uuid.uuid4().hex}
            data["courses"].append(course)
    course.update(name=name, teacher=ss.tt_teacher.strip(), room=ss.tt_room.strip(),
                  credits=float(ss.tt_credits), note=ss.tt_note.strip())

    added, notes = [], []
    for d in sorted(ss.tt_days):
        if any(s["course_id"] == course["id"] and s["day"] == d and s["start"] == start
               and s["end"] == end for s in data["slots"]):
            notes.append(f"{WEEKDAYS[d]}已有相同時段，略過")
            continue
        for s in data["slots"]:
            if s["day"] == d and overlaps(start, end, s["start"], s["end"]):
                other = find_course(data, s["course_id"])
                if other and other["id"] != course["id"]:
                    notes.append(f"⚠️ {WEEKDAYS[d]} 與「{other['name']}」時間重疊")
        data["slots"].append({"id": uuid.uuid4().hex, "course_id": course["id"], "day": d,
                              "periods": periods, "start": start, "end": end,
                              "room": ss.tt_room.strip()})
        added.append(WEEKDAYS[d])
    save_data(data)

    ss.tt_course = course["id"]  # 之後再填同一門課的其他時段更方便
    if added:
        ss.tt_msgs.append(("success", f"已新增「{name}」：{'、'.join(added)} {start}–{end}"))
    for n in notes:
        ss.tt_msgs.append(("warning", n))


# ---------- 課表格子 ----------
def grid_html(data: dict) -> tuple[str, list[dict]]:
    """回傳 (週課表 HTML, 對不到任何節次的時段)。"""
    courses = {c["id"]: c for c in data["courses"]}
    color = {c["id"]: PALETTE[i % len(PALETTE)] for i, c in enumerate(data["courses"])}
    slots = [s for s in data["slots"] if s["course_id"] in courses]
    days = list(range(5)) + [d for d in (5, 6) if any(s["day"] == d for s in slots)]

    orphans = [s for s in slots
               if not any(overlaps(s["start"], s["end"], a, b) for _, a, b in PERIODS)]

    head = "<tr><th></th>" + "".join(f"<th>{WEEKDAYS[d]}</th>" for d in days) + "</tr>"
    rows = []
    for i, (label, a, b) in enumerate(PERIODS):
        tds = [f'<td class="tt-p">{esc(label)}<small>{a}<br>{b}</small></td>']
        for d in days:
            hits = [s for s in slots if s["day"] == d and overlaps(s["start"], s["end"], a, b)]
            if not hits:
                tds.append('<td class="tt-e"></td>')
                continue
            blocks = []
            for s in hits:
                bg, fg = color[s["course_id"]]
                first = i == 0 or not overlaps(s["start"], s["end"], PERIODS[i - 1][1], PERIODS[i - 1][2])
                if first:
                    c = courses[s["course_id"]]
                    lines = [f"<b>{esc(c['name'])}</b>"]
                    if s.get("room"):
                        lines.append(f"📍{esc(s['room'])}")
                    if c.get("teacher"):
                        lines.append(esc(c["teacher"]))
                    inner = "<br>".join(lines)
                else:
                    inner = "&nbsp;"
                blocks.append(f'<div class="tt-c" style="background:{bg};border-left:4px solid {fg}">{inner}</div>')
            tds.append("<td>" + "".join(blocks) + "</td>")
        rows.append("<tr>" + "".join(tds) + "</tr>")
    return f'<div class="tt-wrap"><table class="tt">{head}{"".join(rows)}</table></div>', orphans


# ---------- 頁面 ----------
def _tab_overview(data: dict) -> None:
    if not data["courses"]:
        st.info("還沒有課程，到「➕ 新增時段」填入第一門課吧！")
        return
    c1, c2, c3 = st.columns(3)
    c1.metric("課程數", len(data["courses"]))
    c2.metric("總學分", f"{sum(float(c.get('credits', 0)) for c in data['courses']):g}")
    c3.metric("每週上課時段", len(data["slots"]))
    table, orphans = grid_html(data)
    html(table)
    if orphans:
        courses = {c["id"]: c for c in data["courses"]}
        st.caption("以下時段不在任何節次內，未顯示在表格：" + "；".join(
            f"{courses[s['course_id']]['name']} {slot_label(s)}" for s in orphans))


def _tab_add(data: dict) -> None:
    ss = st.session_state
    msgs, ss.tt_msgs = ss.tt_msgs, []
    for kind, text in msgs:
        if kind == "success":
            st.toast(text, icon="✅")
        getattr(st, kind)(text)

    names = {c["id"]: c["name"] for c in data["courses"]}
    options = [NEW] + sorted(names, key=lambda i: names[i].casefold())
    if ss.tt_course not in options:
        ss.tt_course = NEW
    st.selectbox("選擇已填過的課程（會自動帶入資料）", options, key="tt_course",
                 format_func=lambda i: "➕ 新課程" if i == NEW else names[i],
                 on_change=_on_course_change)

    c1, c2 = st.columns([3, 1])
    c1.text_input("課程名稱", key="tt_name", placeholder="例如：微積分")
    c2.number_input("學分", min_value=0.0, max_value=12.0, step=1.0, format="%g", key="tt_credits")
    c3, c4 = st.columns(2)
    c3.text_input("授課教授", key="tt_teacher")
    c4.text_input("教室", key="tt_room")
    st.text_input("備註（選填）", key="tt_note")

    st.divider()
    st.multiselect("星期（可複選，同節次的多天一次加入）", list(range(7)), key="tt_days",
                   format_func=WEEKDAYS.__getitem__, placeholder="選擇星期")
    st.radio("時段類型", [MODE_P, MODE_C], key="tt_mode", horizontal=True)
    if ss.tt_mode == MODE_P:
        fmt = lambda p: f"第 {p} 節　{PERIOD_TIME[p][0]}–{PERIOD_TIME[p][1]}"
        s1, s2 = st.columns(2)
        s1.selectbox("開始節次", PERIOD_LABELS, key="tt_p_start", format_func=fmt,
                     on_change=_on_start_change)
        s2.selectbox("結束節次", PERIOD_LABELS, key="tt_p_end", format_func=fmt)
        if PERIOD_LABELS.index(ss.tt_p_end) >= PERIOD_LABELS.index(ss.tt_p_start):
            st.caption(f"⏰ {PERIOD_TIME[ss.tt_p_start][0]}–{PERIOD_TIME[ss.tt_p_end][1]}")
    else:
        t1, t2 = st.columns(2)
        t1.time_input("開始時間", key="tt_c_start", step=300)
        t2.time_input("結束時間", key="tt_c_end", step=300)

    st.button("➕ 新增這個時段", type="primary", on_click=_add_slots)
    st.caption("選已填過的課程時，修改教授 / 學分 / 備註會一併更新該課程；想改課程名稱請到「課程管理」。")


def _tab_manage(data: dict) -> None:
    if not data["courses"]:
        st.info("還沒有課程。")
        return
    for c in sorted(data["courses"], key=lambda c: c["name"].casefold()):
        cid = c["id"]
        mine = sorted((s for s in data["slots"] if s["course_id"] == cid),
                      key=lambda s: (s["day"], to_min(s["start"])))
        with st.expander(f"{c['name']}　·　{float(c.get('credits', 0)):g} 學分　·　{len(mine)} 個時段"):
            with st.form(f"edit_{cid}"):
                f1, f2 = st.columns([3, 1])
                name = f1.text_input("課程名稱", c["name"])
                credits = f2.number_input("學分", 0.0, 12.0, float(c.get("credits", 0)), 1.0, format="%g")
                teacher = st.text_input("授課教授", c.get("teacher", ""))
                note = st.text_input("備註", c.get("note", ""))
                if st.form_submit_button("💾 儲存課程資料") and name.strip():
                    c.update(name=name.strip(), credits=float(credits),
                             teacher=teacher.strip(), note=note.strip())
                    save_data(data)
                    st.rerun()
            for s in mine:
                l, r = st.columns([8, 1])
                room = f"　📍{s['room']}" if s.get("room") else ""
                l.markdown(f"🕘 {slot_label(s)}{room}")
                if r.button("🗑️", key=f"del_slot_{s['id']}", help="刪除這個時段"):
                    data["slots"] = [x for x in data["slots"] if x["id"] != s["id"]]
                    save_data(data)
                    st.rerun()
            if st.button("🗑️ 刪除整門課程（含所有時段）", key=f"del_course_{cid}"):
                data["courses"] = [x for x in data["courses"] if x["id"] != cid]
                data["slots"] = [x for x in data["slots"] if x["course_id"] != cid]
                save_data(data)
                st.rerun()


def render() -> None:
    hero("我的課表", "依學校節次填入課程，同一門課可重複選用", "📆")
    _init_state()
    data = load_data()
    tab1, tab2, tab3 = st.tabs(["📆 我的課表", "➕ 新增時段", "📚 課程管理"])
    with tab1:
        _tab_overview(data)
    with tab2:
        _tab_add(data)
    with tab3:
        _tab_manage(data)


FEATURE = Feature(title="課表", icon="📆", render=render, slug="timetable")
