"""📅 考試 / 作業提醒：月曆檢視；點日期新增、點項目看完整資訊並修改 / 刪除，下方保留倒數清單。

每一項有 kind：exam（考試，可填地點與考古題連結）或 homework（作業，截止時間 + 選填的作業連結）；
舊資料沒有 kind 時視為考試。
都可以連結課表裡的科目（exam["course_id"]），卡片會顯示該課程的顏色與教授，課表上也會標出來。
"""
from __future__ import annotations

import calendar as cal_module
import re
import uuid
from datetime import date, datetime, time

import streamlit as st

from core.i18n import fmt_day, month_year, t, weekday
from core.storage import load_user_json, save_user_json
from core.icons import before_css, has, icon, label
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
    urgent = dt >= now and (dt - now).days < WARN_DAYS
    if dt < now:  # 月曆上也看得到已經過去的項目
        tag = badge(t("已結束", "Past"), "#8A8A9A")
    else:
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
def _flash(msg: str, ico: str) -> None:
    """操作結果：存起來，下一次畫面重畫時用 toast 顯示（視窗裡的操作也能看到）。"""
    st.session_state.exam_flash = (msg, ico)


def _course_ctx() -> tuple[dict, dict, list[str], object]:
    timetable = load_timetable()
    courses = {c["id"]: c for c in timetable["courses"]}
    course_opts = [""] + sorted(courses, key=lambda i: courses[i]["name"].casefold())
    course_fmt = lambda i: courses[i]["name"] if i in courses else (i or t("不連結（自行輸入名稱）", "None (type a name)"))
    return timetable, courses, course_opts, course_fmt


def _add_form(courses: dict, course_opts: list[str], course_fmt, kp: str = "", day: date | None = None) -> None:
    """新增考試 / 作業的表單。kp：元件 key 的前綴（彈出視窗用另一組，避免和頁面上的重複）；day：預設日期。"""
    # 類型放在表單外面：切換時表單欄位會立刻跟著變（表單裡的元件要按送出才會更新）
    kind = st.radio(t("要新增什麼？", "What are you adding?"), list(KINDS), format_func=kind_label, horizontal=True,
                    key=f"{kp}add_kind")
    name = kind_label(kind)
    default_day = day or date.today()
    with st.form(f"{kp}add_exam", clear_on_submit=True):
        cid = st.selectbox(t("課表科目（選填）", "Course (optional)"), course_opts, format_func=course_fmt,
                           help=t(f"連結後，{name}卡片會顯示課程顏色與教授，課表上也會標出這項{name}",
                                  "Linked items show the course color and teacher, and appear on your timetable"))
        subject = st.text_input(t(f"{name}名稱", f"{name} name"), placeholder=(
            t("例如：期中考（有選課表科目時，會自動加上科目名稱）", "e.g. Midterm (the course name is added automatically)")
            if kind == "exam" else
            t("例如：作業三、期末報告（有選課表科目時，會自動加上科目名稱）", "e.g. Homework 3 (the course name is added automatically)")))
        c1, c2 = st.columns(2)
        if kind == "exam":
            d = c1.date_input(t("日期", "Date"), default_day)
            tm = c2.time_input(t("時間", "Time"), time(9, 0), step=300)
            place = st.text_input(t("地點（選填，連結科目時留空會用上課教室）", "Location (optional; defaults to the classroom)"))
            links_raw = st.text_area(t("歷屆考古題連結（選填，一行一個）", "Past exam links (optional, one per line)"), height=90,
                                     placeholder="https://drive.google.com/...\nhttps://...")
        else:
            d = c1.date_input(t("截止日期", "Due date"), default_day)
            tm = c2.time_input(t("截止時間", "Due time"), HOMEWORK_DUE, step=300)
            place = ""
            links_raw = st.text_input(t("作業連結（選填）", "Homework link (optional)"),
                                      placeholder="https://eeclass.nthu.edu.tw/...",
                                      help=t("填入作業頁面網址，清單上會出現可直接點擊開啟的按鈕",
                                             "Paste the homework page URL to get a clickable button in the list"))
        if st.form_submit_button(t("新增", "Add"), type="primary", key=f"{kp}add_submit"):
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
                st.session_state.exam_cal_ym = (when.year, when.month)  # 月曆跳到新增的那個月
                _flash(t(f"已新增{name}：{subject}", f"Added {name.lower()}: {subject}"), ":material/check_box:")
                st.rerun()  # 整頁重畫：月曆立刻出現新的一項（在彈出視窗裡也會順便關閉視窗）


