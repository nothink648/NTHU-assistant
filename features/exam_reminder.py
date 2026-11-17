"""📅 考試 / 作業提醒：新增 / 刪除考試或作業，並顯示倒數時間。

每一項有 kind：exam（考試，可填地點與考古題連結）或 homework（作業，截止時間 + 選填的作業連結）；
舊資料沒有 kind 時視為考試。
都可以連結課表裡的科目（exam["course_id"]），卡片會顯示該課程的顏色與教授，課表上也會標出來。
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime, time

import streamlit as st

from core.i18n import fmt_day, t
from core.storage import load_user_json, save_user_json
from core.icons import before_css, icon, label
from core.ui import badge, card, empty, esc, hero, html
from features.base import Feature
from features.timetable import course_colors, load_data as load_timetable

DATA_FILE = "exams.json"
WARN_DAYS = 3  # 幾天內的考試 / 作業用警示色標示
KINDS = {"exam": ("考試", "Exam", "#6C63FF"), "homework": ("作業", "Homework", "#E08A1E")}  # kind -> (中文, 英文, 標籤色)
HOMEWORK_DUE = time(23, 59)  # 作業預設截止時間


def kind_of(exam: dict) -> str:
    return exam.get("kind") if exam.get("kind") in KINDS else "exam"


def kind_label(kind: str) -> str:
    zh, en, _ = KINDS[kind]
    return t(zh, en)


def kind_name(exam: dict) -> str:
    return kind_label(kind_of(exam))


def kind_badge(exam: dict) -> str:
    return badge(kind_name(exam), KINDS[kind_of(exam)][2])


def when_html(exam: dict, dt: datetime | None = None) -> str:
    """考試：日期時間 + 地點；作業：截止 日期時間。"""
    dt = dt or exam_datetime(exam)
    when = f"{fmt_day(dt, year=True)} {dt:%H:%M}"
    if kind_of(exam) == "homework":
        return f"{icon('alarm') or '⏰'} {t('截止', 'Due')} {when}"
    place = f"　{icon('pin')}{esc(exam['place'])}" if exam.get("place") else ""
    return f"{icon('event') or '🗓️'} {when}{place}"


# ---------- 資料邏輯（可被其他頁面重複使用） ----------
def load_exams() -> list[dict]:
    data = load_user_json(DATA_FILE, [])
    return data if isinstance(data, list) else []


def save_exams(exams: list[dict]) -> None:
    save_user_json(DATA_FILE, exams)


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
        return t(f"{days} 天 {hours} 小時", f"{days}d {hours}h")
    return t(f"{hours} 小時 {minutes} 分", f"{hours}h {minutes}m")


def course_html(exam: dict, timetable: dict | None = None) -> str:
    """連結的課表科目：課程色標籤 + 教授。課程被刪掉就不顯示。"""
    timetable = timetable or load_timetable()
    course = next((c for c in timetable["courses"] if c["id"] == exam.get("course_id")), None)
    if not course:
        return ""
    teacher = f'<span class="muted">　{icon("person")} {esc(course["teacher"])}</span>' if course.get("teacher") else ""
    return (f'<div style="margin:2px 0 4px">{badge(course["name"], course_colors(timetable)[course["id"]], ico="book")}'
            f'{teacher}</div>')


def exam_card(exam: dict, now: datetime, timetable: dict | None = None) -> str:
    dt = exam_datetime(exam)
    urgent = (dt - now).days < WARN_DAYS
    left = countdown_text(dt, now)
    tag = badge(t(f"剩 {left}", f"{left} left"), "#E5486F" if urgent else "#6C63FF", ico="hourglass")
    return (f'<div class="card exam exam-card {"urgent" if urgent else ""}"><div class="card-head">'
            f'<span class="card-title">{kind_badge(exam)} {esc(exam["subject"])}</span>{tag}</div>'
            f'{course_html(exam, timetable)}<div class="muted">{when_html(exam, dt)}</div>{links_html(exam)}</div>')


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
    """考古題 / 作業連結做成可點的小膠囊，另開新分頁；作業沒填連結時顯示淡色「無連結」。"""
    homework = kind_of(exam) == "homework"
    links = [u for u in exam.get("links") or [] if isinstance(u, str) and u.lower().startswith(("http://", "https://"))]
    if not links:
        return (f'<div class="links"><span class="muted">{icon("link") or "🔗"} {t("無連結", "No link")}</span></div>'
                if homework else "")
    ico, text = ("link", t("作業連結", "Homework link")) if homework else ("file", t("考古題", "Past exam"))
    chips = "".join(
        f'<a class="link-chip" href="{esc(u)}" target="_blank" rel="noopener noreferrer" title="{esc(u)}">'
        f'{icon(ico) or ("🔗" if homework else "📄")} {text}{"" if len(links) == 1 else f" {i}"}</a>'
        for i, u in enumerate(links, 1))
    return f'<div class="links">{chips}</div>'


# ---------- 頁面 ----------
def render() -> None:
    hero(t("考試 / 作業提醒", "Exams & Homework"), t("新增考試或作業，隨時掌握倒數", "Add exams or homework and track the countdown"), "alarm")
    # 「新增考試或作業」展開區與「新增」按鈕前面的 add icon
    html("<style>" + before_css(".st-key-exam_add [data-testid='stExpander'] summary p", "add")
         + before_css(".st-key-exam_add [data-testid='stFormSubmitButton'] button p", "add") + "</style>")

    timetable = load_timetable()
    courses = {c["id"]: c for c in timetable["courses"]}
    course_opts = [""] + sorted(courses, key=lambda i: courses[i]["name"].casefold())
    course_fmt = lambda i: courses[i]["name"] if i in courses else (i or t("不連結（自行輸入名稱）", "None (type a name)"))

    with st.container(key="exam_add"), st.expander(label("add", t("新增考試或作業", "Add exam or homework")), expanded=False):
        # 類型放在表單外面：切換時表單欄位會立刻跟著變（表單裡的元件要按送出才會更新）
        kind = st.radio(t("要新增什麼？", "What are you adding?"), list(KINDS), format_func=kind_label, horizontal=True,
                        key="add_kind")
        name = kind_label(kind)
        with st.form("add_exam", clear_on_submit=True):
            cid = st.selectbox(t("課表科目（選填）", "Course (optional)"), course_opts, format_func=course_fmt,
                               help=t(f"連結後，{name}卡片會顯示課程顏色與教授，課表上也會標出這項{name}",
                                      "Linked items show the course color and teacher, and appear on your timetable"))
            subject = st.text_input(t(f"{name}名稱", f"{name} name"), placeholder=(
                t("例如：期中考（有選課表科目時，會自動加上科目名稱）", "e.g. Midterm (the course name is added automatically)")
                if kind == "exam" else
                t("例如：作業三、期末報告（有選課表科目時，會自動加上科目名稱）", "e.g. Homework 3 (the course name is added automatically)")))
            c1, c2 = st.columns(2)
            if kind == "exam":
                d = c1.date_input(t("日期", "Date"))
                tm = c2.time_input(t("時間", "Time"), step=300)
                place = st.text_input(t("地點（選填，連結科目時留空會用上課教室）", "Location (optional; defaults to the classroom)"))
                links_raw = st.text_area(t("歷屆考古題連結（選填，一行一個）", "Past exam links (optional, one per line)"), height=90,
                                         placeholder="https://drive.google.com/...\nhttps://...")
            else:
                d = c1.date_input(t("截止日期", "Due date"))
                tm = c2.time_input(t("截止時間", "Due time"), HOMEWORK_DUE, step=300)
                place = ""
                links_raw = st.text_input(t("作業連結（選填）", "Homework link (optional)"),
                                          placeholder="https://eeclass.nthu.edu.tw/...",
                                          help=t("填入作業頁面網址，清單上會出現可直接點擊開啟的按鈕",
                                                 "Paste the homework page URL to get a clickable button in the list"))
            if st.form_submit_button(t("新增", "Add"), type="primary"):
                when = datetime.combine(d, tm)
                links, bad = parse_links(links_raw)
                course = courses.get(cid)
                subject = subject.strip()
                if course and course["name"] not in subject:
                    subject = f"{course['name']} {subject or name}"
                if kind == "exam":
                    place = place.strip() or (course.get("room", "") if course else "")
                if not subject:
                    st.warning(t(f"請選擇課表科目或輸入{name}名稱", "Choose a course or enter a name"))
                elif when < datetime.now():
                    st.warning(t("這個時間已經過了，請確認日期與時間", "That time has already passed, please check the date and time"))
                elif bad:
                    st.warning(t("以下連結格式不正確（需以 http:// 或 https:// 開頭）：", "These links are invalid (must start with http:// or https://): ")
                               + "、".join(bad))
                else:
                    exams = load_exams()
                    exams.append({"id": uuid.uuid4().hex, "kind": kind, "subject": subject,
                                  "datetime": when.isoformat(), "place": place,
                                  "links": links, "course_id": cid if course else ""})
                    save_exams(exams)
                    st.toast(t(f"已新增{name}：{subject}", f"Added {name.lower()}: {subject}"), icon=":material/check_box:")

    now = datetime.now()
    upcoming = get_upcoming_exams(now)

    if not upcoming:
        html(card(empty(icon("party") or "🎉", t("目前沒有即將到來的考試或作業，點上方「新增考試或作業」加入吧！",
                                                 "Nothing coming up. Use “Add exam or homework” above to add one."))))
        return

    n_hw = sum(kind_of(e) == "homework" for e in upcoming)
    n_ex = len(upcoming) - n_hw
    st.caption(t(f"共 {len(upcoming)} 項即將到來（考試 {n_ex}、作業 {n_hw}）　·　"
                 f"{WARN_DAYS} 天內的會以紅色標示　·　按卡片右上角的 ⋮ 可修改、連結科目或刪除",
                 f"{len(upcoming)} upcoming ({n_ex} exams, {n_hw} homework)　·　"
                 f"Items within {WARN_DAYS} days are shown in red　·　Use ⋮ on a card to edit, link a course or delete"))
    html(MENU_CSS)
    for exam in upcoming:
        with st.container():  # 每張卡片一個容器：⋮ 選單用 CSS 疊在卡片右上角
            _menu(exam, course_opts, course_fmt)
            html(exam_card(exam, now, timetable))


# 把「⋮」選單按鈕定位到卡片右上角（同一個容器裡：先選單、後卡片）
_EC = ':is([data-testid="stElementContainer"],.element-container)'
# 選單按鈕的外層：新版是 stLayoutWrapper / stElementContainer，1.37 直接是 stPopover
_PM = (':is([data-testid="stLayoutWrapper"]:has(> [data-testid="stPopover"]),'
       f'{_EC}:has(> [data-testid="stPopover"]),[data-testid="stPopover"]):has(+ {_EC} .exam-card)')
MENU_CSS = f"""<style>
[data-testid="stVerticalBlock"]:has(> {_EC} .exam-card){{position:relative;gap:0!important}}
[data-testid="stVerticalBlock"] > {_PM}{{position:absolute!important;top:12px;right:12px;z-index:5;width:auto!important}}
{_PM} button{{min-height:0;height:30px;width:34px;padding:0;border-radius:10px;
  border:none;background:transparent;font-size:1.25rem;font-weight:800;line-height:1}}
{_PM} button:hover{{background:var(--acc-soft);transform:none;box-shadow:none}}
{_PM} button [data-testid="stMarkdownContainer"] [data-testid="stIconMaterial"]{{font-size:1.35rem}}
{_PM} button > div > :is(svg,[data-testid="stIconMaterial"]):last-child,{_PM} button > :is(svg,[data-testid="stIconMaterial"]):last-child{{display:none}}
.exam-card .card-head{{padding-right:40px}}
.pm-h{{font-weight:700;margin:2px 0 4px}}
</style>"""


MENU_LABEL = ":material/more_vert:"  # 直立三點；新版 Streamlit 用文字「⋮」當標籤時選單會打不開


def _menu(exam: dict, course_opts: list[str], course_fmt) -> None:
    """卡片右上角的 ⋮：連結科目 / 修改 / 刪除。"""
    eid = exam["id"]
    with st.popover(MENU_LABEL):
        html(f'<div class="pm-h">{icon("link") or "🔗"} {t("連結課表科目", "Link a course")}</div>')  # 新版 Streamlit：popover 內放粗體 markdown 會打不開，改用 HTML
        cur = exam.get("course_id") if exam.get("course_id") in course_opts else ""
        st.selectbox(t("課表科目", "Course"), course_opts, index=course_opts.index(cur), format_func=course_fmt,
                     key=f"link_{eid}", on_change=_relink, args=(exam,), label_visibility="collapsed")

        name = kind_name(exam)
        homework = kind_of(exam) == "homework"
        html(f'<div class="pm-h">{icon("edit") or "✏️"} {t(f"修改{name}", f"Edit {name.lower()}")}</div>')
        dt = exam_datetime(exam)
        with st.form(f"edit_{eid}", border=False):
            st.text_input(t(f"{name}名稱", f"{name} name"), exam["subject"], key=f"ed_subject_{eid}")
            c1, c2 = st.columns(2)
            c1.date_input(t("截止日期", "Due date") if homework else t("日期", "Date"), dt.date(), key=f"ed_date_{eid}")
            c2.time_input(t("截止時間", "Due time") if homework else t("時間", "Time"), dt.time(), step=300,
                          key=f"ed_time_{eid}")
            if not homework:
                st.text_input(t("地點", "Location"), exam.get("place", ""), key=f"ed_place_{eid}")
                st.text_area(t("歷屆考古題連結（一行一個）", "Past exam links (one per line)"),
                             "\n".join(exam.get("links") or []), height=80, key=f"ed_links_{eid}")
            else:
                st.text_input(t("作業連結（留空表示無連結）", "Homework link (leave empty for none)"),
                              " ".join(exam.get("links") or []), placeholder="https://eeclass.nthu.edu.tw/...",
                              key=f"ed_links_{eid}")
            st.form_submit_button(label("save", t("儲存修改", "Save changes")), type="primary", on_click=_save_edit,
                                  args=(exam,), use_container_width=True, key=f"save_exam_{eid}")

        st.button(label("trash", t(f"刪除這項{name}", f"Delete this {name.lower()}")), key=f"del_{eid}", on_click=_delete,
                  args=(exam,), use_container_width=True)


def _save_edit(exam: dict) -> None:
    ss, eid = st.session_state, exam["id"]
    subject = ss.get(f"ed_subject_{eid}", "").strip()
    links, bad = parse_links(ss.get(f"ed_links_{eid}", ""))
    if not subject:
        st.toast(t(f"{kind_name(exam)}名稱不能空白，未儲存", "Name can't be empty; not saved"), icon=":material/warning:")
        return
    if bad:
        st.toast(t("連結格式不正確（需以 http:// 或 https:// 開頭）：", "Invalid links (must start with http:// or https://): ")
                 + "、".join(bad), icon=":material/warning:")
        return
    when = datetime.combine(ss[f"ed_date_{eid}"], ss[f"ed_time_{eid}"])
    exams = load_exams()
    for e in exams:
        if e.get("id") == eid:
            e.update(subject=subject, datetime=when.isoformat())
            e["links"] = links  # 考試：考古題；作業：作業連結
            if kind_of(e) == "exam":  # 作業沒有地點
                e["place"] = ss.get(f"ed_place_{eid}", "").strip()
    save_exams(exams)
    st.toast(t(f"已更新：{subject}", f"Updated: {subject}")
             + (t("（時間已過，不會再顯示在清單）", " (time has passed, it won't be listed)") if when < datetime.now() else ""),
             icon=":material/edit:")


def _relink(exam: dict) -> None:
    cid = st.session_state.get(f"link_{exam['id']}", "")
    exams = load_exams()
    for e in exams:
        if e.get("id") == exam["id"]:
            e["course_id"] = cid
    save_exams(exams)
    st.toast(t("已更新連結的課表科目", "Linked course updated"), icon=":material/link:")


def _delete(exam: dict) -> None:
    save_exams([e for e in load_exams() if e.get("id") != exam["id"]])
    st.toast(t(f"已刪除：{exam['subject']}", f"Deleted: {exam['subject']}"), icon=":material/delete:")


FEATURE = Feature(title="考試 / 作業提醒", icon="📅", render=render, slug="exams", ico="alarm",
                  title_en="Exams & Homework")
