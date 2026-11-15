"""📆 課表：依學校節次（或自訂時間）填入課程；同一門課第二次起可直接選用已填過的資料。

資料存在 data/timetable.json：
  courses：課程資料（名稱、教授、預設教室、學分、備註）
  slots  ：上課時段（哪一門課、星期幾、起訖時間）；一門課可以有很多個時段
節次時間定義在 config.py 的 PERIODS。
"""
from __future__ import annotations

import re
import unicodedata
import uuid
from datetime import datetime, time

import streamlit as st

from config import PERIODS
from core import nthu_api
from core.i18n import is_en, t, weekday
from core.storage import load_user_json, save_user_json
from core.icons import before_css, has, icon, label, tab_css
from core.ui import esc, hero, html
from features.base import Feature

DATA_FILE = "timetable.json"
NEW = "__new__"
MODE_P, MODE_C = "依學校節次", "自訂時間"  # 內部值（存在 session）；顯示文字用 mode_label()
PERIOD_TIME = {label: (start, end) for label, start, end in PERIODS}
PERIOD_LABELS = [p[0] for p in PERIODS]
PALETTE = ["#6C63FF", "#E5486F", "#2E9E6A", "#E08A1E", "#2C8BC9", "#9B51E0", "#B89A0B", "#1E9E94"]


def _tint(hex_color: str, alpha: float = 0.22) -> str:
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (1, 3, 5))
    return f"rgba({r},{g},{b},{alpha})"


# ---------- 資料邏輯（可被其他頁面重複使用） ----------
def load_data() -> dict:
    data = load_user_json(DATA_FILE, {})
    if not isinstance(data, dict):
        data = {}
    data.setdefault("courses", [])
    data.setdefault("slots", [])
    return data


def save_data(data: dict) -> None:
    save_user_json(DATA_FILE, data)


def to_min(hhmm: str) -> int:
    h, m = map(int, hhmm.split(":"))
    return h * 60 + m


def overlaps(a_start: str, a_end: str, b_start: str, b_end: str) -> bool:
    return to_min(a_start) < to_min(b_end) and to_min(a_end) > to_min(b_start)


def find_course(data: dict, course_id: str) -> dict | None:
    return next((c for c in data["courses"] if c["id"] == course_id), None)


def course_colors(data: dict) -> dict[str, str]:
    """每門課的代表色（課表方塊、考試卡片共用同一個顏色）。"""
    return {c["id"]: PALETTE[i % len(PALETTE)] for i, c in enumerate(data["courses"])}


def exams_by_course(now: datetime | None = None) -> dict[str, list[dict]]:
    """{課程 id: [即將到來、有連結這門課的考試 / 作業]}（延遲 import，避免和考試頁互相 import）。"""
    from features.exam_reminder import get_upcoming_exams
    result: dict[str, list[dict]] = {}
    for e in get_upcoming_exams(now):
        if e.get("course_id"):
            result.setdefault(e["course_id"], []).append(e)
    return result


def mode_label(mode: str) -> str:
    return t(mode, "School periods") if mode == MODE_P else t(mode, "Custom time")