def render() -> None:
    ss = st.session_state
    hero(t("考試 / 作業提醒", "Exams & Homework"), t("新增考試或作業，隨時掌握倒數", "Add exams or homework and track the countdown"), "alarm")
    # 「新增考試或作業」展開區與「新增」按鈕前面的 add icon
    html("<style>" + before_css(".st-key-cal_add button p", "add", size="1.25em")
         + before_css(".st-key-cal_prev button p", "arrow-up", rotate=-90, size="1.2em")
         + before_css(".st-key-cal_next button p", "arrow-up", rotate=90, size="1.2em")
         + ":is(.st-key-cal_prev,.st-key-cal_next) button p::before{margin-right:0}"
         + before_css("[class*='add_submit'] button p", "add")
         + before_css(".st-key-exam_list summary p", "time-list") + "</style>")
    html(CAL_CSS.replace("\n", ""))  # 壓成一行：多行時 Markdown 會把 [class*=…] 裡的 * 當成格式，CSS 變成文字
    html(MENU_CSS)
    ss.pop("exam_refresh", None)  # 只給彈出視窗用；整頁重畫時清掉
    if "exam_flash" in ss:
        msg, ico = ss.pop("exam_flash")
        st.toast(msg, icon=ico)

    timetable, courses, course_opts, course_fmt = _course_ctx()
    now = datetime.now()
    _calendar(timetable, courses, course_opts, course_fmt, now)

    upcoming = get_upcoming_exams(now)
    n_hw = sum(kind_of(e) == "homework" for e in upcoming)
    n_ex = len(upcoming) - n_hw
    with st.expander(label("time-list", t(f"即將到來的清單（考試 {n_ex}、作業 {n_hw}）",
                                          f"Upcoming list ({n_ex} exams, {n_hw} homework)")), key="exam_list"):
        if not upcoming:
            html(card(empty(icon("party") or "🎉", t("目前沒有即將到來的考試或作業，點月曆上的日期或上方「新增考試或作業」加入吧！",
                                                     "Nothing coming up. Click a day on the calendar or use “Add exam or homework” above."))))
        else:
            st.caption(t(f"{WARN_DAYS} 天內的會以紅色標示　·　按卡片右上角的 ⋮ 可修改、連結科目或刪除",
                         f"Items within {WARN_DAYS} days are shown in red　·　Use ⋮ on a card to edit, link a course or delete"))
            for exam in upcoming:
                with st.container():  # 每張卡片一個容器：⋮ 選單用 CSS 疊在卡片右上角
                    with st.popover(MENU_LABEL):
                        _manage(exam, course_opts, course_fmt)
                    html(exam_card(exam, now, timetable))


# ---------- 月曆 ----------
def _md(text: str) -> str:
    """按鈕文字會被當成 Markdown：把特殊符號跳脫。"""
    return re.sub(r"([\\`*_{}\[\]<>()#+\-.!|~])", r"\\\1", text)


def _chip_label(exam: dict, courses: dict) -> str:
    """月曆上只顯示：類型、科目、標題。"""
    course = courses.get(exam.get("course_id"))
    title = exam["subject"]
    if course:
        title = title.replace(course["name"], "", 1).strip() or kind_name(exam)
        return f"**{_md(kind_name(exam))}** {_md(course['name'])} · {_md(title)}"
    return f"**{_md(kind_name(exam))}** {_md(title)}"


def _shift_month(step: int) -> None:
    y, m = st.session_state.exam_cal_ym
    m += step
    y, m = y + (m - 1) // 12, (m - 1) % 12 + 1
    st.session_state.exam_cal_ym = (y, m)


def _this_month() -> None:
    st.session_state.exam_cal_ym = (date.today().year, date.today().month)


def _calendar(timetable: dict, courses: dict, course_opts: list[str], course_fmt, now: datetime) -> None:
    ss = st.session_state
    ss.setdefault("exam_cal_ym", (now.year, now.month))
    y, m = ss.exam_cal_ym
    exams = sorted((e for e in load_exams() if _valid(e)), key=exam_datetime)
    by_day: dict[date, list[dict]] = {}
    for e in exams:
        by_day.setdefault(exam_datetime(e).date(), []).append(e)
    colors = course_colors(timetable)

    with st.container(border=True, key="exam_cal"):  # 整個月曆放在同一個方框
        c1, c2, c3, c4, c5 = st.columns([0.7, 3, 1, 0.7, 2.4], vertical_alignment="center")
        arrow = has("arrow-up")  # 用 arrow-up 圖示轉向當左右箭頭（CSS 畫上），沒有圖時用文字箭頭
        c1.button("​" if arrow else "‹", key="cal_prev", on_click=_shift_month, args=(-1,), use_container_width=True,
                  help=t("上個月", "Previous month"))
        n_month = sum(1 for d in by_day if (d.year, d.month) == (y, m) for _ in by_day[d])
        c2.markdown(f'<div class="cal-title">{month_year(y, m)}<small>{t(f"本月 {n_month} 項", f"{n_month} this month")}</small></div>',
                    unsafe_allow_html=True)
        c3.button(t("今天", "Today"), key="cal_today", on_click=_this_month, use_container_width=True)
        c4.button("​" if arrow else "›", key="cal_next", on_click=_shift_month, args=(1,), use_container_width=True,
                  help=t("下個月", "Next month"))
        if c5.button(label("add", t("新增考試或作業", "Add exam or homework")), type="primary", key="cal_add",
                     use_container_width=True):
            _open_add(now.date(), courses, course_opts, course_fmt, title=t("新增考試或作業", "Add exam or homework"))
        st.caption(t("點日期可在那天新增考試或作業；點月曆上的項目可查看完整資訊、修改或刪除。",
                     "Click a day to add an exam or homework on it; click an item to see all details, edit or delete it."))

        heads = st.columns(7, gap="small")
        for i, h in enumerate(heads):
            h.markdown(f'<div class="cal-wd{" we" if i >= 5 else ""}">{weekday(i)}</div>', unsafe_allow_html=True)

        today = now.date()
        rules = []  # 每個項目左邊的課程顏色
        for week in cal_module.Calendar(firstweekday=0).monthdatescalendar(y, m):
            cols = st.columns(7, gap="small")
            for col, d in zip(cols, week):
                state = "t" if d == today else ("o" if d.month != m else "n")
                with col.container(key=f"cal_c_{state}_{d.isoformat()}"):
                    if st.button(str(d.day), key=f"cal_d_{state}_{d.isoformat()}", use_container_width=True,
                                 help=t(f"在 {fmt_day(d)} 新增", f"Add on {fmt_day(d)}")):
                        _open_add(d, courses, course_opts, course_fmt)
                    for e in by_day.get(d, []):
                        past = "p" if exam_datetime(e) < now else "u"
                        key = f"cal_e_{kind_of(e)}_{past}_{e['id']}"
                        color = colors.get(e.get("course_id"))
                        if color:
                            rules.append(f".st-key-{key} button{{border-left-color:{color}!important}}")
                        if st.button(_chip_label(e, courses), key=key, use_container_width=True):
                            _open_detail(e, timetable, course_opts, course_fmt)
        if rules:
            html("<style>" + "".join(rules) + "</style>")


def _open_add(d: date, courses: dict, course_opts: list[str], course_fmt, title: str = "") -> None:
    def body() -> None:
        _add_form(courses, course_opts, course_fmt, kp="dlg_", day=d)
    title = title or t(f"新增到 {fmt_day(d, year=True)}", f"Add on {fmt_day(d, year=True)}")
    st.dialog(title, width="large")(body)()