def slot_label(slot: dict) -> str:
    p = slot.get("periods")
    if p:
        period = (t(f"第{p[0]}節", f"Period {p[0]}") if p[0] == p[1]
                  else t(f"第{p[0]}–{p[1]}節", f"Periods {p[0]}–{p[1]}"))
    else:
        period = t("自訂", "Custom")
    return f"{weekday(slot['day'])}　{period}　{slot['start']}–{slot['end']}"


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
    ss.setdefault("tt_lookup_msgs", [])


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
        return err(t("請輸入課程名稱", "Please enter a course name"))
    if not ss.tt_days:
        return err(t("請至少選一個星期", "Please choose at least one day"))

    if ss.tt_mode == MODE_P:
        a, b = ss.tt_p_start, ss.tt_p_end
        if PERIOD_LABELS.index(b) < PERIOD_LABELS.index(a):
            return err(t("結束節次不能早於開始節次", "The end period cannot be before the start period"))
        start, end, periods = PERIOD_TIME[a][0], PERIOD_TIME[b][1], [a, b]
    else:
        if ss.tt_c_end <= ss.tt_c_start:
            return err(t("結束時間必須晚於開始時間", "The end time must be after the start time"))
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
            notes.append(t(f"{weekday(d)}已有相同時段，略過", f"{weekday(d)}: same slot already exists, skipped"))
            continue
        for s in data["slots"]:
            if s["day"] == d and overlaps(start, end, s["start"], s["end"]):
                other = find_course(data, s["course_id"])
                if other and other["id"] != course["id"]:
                    notes.append(t(f"{weekday(d)} 與「{other['name']}」時間重疊", f"{weekday(d)}: overlaps with “{other['name']}”"))
        data["slots"].append({"id": uuid.uuid4().hex, "course_id": course["id"], "day": d,
                              "periods": periods, "start": start, "end": end,
                              "room": ss.tt_room.strip()})
        added.append(weekday(d))
    save_data(data)

    ss.tt_course = course["id"]  # 之後再填同一門課的其他時段更方便
    if added:
        ss.tt_days = []  # 清空星期，避免重複按到又加一次
        ss.tt_msgs.append(("success", t(f"已新增「{name}」：{'、'.join(added)} {start}–{end}",
                                         f"Added “{name}”: {', '.join(added)} {start}–{end}")))
    for n in notes:
        ss.tt_msgs.append(("warning", n))


# ---------- 從課程資料庫帶入（NTHU Data API /courses） ----------
DAY_CODES = "MTWRFSU"  # 校務系統的星期代號：M=週一 … U=週日
SEARCH_LIMIT = 40


def semester_label(code: str) -> str:
    """'11510' → '115 上' / '115 Fall'。"""
    year, term = code[:3], code[3:4]
    return f"{year} " + {"1": t("上", "Fall"), "2": t("下", "Spring")}.get(term, t("暑", "Summer"))


def load_semesters() -> list[str]:
    data, _ = nthu_api.get("/courses/semesters", ttl=86400)
    return [s for s in data or [] if isinstance(s, str)]


def load_catalog(semester: str) -> tuple[list[dict], str | None]:
    data, err = nthu_api.get(f"/courses/{semester}", ttl=86400)  # 一學期約 3000 門、4 MB，一天抓一次就好
    return [c for c in data or [] if isinstance(c, dict) and c.get("id")], err


def course_code(c: dict) -> str:
    """'11510CS  233601' → 'CS 233601'（去掉學期與多餘空白）。"""
    return re.sub(r"\s+", " ", str(c.get("id", ""))[5:]).strip()


def _norm(text: str) -> str:
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", str(text or ""))).casefold()


def search_catalog(catalog: list[dict], query: str) -> list[dict]:
    """課號（可省略空白與學期）、中英文課名、老師名字都能搜；多個關鍵字要全部符合。"""
    words = [_norm(w) for w in query.split() if w.strip()]
    if not words:
        return []
    out = []
    for c in catalog:
        hay = _norm(" ".join([c["id"], c.get("chinese_title") or "", c.get("english_title") or ""]
                             + [f"{p.get('name_zh') or ''}{p.get('name_en') or ''}" for p in c.get("lecturers") or []]))
        if all(w in hay for w in words):
            out.append(c)
    # 課號完全符合的排最前面，其次是未停開的
    q = _norm(query)
    out.sort(key=lambda c: (not _norm(c["id"]).endswith(q), bool(c.get("is_cancelled"))))
    return out[:SEARCH_LIMIT]


def catalog_name(c: dict) -> str:
    # NFKC：全形英數字（微積分Ｂ一）轉成半形，和手動輸入的課名一致
    zh, en = (unicodedata.normalize("NFKC", c.get(k) or "").strip() for k in ("chinese_title", "english_title"))
    return t(zh or en, en or zh)


def catalog_teacher(c: dict) -> str:
    names = [t(p.get("name_zh") or p.get("name_en") or "", p.get("name_en") or p.get("name_zh") or "")
             for p in c.get("lecturers") or []]
    return t("、", ", ").join(n for n in names if n)