def _open_detail(exam: dict, timetable: dict, course_opts: list[str], course_fmt) -> None:
    def body() -> None:
        if st.session_state.pop("exam_refresh", False):  # 視窗裡改了資料：整頁重畫（同時關閉視窗）
            st.rerun()
        with st.container():  # 卡片獨立一個容器：清單用的 CSS（容器內間距 0）不會影響下面的表單
            html(exam_card(exam, datetime.now(), timetable))
        st.divider()
        _manage(exam, course_opts, course_fmt, kp="dlg_")
    st.dialog(f"{kind_name(exam)}：{exam['subject']}", width="large")(body)()


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

_EXAM_C, _HW_C = KINDS["exam"][2], KINDS["homework"][2]
CAL_CSS = f"""<style>
.st-key-exam_cal{{background:var(--card-bg);border-radius:18px!important;padding:16px 16px 18px!important}}
.st-key-cal_add button{{min-height:46px;border-radius:14px;font-weight:800;box-shadow:0 8px 22px rgba(108,99,255,.35)}}
.st-key-cal_add button p{{font-size:1rem;font-weight:800}}
.st-key-cal_add button:hover{{transform:translateY(-1px);box-shadow:0 10px 26px rgba(108,99,255,.45)}}
.cal-title{{text-align:center;font-weight:800;font-size:1.3rem;line-height:1.2}}
.cal-title small{{display:block;font-size:.75rem;font-weight:500;opacity:.6}}
.cal-wd{{text-align:center;font-size:.78rem;font-weight:700;opacity:.65}}
.cal-wd.we{{color:#E5486F}}
/* 一週 7 格不換行（手機上也維持月曆排列） */
.st-key-exam_cal [data-testid="stHorizontalBlock"]:has(:is([class*="st-key-cal_c_"],.cal-wd)){{flex-wrap:nowrap!important;gap:6px!important}}
.st-key-exam_cal [data-testid="stHorizontalBlock"]:has(:is([class*="st-key-cal_c_"],.cal-wd)) > [data-testid="stColumn"]{{min-width:0!important;flex:1 1 0!important;width:auto!important}}
[class*="st-key-cal_c_"]{{border:1px solid var(--line);border-radius:12px;padding:4px 4px 6px;min-height:104px;
  gap:3px!important;background:var(--card-bg);transition:border-color .15s}}
[class*="st-key-cal_c_"]:hover{{border-color:var(--acc-line)}}
[class*="st-key-cal_c_o_"]{{opacity:.45}}
[class*="st-key-cal_c_t_"]{{border-color:var(--acc);box-shadow:0 0 0 1px var(--acc) inset}}
/* 日期按鈕：看起來像日期數字，滑過時出現 ＋ */
[class*="st-key-cal_d_"] button{{min-height:0;height:26px;padding:0 6px;border:none;background:transparent;
  justify-content:flex-start;box-shadow:none}}
[class*="st-key-cal_d_"] button:hover{{background:var(--acc-soft);transform:none}}
[class*="st-key-cal_d_"] button p{{font-weight:700;font-size:.85rem}}
[class*="st-key-cal_d_"] button:hover p::after{{content:"　＋";opacity:.7;font-weight:800}}
[class*="st-key-cal_d_t_"] button p{{background:var(--acc);color:#fff;border-radius:999px;padding:1px 8px}}
/* 項目：類型顏色 + 左邊科目顏色，最多兩行 */
[class*="st-key-cal_e_"] button{{min-height:0;padding:3px 6px;border-radius:7px;border:none;border-left:3px solid transparent;
  justify-content:flex-start;text-align:left;box-shadow:none}}
[class*="st-key-cal_e_"] button:hover{{transform:none;filter:brightness(1.12)}}
[class*="st-key-cal_e_"] button p{{font-size:.72rem;line-height:1.3;white-space:normal;display:-webkit-box;-webkit-line-clamp:2;
  -webkit-box-orient:vertical;overflow:hidden;word-break:break-all}}
[class*="st-key-cal_e_exam_"] button{{background:color-mix(in srgb,{_EXAM_C} 20%,transparent);border-left-color:{_EXAM_C}}}
[class*="st-key-cal_e_exam_"] button strong{{color:color-mix(in srgb,{_EXAM_C} 80%,currentColor)}}
[class*="st-key-cal_e_homework_"] button{{background:color-mix(in srgb,{_HW_C} 20%,transparent);border-left-color:{_HW_C}}}
[class*="st-key-cal_e_homework_"] button strong{{color:color-mix(in srgb,{_HW_C} 85%,currentColor)}}
[class*="st-key-cal_e_"][class*="_p_"] button{{opacity:.5}}
/* 手機直式：上方切換列維持一列（← 月份 今天 →），「新增」獨立一列；月曆格子縮小間距、加寬 */
@media (max-width:640px){{
  .st-key-exam_cal{{padding:10px 5px 10px!important;gap:6px!important}}
  .st-key-exam_cal [data-testid="stHorizontalBlock"]:has(.st-key-cal_prev){{flex-wrap:wrap!important;gap:6px!important;align-items:center}}
  .st-key-exam_cal [data-testid="stColumn"]:is(:has(.st-key-cal_prev),:has(.st-key-cal_next)){{flex:0 0 38px!important;width:38px!important;min-width:0!important}}
  .st-key-exam_cal [data-testid="stColumn"]:has(.st-key-cal_today){{flex:0 0 60px!important;width:60px!important;min-width:0!important}}
  .st-key-exam_cal [data-testid="stColumn"]:has(.cal-title){{flex:1 1 0!important;width:auto!important;min-width:0!important}}
  .st-key-exam_cal [data-testid="stColumn"]:has(.st-key-cal_add){{flex:1 0 100%!important;width:100%!important;order:9}}
  :is(.st-key-cal_prev,.st-key-cal_next,.st-key-cal_today) button{{min-height:0;height:36px;padding:0 4px;border-radius:10px}}
  .st-key-cal_today button p{{font-size:.8rem}}
  .st-key-cal_add button{{min-height:42px}}
  .cal-title{{font-size:1.05rem}}
  .st-key-exam_cal [data-testid="stHorizontalBlock"]:has(:is([class*="st-key-cal_c_"],.cal-wd)){{gap:2px!important}}
  .cal-wd{{font-size:.68rem}}
  .st-key-exam_cal [data-testid="stHorizontalBlock"]:has(.cal-wd){{margin-bottom:8px}}
  .cal-title{{padding-bottom:4px}}
  [class*="st-key-cal_c_"]{{min-height:64px;padding:2px 1px 3px;border-radius:8px;gap:2px!important}}
  [class*="st-key-cal_d_"] button{{height:22px;padding:0;justify-content:center}}
  [class*="st-key-cal_d_"] button p{{font-size:.78rem}}
  [class*="st-key-cal_d_"] button:hover p::after{{content:none}}
  [class*="st-key-cal_e_"] button{{padding:2px 2px 2px 3px;border-radius:5px;border-left-width:2px}}
  [class*="st-key-cal_e_"] button p{{font-size:.6rem;line-height:1.25;-webkit-line-clamp:3}}
}}
</style>"""


MENU_LABEL = ":material/more_vert:"  # 直立三點；新版 Streamlit 用文字「⋮」當標籤時選單會打不開


def _manage(exam: dict, course_opts: list[str], course_fmt, kp: str = "") -> None:
    """連結科目 / 修改 / 刪除（清單卡片的 ⋮ 選單與月曆的詳細資訊視窗共用）。kp：元件 key 前綴。"""
    eid = exam["id"]
    html(f'<div class="pm-h">{icon("link") or "🔗"} {t("連結課表科目", "Link a course")}</div>')  # 新版 Streamlit：popover 內放粗體 markdown 會打不開，改用 HTML
    cur = exam.get("course_id") if exam.get("course_id") in course_opts else ""
    st.selectbox(t("課表科目", "Course"), course_opts, index=course_opts.index(cur), format_func=course_fmt,
                 key=f"{kp}link_{eid}", on_change=_relink, args=(exam, kp), label_visibility="collapsed")

    name = kind_name(exam)
    homework = kind_of(exam) == "homework"
    html(f'<div class="pm-h">{icon("edit") or "✏️"} {t(f"修改{name}", f"Edit {name.lower()}")}</div>')
    dt = exam_datetime(exam)
    with st.form(f"{kp}edit_{eid}", border=False):
        st.text_input(t(f"{name}名稱", f"{name} name"), exam["subject"], key=f"{kp}ed_subject_{eid}")
        c1, c2 = st.columns(2)
        c1.date_input(t("截止日期", "Due date") if homework else t("日期", "Date"), dt.date(), key=f"{kp}ed_date_{eid}")
        c2.time_input(t("截止時間", "Due time") if homework else t("時間", "Time"), dt.time(), step=300,
                      key=f"{kp}ed_time_{eid}")
        if not homework:
            st.text_input(t("地點", "Location"), exam.get("place", ""), key=f"{kp}ed_place_{eid}")
            st.text_area(t("歷屆考古題連結（一行一個）", "Past exam links (one per line)"),
                         "\n".join(exam.get("links") or []), height=80, key=f"{kp}ed_links_{eid}")
        else:
            st.text_input(t("作業連結（留空表示無連結）", "Homework link (leave empty for none)"),
                          " ".join(exam.get("links") or []), placeholder="https://eeclass.nthu.edu.tw/...",
                          key=f"{kp}ed_links_{eid}")
        st.form_submit_button(label("save", t("儲存修改", "Save changes")), type="primary", on_click=_save_edit,
                              args=(exam, kp), use_container_width=True, key=f"save_exam_{kp}{eid}")

    st.button(label("trash", t(f"刪除這項{name}", f"Delete this {name.lower()}")), key=f"del_{kp}{eid}", on_click=_delete,
              args=(exam,), use_container_width=True)