def catalog_room(classroom: str) -> str:
    """'GEN II綜二203' → '綜二203'（中文介面去掉英文館名代號）；多餘空白一律拿掉。"""
    room = re.sub(r"\s+", " ", classroom or "").strip()
    if not is_en():
        room = re.sub(r"^[A-Za-z][A-Za-z0-9 .&-]*?(?=[一-鿿])", "", room)
        room = re.sub(r"(?<=[一-鿿])\s+(?=\w)", "", room)
    return room


def catalog_slots(c: dict) -> list[dict]:
    """meetings 的 time_codes（例如 W2、W3、W4）→ 每天連續的節次合併成一個時段。"""
    slots = []
    for m in c.get("meetings") or []:
        by_day: dict[int, list[int]] = {}
        for code in m.get("time_codes") or []:
            if len(code) == 2 and code[0] in DAY_CODES and code[1] in PERIOD_LABELS:
                by_day.setdefault(DAY_CODES.index(code[0]), []).append(PERIOD_LABELS.index(code[1]))
        for day, idx in sorted(by_day.items()):
            idx = sorted(set(idx))
            run = [idx[0]]
            for i in idx[1:] + [None]:
                if i is not None and i == run[-1] + 1:
                    run.append(i)
                    continue
                a, b = PERIOD_LABELS[run[0]], PERIOD_LABELS[run[-1]]
                slots.append({"day": day, "periods": [a, b], "start": PERIOD_TIME[a][0], "end": PERIOD_TIME[b][1],
                              "room": catalog_room(m.get("classroom", ""))})
                if i is not None:
                    run = [i]
    return slots


def catalog_option(c: dict) -> str:
    times = " ".join(f"{weekday(s['day'])}{s['periods'][0]}" + (f"-{s['periods'][1]}" if s["periods"][1] != s["periods"][0] else "")
                     for s in catalog_slots(c)) or t("無固定時間", "no fixed time")
    cr = float(c.get("credits") or 0)
    parts = [course_code(c), catalog_name(c), catalog_teacher(c), t(f"{cr:g} 學分", f"{cr:g} cr"), times]
    if c.get("is_cancelled"):
        parts.append(t("已停開", "cancelled"))
    return "　·　".join(p for p in parts if p)


def _add_catalog_course(c: dict) -> None:
    """把整門課（課程資料 + 所有上課時段）加入課表。同名課程沿用、相同時段不重複加入。"""
    ss = st.session_state
    data = load_data()
    name = catalog_name(c)
    slots = catalog_slots(c)
    course = next((x for x in data["courses"] if x["name"].casefold() == name.casefold()), None)
    if course is None:
        course = {"id": uuid.uuid4().hex}
        data["courses"].append(course)
    course.update(name=name, teacher=catalog_teacher(c), room=slots[0]["room"] if slots else course.get("room", ""),
                  credits=float(c.get("credits") or 0), code=course_code(c),
                  note="Offered in English" if c.get("language_code") == "en" else course.get("note", ""))

    added, notes = [], []
    for s in slots:
        if any(x["course_id"] == course["id"] and x["day"] == s["day"] and x["start"] == s["start"]
               and x["end"] == s["end"] for x in data["slots"]):
            notes.append(t(f"{weekday(s['day'])} {s['start']} 已有相同時段，略過",
                           f"{weekday(s['day'])} {s['start']}: same slot already exists, skipped"))
            continue
        for x in data["slots"]:
            other = find_course(data, x["course_id"])
            if x["day"] == s["day"] and overlaps(s["start"], s["end"], x["start"], x["end"]) and other \
                    and other["id"] != course["id"]:
                notes.append(t(f"{weekday(s['day'])} 與「{other['name']}」時間重疊",
                               f"{weekday(s['day'])}: overlaps with “{other['name']}”"))
        data["slots"].append({"id": uuid.uuid4().hex, "course_id": course["id"], **s})
        added.append(f"{weekday(s['day'])} {s['start']}–{s['end']}")
    save_data(data)

    if added:
        ss.tt_lookup_msgs.append(("success", t(f"已加入「{name}」：{'、'.join(added)}", f"Added “{name}”: {', '.join(added)}")))
    elif not slots:
        ss.tt_lookup_msgs.append(("info", t(f"「{name}」沒有固定上課時間，只加入課程資料（可到「課程管理」查看）",
                                     f"“{name}” has no fixed class time; only the course info was added")))
    for n in notes:
        ss.tt_lookup_msgs.append(("warning", n))