def _save_edit(exam: dict, kp: str = "") -> None:
    ss, eid = st.session_state, exam["id"]
    subject = ss.get(f"{kp}ed_subject_{eid}", "").strip()
    links, bad = parse_links(ss.get(f"{kp}ed_links_{eid}", ""))
    if not subject:
        st.toast(t(f"{kind_name(exam)}名稱不能空白，未儲存", "Name can't be empty; not saved"), icon=":material/warning:")
        return
    if bad:
        st.toast(t("連結格式不正確（需以 http:// 或 https:// 開頭）：", "Invalid links (must start with http:// or https://): ")
                 + "、".join(bad), icon=":material/warning:")
        return
    when = datetime.combine(ss[f"{kp}ed_date_{eid}"], ss[f"{kp}ed_time_{eid}"])
    exams = load_exams()
    for e in exams:
        if e.get("id") == eid:
            e.update(subject=subject, datetime=when.isoformat())
            e["links"] = links  # 考試：考古題；作業：作業連結
            if kind_of(e) == "exam":  # 作業沒有地點
                e["place"] = ss.get(f"{kp}ed_place_{eid}", "").strip()
    save_exams(exams)
    _flash(t(f"已更新：{subject}", f"Updated: {subject}"), ":material/edit:")
    ss.exam_refresh = True


def _relink(exam: dict, kp: str = "") -> None:
    cid = st.session_state.get(f"{kp}link_{exam['id']}", "")
    exams = load_exams()
    for e in exams:
        if e.get("id") == exam["id"]:
            e["course_id"] = cid
    save_exams(exams)
    _flash(t("已更新連結的課表科目", "Linked course updated"), ":material/link:")
    st.session_state.exam_refresh = True


def _delete(exam: dict) -> None:
    save_exams([e for e in load_exams() if e.get("id") != exam["id"]])
    _flash(t(f"已刪除：{exam['subject']}", f"Deleted: {exam['subject']}"), ":material/delete:")
    st.session_state.exam_refresh = True


FEATURE = Feature(title="考試 / 作業提醒", icon="📅", render=render, slug="exams", ico="alarm",
                  title_en="Exams & Homework")