def _catalog_lookup() -> None:
    semesters = load_semesters()
    with st.container(border=True, key="tt_lookup"):
        st.markdown(f"**{icon('search') or '🔍'} {t('輸入課號或課名，一鍵加入課表', 'Find a course by number or name')}**",
                    unsafe_allow_html=True)
        if not semesters:
            st.warning(t("暫時連不上課程資料 API，請改用下方手動填寫。",
                         "The course API is unreachable right now; please fill in the form below instead."))
            return
        c1, c2 = st.columns([1, 3])
        sem = c1.selectbox(t("學期", "Semester"), semesters, format_func=semester_label, key="tt_sem")
        q = c2.text_input(t("課號 / 課名 / 老師", "Course no. / name / teacher"), key="tt_q",
                          placeholder=t("例如：CS 233601、離散數學、微積分 顏東勇", "e.g. CS 233601, Discrete Mathematics"))
        if not q.strip():
            return
        with st.spinner(t("正在載入本學期課程…", "Loading this semester's courses…")):
            catalog, err = load_catalog(sem)
        if err:
            st.caption(err)
        found = search_catalog(catalog, q)
        if not found:
            st.info(t("找不到符合的課程，換個關鍵字試試。", "No matching courses. Try another keyword."))
            return
        by_id = {c["id"]: c for c in found}
        pick = st.selectbox(t(f"搜尋結果（{len(found)} 筆{'，只列前 ' + str(SEARCH_LIMIT) + ' 筆' if len(found) >= SEARCH_LIMIT else ''}）",
                              f"Results ({len(found)})"), list(by_id), format_func=lambda i: catalog_option(by_id[i]),
                            key="tt_pick")
        c = by_id[pick]
        rooms = "、".join(dict.fromkeys(s["room"] for s in catalog_slots(c) if s["room"]))
        info = [t(f"教室：{rooms}", f"Room: {rooms}") if rooms else "",
                t("英文授課", "Taught in English") if c.get("language_code") == "en" else ""]
        if any(info):
            st.caption("　·　".join(i for i in info if i))
        st.button(label("add", t("加入課表", "Add to timetable")), type="primary", key="tt_lookup_add",
                  on_click=_add_catalog_course, args=(c,), disabled=bool(c.get("is_cancelled")))
    _show_msgs("tt_lookup_msgs")


def _show_msgs(key: str) -> None:
    """訊息顯示在按鈕正下方，按下去立刻看得到結果（顯示一次就清掉）。"""
    ss = st.session_state
    msgs, ss[key] = ss.get(key, []), []
    for kind, text in msgs:
        if kind == "success":
            st.toast(text, icon=":material/check_box:")
        getattr(st, kind)(text)


# ---------- 課表格子 ----------
def build_blocks(slots: list[dict]) -> list[dict]:
    """把同一門課、同一天、節次相連（或重疊）的時段合併成一個方塊。

    回傳 [{day, course_id, i0, i1, slots}]，i0 / i1 是 PERIODS 的列索引（含）。
    """
    per: dict[tuple, list] = {}
    for s in slots:
        hit = [i for i, (_, a, b) in enumerate(PERIODS) if overlaps(s["start"], s["end"], a, b)]
        if hit:
            per.setdefault((s["day"], s["course_id"]), []).append((hit[0], hit[-1], s))
    blocks = []
    for (day, cid), items in per.items():
        cur = None
        for i0, i1, s in sorted(items, key=lambda x: x[0]):
            if cur and i0 <= cur["i1"] + 1:  # 相連 → 接在同一個方塊
                cur["i1"] = max(cur["i1"], i1)
                cur["slots"].append(s)
            else:
                cur = {"day": day, "course_id": cid, "i0": i0, "i1": i1, "slots": [s]}
                blocks.append(cur)
    return blocks


def assign_lanes(day_blocks: list[dict]) -> None:
    """不同課程時間重疊（衝突）時，讓它們左右並排而不是疊在一起。"""
    groups: list[dict] = []
    for b in sorted(day_blocks, key=lambda b: (b["i0"], b["i1"])):
        if groups and b["i0"] <= groups[-1]["end"]:
            groups[-1]["blocks"].append(b)
            groups[-1]["end"] = max(groups[-1]["end"], b["i1"])
        else:
            groups.append({"blocks": [b], "end": b["i1"]})
    for g in groups:
        lane_end: list[int] = []
        for b in g["blocks"]:
            for k, e in enumerate(lane_end):
                if b["i0"] > e:
                    b["lane"], lane_end[k] = k, b["i1"]
                    break
            else:
                b["lane"] = len(lane_end)
                lane_end.append(b["i1"])
        for b in g["blocks"]:
            b["lanes"] = len(lane_end)


def grid_html(data: dict) -> tuple[str, list[dict]]:
    """回傳 (週課表 HTML, 對不到任何節次的時段)。用 CSS grid，相連的課會合成一個方塊。"""
    courses = {c["id"]: c for c in data["courses"]}
    accent = course_colors(data)
    exams = exams_by_course()
    slots =[s for s in data["slots"] if s["course_id"] in courses]
    days = list(range(5)) + [d for d in (5, 6) if any(s["day"] == d for s in slots)]
    col = {d: k + 2 for k, d in enumerate(days)}  # grid 欄號（第 1 欄是節次）

    orphans = [s for s in slots
               if not any(overlaps(s["start"], s["end"], a, b) for _, a, b in PERIODS)]
    blocks = [b for b in build_blocks(slots) if b["day"] in col]
    for d in days:
        assign_lanes([b for b in blocks if b["day"] == d])

    cells = ['<div class="tt-h" style="grid-row:1;grid-column:1"></div>']
    today = datetime.now().weekday()
    cells += [f'<div class="tt-h{" today" if d == today else ""}" style="grid-row:1;grid-column:{col[d]}">'
              f'{weekday(d)}</div>' for d in days]
    for i, (period, a, b) in enumerate(PERIODS):
        cells.append(f'<div class="tt-p" style="grid-row:{i + 2};grid-column:1">{esc(period)}'
                     f'<small>{a}<br>{b}</small></div>')
        cells += [f'<div class="tt-e" style="grid-row:{i + 2};grid-column:{col[d]}"></div>' for d in days]

    for n, b in enumerate(sorted(blocks, key=lambda b: (b["day"], b["i0"]))):
        c = courses[b["course_id"]]
        color = accent[b["course_id"]]
        rooms = list(dict.fromkeys(s["room"] for s in b["slots"] if s.get("room")))
        lines = [f"<b>{esc(c['name'])}</b>"]
        if rooms:
            lines.append(icon("pin") + esc(" / ".join(rooms)))
        if c.get("teacher"):
            lines.append(esc(c["teacher"]))
        if exams.get(b["course_id"]):  # 連結到這門課的下一個考試 / 作業
            e = exams[b["course_id"]][0]
            kind = t("作業", "Homework") if e.get("kind") == "homework" else t("考試", "Exam")
            lines.append(f'<span style="color:#E5486F;font-weight:600">{icon("edit") or "📝"} {kind} {e["datetime"][5:10].replace("-", "/")}</span>')
        w = 100 / b["lanes"]
        cells.append(
            f'<div class="tt-c" style="grid-row:{b["i0"] + 2} / span {b["i1"] - b["i0"] + 1};'
            f'grid-column:{col[b["day"]]};width:{w:.2f}%;margin-left:{b["lane"] * w:.2f}%;'
            f'background:{_tint(color)};border-left:4px solid {color};animation-delay:{min(n, 12) * 0.04:.2f}s"'
            f' title="{esc(c["name"])}　{esc(c.get("note", ""))}">{"<br>".join(lines)}</div>')

    grid_style = (f"grid-template-columns:62px repeat({len(days)},minmax(96px,1fr));"
                  f"grid-template-rows:auto repeat({len(PERIODS)},minmax(46px,auto))")
    return f'<div class="tt-wrap"><div class="ttg" style="{grid_style}">{"".join(cells)}</div></div>', orphans


# ---------- 頁面 ----------
def _tab_overview(data: dict) -> None:
    if not data["courses"]:
        st.info(t("還沒有課程，到「新增時段」填入第一門課吧！", "No courses yet. Add your first one under “Add slot”!"))
        return
    table, orphans = grid_html(data)
    html(table)
    if orphans:
        courses = {c["id"]: c for c in data["courses"]}
        st.caption(t("以下時段不在任何節次內，未顯示在表格：", "These slots fall outside the periods and are not shown: ") + "；".join(
            f"{courses[s['course_id']]['name']} {slot_label(s)}" for s in orphans))


def _tab_add(data: dict) -> None:
    ss = st.session_state
    names = {c["id"]: c["name"] for c in data["courses"]}
    options = [NEW] + sorted(names, key=lambda i: names[i].casefold())
    if ss.tt_course not in options:
        ss.tt_course = NEW

    _catalog_lookup()
    st.markdown(f"<div class='muted' style='margin:6px 2px'>{t('或手動填寫（課程資料庫沒有的課、自訂時段）', 'Or fill in manually (courses not in the catalog, custom times)')}</div>",
                unsafe_allow_html=True)
    with st.container(border=True):
        st.markdown(f"**{icon('book') or '📘'} {t('課程資料', 'Course info')}**", unsafe_allow_html=True)
        st.selectbox(t("選擇已填過的課程（會自動帶入資料）", "Pick an existing course (fills in its details)"), options,
                     key="tt_course", format_func=lambda i: t("➕ 新課程", "➕ New course") if i == NEW else names[i],
                     on_change=_on_course_change)
        c1, c2 = st.columns([3, 1])
        c1.text_input(t("課程名稱", "Course name"), key="tt_name", placeholder=t("例如：微積分", "e.g. Calculus"))
        c2.number_input(t("學分", "Credits"), min_value=0.0, max_value=12.0, step=1.0, format="%g", key="tt_credits")
        c3, c4 = st.columns(2)
        c3.text_input(t("授課教授", "Teacher"), key="tt_teacher")
        c4.text_input(t("教室", "Classroom"), key="tt_room")
        st.text_input(t("備註（選填）", "Note (optional)"), key="tt_note")

    with st.container(border=True):
        st.markdown(f"**{icon('clock') or '🕘'} {t('上課時段', 'Class time')}**", unsafe_allow_html=True)
        st.multiselect(t("星期（可複選，同節次的多天一次加入）", "Days (pick several to add them all at once)"), list(range(7)),
                       key="tt_days", format_func=weekday, placeholder=t("選擇星期", "Choose days"))
        st.radio(t("時段類型", "Time type"), [MODE_P, MODE_C], key="tt_mode", horizontal=True, format_func=mode_label)
        if ss.tt_mode == MODE_P:
            fmt = lambda p: t(f"第 {p} 節", f"Period {p}") + f"　{PERIOD_TIME[p][0]}–{PERIOD_TIME[p][1]}"
            s1, s2 = st.columns(2)
            s1.selectbox(t("開始節次", "Start period"), PERIOD_LABELS, key="tt_p_start", format_func=fmt,
                         on_change=_on_start_change)
            s2.selectbox(t("結束節次", "End period"), PERIOD_LABELS, key="tt_p_end", format_func=fmt)
            if PERIOD_LABELS.index(ss.tt_p_end) >= PERIOD_LABELS.index(ss.tt_p_start):
                st.caption(f"{icon('alarm') or '⏰'} {PERIOD_TIME[ss.tt_p_start][0]}–{PERIOD_TIME[ss.tt_p_end][1]}",
                           unsafe_allow_html=True)
        else:
            t1, t2 = st.columns(2)
            t1.time_input(t("開始時間", "Start time"), key="tt_c_start", step=300)
            t2.time_input(t("結束時間", "End time"), key="tt_c_end", step=300)

    st.button(label("add", t("新增這個時段", "Add this slot")), type="primary", on_click=_add_slots, key="tt_add_btn")

    _show_msgs("tt_msgs")
    st.caption(t("選已填過的課程時，修改教授 / 學分 / 備註會一併更新該課程；想改課程名稱請到「課程管理」。",
                 "Editing teacher / credits / note of an existing course updates that course; rename courses under “Manage courses”."))


def _tab_manage(data: dict) -> None:
    if not data["courses"]:
        st.info(t("還沒有課程。", "No courses yet."))
        return
    exams = exams_by_course()
    for c in sorted(data["courses"], key=lambda c: c["name"].casefold()):
        cid = c["id"]
        mine = sorted((s for s in data["slots"] if s["course_id"] == cid),
                      key=lambda s: (s["day"], to_min(s["start"])))
        n_exam = (t(f"　·　{len(exams[cid])} 項考試 / 作業", f"　·　{len(exams[cid])} exams / homework")
                  if exams.get(cid) else "")
        cr = float(c.get("credits", 0))
        with st.expander(f"{c['name']}　·　" + t(f"{cr:g} 學分　·　{len(mine)} 個時段", f"{cr:g} credits　·　{len(mine)} slots")
                         + n_exam):
            for e in exams.get(cid, []):
                place = f"　{icon('pin')}{esc(e['place'])}" if e.get("place") else ""
                st.markdown(f"{icon('edit') or '📝'} **{esc(e['subject'])}**　{e['datetime'][:16].replace('T', ' ')}{place}",
                            unsafe_allow_html=True)
            with st.form(f"edit_{cid}"):
                f1, f2 = st.columns([3, 1])
                name = f1.text_input(t("課程名稱", "Course name"), c["name"])
                credits = f2.number_input(t("學分", "Credits"), 0.0, 12.0, float(c.get("credits", 0)), 1.0, format="%g")
                teacher = st.text_input(t("授課教授", "Teacher"), c.get("teacher", ""))
                note = st.text_input(t("備註", "Note"), c.get("note", ""))
                if st.form_submit_button(label("save", t("儲存課程資料", "Save course")), key=f"save_course_{cid}") and name.strip():
                    c.update(name=name.strip(), credits=float(credits),
                             teacher=teacher.strip(), note=note.strip())
                    save_data(data)
                    st.rerun()
            for s in mine:
                l, r = st.columns([8, 1])
                room = f"　{icon('pin')}{esc(s['room'])}" if s.get("room") else ""
                l.markdown(f"{icon('clock') or '🕘'} {slot_label(s)}{room}", unsafe_allow_html=True)
                # 有圖時按鈕文字只放零寬空白，垃圾桶由 CSS 畫上（core/icons.py）
                if r.button("​" if has("trash") else "🗑️", key=f"del_slot_{s['id']}", help=t("刪除這個時段", "Delete this slot")):
                    data["slots"] = [x for x in data["slots"] if x["id"] != s["id"]]
                    save_data(data)
                    st.rerun()
            if st.button(label("trash", t("刪除整門課程（含所有時段）", "Delete course (and all its slots)")), key=f"del_course_{cid}"):
                data["courses"] = [x for x in data["courses"] if x["id"] != cid]
                data["slots"] = [x for x in data["slots"] if x["course_id"] != cid]
                save_data(data)
                st.rerun()


def render() -> None:
    hero(t("我的課表", "My Timetable"), t("依學校節次填入課程，同一門課可重複選用", "Fill in courses by school period; reuse a course for more slots"), "calendar")
    _init_state()
    data = load_data()
    # 分頁標籤與「新增這個時段」按鈕的 icon（標籤只能放純文字，icon 用 CSS 畫上）
    html("<style>" + tab_css("tt_tabs", ["calendar", "add", "manage-dates"])
         + before_css(".st-key-tt_add_btn button p", "add") + "</style>")
    with st.container(key="tt_tabs"):
        tab1, tab2, tab3 = st.tabs([label("calendar", t("我的課表", "My timetable")), label("add", t("新增時段", "Add slot")),
                                    label("manage-dates", t("課程管理", "Manage courses"))])
    with tab1:
        _tab_overview(data)
    with tab2:
        _tab_add(data)
    with tab3:
        _tab_manage(data)


FEATURE = Feature(title="課表", icon="📆", render=render, slug="timetable", ico="calendar",
                  title_en="Timetable")
