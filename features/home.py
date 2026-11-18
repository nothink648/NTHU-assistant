"""🏠 首頁：整合各功能的摘要。

版面：問候 → 四格速覽（課程 / 公車 / 考試 / 餐廳）→ 2×2 等高卡片。
每一格都可以點：卡片上蓋一顆透明按鈕，按了用 st.switch_page 跳到對應頁面（考試卡片會展開「即將到來的清單」，
營業中餐廳的每一列會跳到該餐廳）。
"""
from __future__ import annotations

import random
from datetime import datetime

import streamlit as st

from config import app_title
from core.auth import username
from core.i18n import fmt_day, is_en, t, tr, weekday
from core.icons import icon
from core.nav import goto
from core.ui import badge, card, empty, esc, hero, html
from features.base import Feature
from features.bus_schedule import (eta_text, focus_short, focus_routes, get_directions, get_focus, get_next_buses,
                                   load_bus_data, mark_html, route_color, route_dir_label)
from features.exam_reminder import (WARN_DAYS, countdown_text, course_html, exam_datetime, get_upcoming_exams,
                                    kind_badge, kind_name, links_html, when_html)
from features.restaurants import all_restaurants, load_data as load_food, my_restaurants, status
from features.school_calendar import marquee_html
from features.timetable import to_min, today_classes

FOOD_ROWS = 6  # 首頁最多列幾間營業中的餐廳

# 只在首頁注入：四格速覽與等高格線的樣式（動態背景在 core/ui.py，所有分頁共用）。
HOME_CSS = """<style>
/* 卡片陰影 */
.home .card,.stat{box-shadow:0 6px 22px rgba(30,20,90,.07)}

/* 四格速覽 */
.st-key-home_stats{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px;margin:6px 0 2px}
.stat{position:relative;overflow:hidden;display:flex;gap:12px;align-items:center;padding:14px 16px;border-radius:16px;
  background:var(--card-bg);border:1px solid var(--line);animation:popIn .45s var(--ease) both;
  transition:transform .25s var(--ease),box-shadow .25s ease}
[class*="st-key-hs_"]:hover .stat{transform:translateY(-3px);box-shadow:0 12px 26px rgba(108,99,255,.16)}
.stat .bar{position:absolute;left:0;right:0;top:0;height:3px}
.st-key-hs_bus .stat{animation-delay:.06s}.st-key-hs_exam .stat{animation-delay:.12s}.st-key-hs_food .stat{animation-delay:.18s}
.stat .ic{flex:none;width:42px;height:42px;border-radius:12px;display:grid;place-items:center;font-size:1.35rem}
.stat .ic .ico{width:24px;height:24px;vertical-align:0}
.stat .lb{font-size:.78rem;opacity:.65;font-weight:600}
.stat .v{font-size:1.35rem;font-weight:800;line-height:1.25;white-space:nowrap}
.stat .v small{font-size:.8rem;font-weight:700;margin-left:2px;opacity:.75}
.stat .sb{font-size:.78rem;opacity:.62;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.stat .tx{min-width:0}

/* 2×2 等高卡片：grid 讓同一列等高，卡片外層一路撐滿 */
.st-key-home_grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px;align-items:stretch}
:is(.st-key-home_grid,.st-key-home_stats)>[data-testid="stLayoutWrapper"],
[class*="st-key-hc_"],[class*="st-key-hs_"],[class*="st-key-hc_"] div:has(.card),[class*="st-key-hs_"] div:has(.stat){height:100%}
.st-key-home_grid .card{margin:0;height:100%;display:flex;flex-direction:column;
  transition:transform .25s var(--ease),box-shadow .25s ease,border-color .25s ease}
.st-key-home_grid .card .grow{flex:1}
.st-key-hc_exam .card{animation-delay:.08s}.st-key-hc_bus .card{animation-delay:.16s}
.st-key-home_grid .foot{margin-top:auto;padding-top:8px}
[class*="st-key-hc_"]:hover .card{transform:translateY(-3px);box-shadow:0 12px 26px rgba(108,99,255,.16);border-color:var(--acc)}

/* 可點的格子：透明按鈕蓋滿整格；餐廳每一列有自己的按鈕，疊在卡片按鈕上面 */
:is([class*="st-key-hc_"],[class*="st-key-hs_"],.st-key-hl_cal,[class*="st-key-hf_"]){position:relative}
[class*="st-key-go_"]{position:absolute!important;inset:0;z-index:3;margin:0!important}
[class*="st-key-go_f_"]{z-index:4}
[class*="st-key-go_"] div,[class*="st-key-go_"] button{width:100%!important;height:100%!important;min-height:0}
[class*="st-key-go_"] button{opacity:0;cursor:pointer;padding:0;border:0}
[class*="st-key-go_"] button:focus-visible{opacity:1;background:transparent;box-shadow:0 0 0 2px var(--acc);border-radius:16px}
[class*="st-key-go_"] button:focus-visible p{display:none}
[class*="st-key-hf_"]:hover .row{background:var(--acc-soft)}
.st-key-home_grid .links{position:relative;z-index:5}  /* 考古題 / 作業連結要在透明按鈕上面才點得到 */
.st-key-hl_cal:hover .mq{box-shadow:0 0 0 1px var(--acc)}

/* 營業中餐廳：卡片拆成標題 + 每列一個容器，外框畫在容器上 */
.st-key-hc_food{gap:0;background:var(--card-bg);border:1px solid var(--line);border-radius:16px;padding:16px 18px;
  box-shadow:0 6px 22px rgba(30,20,90,.07);animation:popIn .45s var(--ease) both;animation-delay:.24s;
  transition:transform .25s var(--ease),box-shadow .25s ease,border-color .25s ease}
.st-key-hc_food:hover{transform:translateY(-3px);box-shadow:0 12px 26px rgba(108,99,255,.16);border-color:var(--acc)}
.st-key-hc_food .row{margin:0 -6px}
/* Streamlit 的 markdown 底部有 -1rem，平常靠區塊間距抵掉；這裡間距是 0，要歸零才不會疊在一起 */
:is(.st-key-hc_food,[class*="st-key-hc_"],[class*="st-key-hs_"],.st-key-hl_cal) [data-testid="stMarkdownContainer"]{margin-bottom:0}
.st-key-hc_food .foot{margin-top:auto;padding-top:8px}

@media (max-width:900px){.st-key-home_stats{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media (max-width:640px){.st-key-home_grid{grid-template-columns:minmax(0,1fr)}}
</style>"""


# 問候語：依時段分組，每次打開首頁從該時段隨機挑一句；{name} 會換成使用者帳號名稱
GREETINGS = [  # (開始小時, 結束小時, 句子)
    (0, 5, ["{name}，夜深了，早點休息 🌙", "這麼晚還沒睡嗎，{name}？ 🦉", "{name}，熬夜傷身，記得喝水 💧",
            "夜貓子 {name} 你好 🌌", "{name}，明天的事明天再煩惱吧 😴"]),
    (5, 11, ["早安，{name}！今天也加油 ☀️", "{name}，新的一天開始了 🌱", "早啊 {name}，吃早餐了嗎？ 🥪",
             "{name}，早八辛苦了 ☕", "早安 {name}，今天會是好日子 🌤️"]),
    (11, 14, ["午安，{name}！記得吃飯 🍱", "{name}，中午想吃什麼？ 🍜", "午安 {name}，充個電再出發 🔋",
              "{name}，吃飽才有力氣上課 🍙", "嗨 {name}，午休時間到了 😌"]),
    (14, 18, ["午安，{name} ☕", "{name}，下午也要打起精神 💪", "嗨 {name}，來杯飲料續命吧 🧋",
              "{name}，今天的課還順利嗎？ 📚", "再撐一下，{name}，快下課了 ⏳"]),
    (18, 24, ["晚安，{name}，辛苦了 🌆", "{name}，今天也辛苦了 🌙", "晚上好 {name}，記得吃晚餐 🍛",
              "{name}，作業寫完了嗎？ 📝", "好好休息，{name}，明天見 ✨"]),
]
GREETINGS_EN = [
    (0, 5, ["It's late, {name}. Get some rest 🌙", "Still up, {name}? 🦉", "Late night, {name}? Stay hydrated 💧",
            "Hello, night owl {name} 🌌", "{name}, tomorrow's problems can wait 😴"]),
    (5, 11, ["Good morning, {name}! You've got this ☀️", "A fresh new day, {name} 🌱", "Morning, {name}! Had breakfast? 🥪",
             "Early class, {name}? Hang in there ☕", "Good morning, {name}. It's going to be a good day 🌤️"]),
    (11, 14, ["Good afternoon, {name}! Don't skip lunch 🍱", "What's for lunch, {name}? 🍜",
              "Recharge a little, {name} 🔋", "Eat well, {name}, classes need energy 🍙", "Hi {name}, time for a break 😌"]),
    (14, 18, ["Good afternoon, {name} ☕", "Keep it up this afternoon, {name} 💪", "Hi {name}, bubble tea time? 🧋",
              "How are classes going, {name}? 📚", "Almost there, {name}, class is nearly over ⏳"]),
    (18, 24, ["Good evening, {name}. Well done today 🌆", "You worked hard today, {name} 🌙",
              "Evening, {name}! Remember to eat dinner 🍛", "Finished your homework, {name}? 📝",
              "Rest well, {name}. See you tomorrow ✨"]),
]


def greeting(now: datetime, name: str = "") -> str:
    """依目前時段，隨機挑一句問候語（沒有名稱時稱呼「同學」/ "friend"）。"""
    table = GREETINGS_EN if is_en() else GREETINGS
    lines = next(g for s, e, g in table if s <= now.hour < e)
    line = random.choice(lines)
    return (tr(line) if is_en() else line).format(name=name or t("同學", "friend"))  # 印尼文 / 越南文由英文翻譯


def _head(title: str, extra: str = "") -> str:
    return f'<div class="card-head"><span class="card-title">{title}</span>{extra}</div>'


def _grow(inner: str) -> str:
    return f'<div class="grow">{inner}</div>'


# ---------- 資料整理 ----------
def next_bus(now: datetime) -> tuple[str, int] | None:
    """所有路線中最快發車的一班：(說明, 幾分鐘後)。"""
    data, _ = load_bus_data()
    best = None
    for r in focus_routes(data.get("routes", [])):  # 只看「關注路線」（在公車班表頁設定）
        for d in get_directions(r, data.get("origin", "")):
            nxt = get_next_buses(d, now, n=1)
            if nxt and (best is None or nxt[0][1] < best[1]):
                best = (f"{route_dir_label(r, d)} {nxt[0][0]}", nxt[0][1])
    return best


def open_food(now: datetime) -> tuple[list[tuple[dict, dict]], int]:
    """(營業中的餐廳 [(店, 狀態)]，快打烊的排前面；餐飲類總數)。"""
    foods = [r for r in all_restaurants(load_food()) + my_restaurants() if r["is_food"]]
    opened = [(r, s) for r in foods for s in [status(r, now)] if s["is_open"]]
    opened.sort(key=lambda x: (x[1]["key"] != "closing", x[0]["name"]))
    return opened, len(foods)


# ---------- 四格速覽 ----------
def stat(ico: str, color: str, label: str, value: str, sub: str) -> str:
    return (f'<div class="stat"><i class="bar" style="background:{color}"></i>'
            f'<div class="ic" style="background:color-mix(in srgb,{color} 16%,transparent);'
            f'color:color-mix(in srgb,{color} 85%,currentColor)">{ico}</div>'
            f'<div class="tx"><div class="lb">{label}</div>'
            f'<div class="v" style="color:color-mix(in srgb,{color} 80%,currentColor)">{value}</div>'
            f'<div class="sb">{sub}</div></div></div>')


def stats_strip(now: datetime) -> list[str]:
    cur = now.hour * 60 + now.minute
    items = today_classes(now)
    upcoming = [(s, c) for s, c in items if to_min(s["end"]) > cur]
    cal_ico, today_lb = icon("calendar") or "📆", t("今日課程", "Today's classes")
    n_cls = f"{len(items)}<small>{t('堂', ' classes')}</small>"
    if not items:
        cls = stat(cal_ico, "#6C63FF", today_lb, n_cls, t("今天沒有課 😎", "No classes today 😎"))
    elif upcoming:
        s, c = upcoming[0]
        word = t("上課中", "Now") if to_min(s["start"]) <= cur else t("下一堂", "Next")
        cls = stat(cal_ico, "#6C63FF", today_lb, n_cls, f'{word}{t("：", ": ")}{esc(c["name"])} {s["start"]}')
    else:
        cls = stat(cal_ico, "#6C63FF", today_lb, n_cls, t("今天的課都上完了", "All done for today") + " " + (icon("party") or "🎉"))

    nb = next_bus(now)
    if nb:
        m = nb[1]
        val = (t("即將發車", "Leaving") if m < 1 else f"{m}<small>{t('分', ' min')}</small>" if m < 60
               else f"{m // 60}<small>{t('時', 'h ')}</small>{m % 60}<small>{t('分', 'm')}</small>")
        bus = stat(icon("bus") or "🚌", "#2E9E6A", t("下一班公車", "Next bus"), val, esc(nb[0]))
    else:
        bus = stat(icon("bus") or "🚌", "#2E9E6A", t("下一班公車", "Next bus"), "—", t("今天已無班次", "No more buses today"))

    exams = get_upcoming_exams(now)
    if exams:
        days = (exam_datetime(exams[0]).date() - now.date()).days
        exam = stat(icon("alarm") or "📅", "#E5486F", t("考試 / 作業", "Exams & homework"),
                    t("今天", "Today") if days == 0 else f"{days}<small>{t('天後', ' days')}</small>",
                    f'{kind_name(exams[0])}{t("：", ": ")}{esc(exams[0]["subject"])}')
    else:
        exam = stat(icon("alarm") or "📅", "#E5486F", t("考試 / 作業", "Exams & homework"), "—",
                    t("目前沒有考試或作業", "Nothing due") + " " + (icon("party") or "🎉"))

    opened, total = open_food(now)
    food = stat(icon("food") or "🍱", "#E08A1E", t("營業中餐廳", "Open now"), f"{len(opened)}<small>{t('家', ' places')}</small>",
                t(f"校內共 {total} 家", f"{total} on campus"))
    return [cls, bus, exam, food]


# ---------- 卡片 ----------
def class_summary(now: datetime) -> str:
    head = _head((icon("calendar") or "📆 ") + t("今日課程", "Today's classes"), badge(weekday(now.weekday())))
    items = today_classes(now)
    if not items:
        return card(head + _grow(empty("😎", t("今天沒有課", "No classes today"))))
    cur = now.hour * 60 + now.minute
    rows = []
    for s, c in items:
        done = to_min(s["end"]) <= cur
        live = to_min(s["start"]) <= cur < to_min(s["end"])
        room = f'<span class="muted">　{icon("pin")}{esc(s["room"])}</span>' if s.get("room") else ""
        tag = " " + badge(t("上課中", "Now"), "#2E9E6A", live=True) if live else ""
        rows.append(f'<div class="row {"dim" if done else ""}"><span class="t">{esc(c["name"])}{room}</span>'
                    f'<span class="e">{s["start"]}–{s["end"]}{tag}</span></div>')
    finished = sum(to_min(s["end"]) <= cur for s, _ in items)
    pct = round(finished / len(items) * 100)
    bar = (f'<div class="foot"><div class="progress" title="{t("今日進度", "Progress")} {finished}/{len(items)}">'
           f'<i style="width:{pct}%"></i></div>'
           f'<div class="muted" style="margin-top:4px">'
           f'{t(f"已上完 {finished} / {len(items)} 堂", f"{finished} of {len(items)} classes done")}</div></div>')
    return card(head + _grow("".join(rows)) + bar)


def exam_summary(now: datetime) -> str:
    exams = get_upcoming_exams(now)
    head = _head((icon("alarm") or "📅 ") + t("下一個考試 / 作業", "Next exam / homework"),
                 kind_badge(exams[0]) if exams else "")
    if not exams:
        return card(head + _grow(empty(icon("party") or "🎉", t("目前沒有考試或作業", "Nothing due"))))
    e = exams[0]
    dt = exam_datetime(e)
    urgent = (dt - now).days < WARN_DAYS
    main = (f'<div class="big">{esc(e["subject"])}</div>{course_html(e)}'
            f'<div style="margin:4px 0">{badge(t("剩 ", "") + countdown_text(dt, now) + t("", " left"), "#E5486F" if urgent else "#6C63FF", ico="hourglass")}</div>'
            f'<div class="muted">{when_html(e, dt)}</div>{links_html(e)}')
    more = ""
    if len(exams) > 1:
        rest = "".join(f'<div class="row"><span class="t">{kind_badge(x)} {esc(x["subject"])}</span>'
                       f'<span class="e">{exam_datetime(x):%m/%d}</span></div>' for x in exams[1:4])
        more = f'<div class="foot"><div class="muted">{t(f"之後還有 {len(exams) - 1} 項", f"{len(exams) - 1} more")}</div>{rest}</div>'
    return card(head + _grow(main) + more, "exam urgent" if urgent else "exam")


def bus_summary(now: datetime) -> str:
    head = _head((icon("bus") or "🚌 ") + t("最近一班公車", "Next buses"), badge(focus_short(get_focus()), "#2E9E6A", ico="star"))
    data, _ = load_bus_data()
    rows = []
    for r in focus_routes(data.get("routes", [])):  # 只看「關注路線」（在公車班表頁設定）
        for d in get_directions(r, data.get("origin", "")):
            nxt = get_next_buses(d, now, n=1)
            if nxt:
                dot = f'<span class="line-dot sm" style="background:{route_color(r)}"></span>'
                rows.append(f'<div class="row"><span class="t">{dot}{esc(route_dir_label(r, d))}　{nxt[0][0]}{mark_html(nxt[0][2])}</span>'
                            f'<span class="e">{eta_text(nxt[0][1])}</span></div>')
    if not rows:
        msg = t("今天沒有班次", "No buses today") if now.weekday() >= 5 else t("今天已無班次", "No more buses today")
        return card(head + _grow(empty(icon("night-sleeping") or "🌃", msg)) +
                    f'<div class="foot muted">{t("可到「公車班表」切換關注路線", "Change favorite routes on the Bus page")}</div>')
    return card(head + _grow("".join(rows)))


def _food_row(r: dict, s: dict, last: bool) -> str:
    if s.get("allday"):
        right = t("24 小時", "24 hours")
    else:
        tag = badge(t("快打烊", "Closing soon"), "#E5486F", live=True) + " " if s["key"] == "closing" else ""
        right = f'{tag}{t("至", "until")} {esc(s.get("end") or "")}'
    return (f'<div class="row" {"style=border-bottom:none" if last else ""}><span class="t">{esc(r["name"])}'
            f'<span class="muted">　{esc(r.get("building", ""))}</span></span>'
            f'<span class="e">{right}</span></div>')


def food_box(now: datetime) -> None:
    """現在營業的餐廳：每一列各自可點（跳到該餐廳），其他地方點了到「校園餐廳」。"""
    opened, _ = open_food(now)
    head = _head((icon("food") or "🍱 ") + t("現在營業的餐廳", "Open restaurants"),
                 badge(t(f"{len(opened)} 家", f"{len(opened)} open"), "#E08A1E") if opened else "")
    with st.container(key="hc_food"):
        if not opened:
            html(head + _grow(empty(icon("night") or "🌙", t("目前沒有營業中的餐廳", "Nothing is open right now"))))
        else:
            html(head)
            shown = opened[:FOOD_ROWS]
            for i, (r, s) in enumerate(shown):
                with st.container(key=f"hf_{i}"):
                    html(_food_row(r, s, i == len(shown) - 1))
                    if st.button(t(f"查看 {r['name']}", f"View {r['name']}"), key=f"go_f_{i}"):
                        goto("food", food_focus=r["id"])
            if len(opened) > FOOD_ROWS:
                html(f'<div class="foot muted">{t(f"還有 {len(opened) - FOOD_ROWS} 家營業中，到「校園餐廳」看全部", f"{len(opened) - FOOD_ROWS} more open, see Restaurants")}</div>')
        if st.button(t("前往校園餐廳", "Open Restaurants"), key="go_food"):
            goto("food")


def _linked(key: str, markup: str, slug: str, text: str, **state) -> None:
    """一個可點的格子：HTML 內容 + 蓋在上面的透明按鈕（鍵盤 Tab 也點得到）。"""
    with st.container(key=key):
        html(markup)
        if st.button(text, key=f"go_{key}"):
            goto(slug, **state)


def render() -> None:
    now = datetime.now()
    html(HOME_CSS.replace("\n", ""))  # 壓成一行：多行時 Markdown 會把 [class*=…] 的 * 當成格式，CSS 變成文字
    name = username(st.session_state.get("auth_uid"))
    hero(greeting(now, name), f"{fmt_day(now, year=True)}　{now:%H:%M}　·　{app_title()}", "home")
    mq = marquee_html(now.date())  # 學校行事曆接下來的一個事件；API 與暫存都沒有資料時不顯示
    if mq:
        _linked("hl_cal", mq, "school-calendar", t("前往學校行事曆", "Open School Calendar"))
    cls, bus, exam, food = stats_strip(now)
    to_list = {"exam_goto_list": True}  # 考試頁：展開「即將到來的清單」並捲過去
    with st.container(key="home_stats"):
        _linked("hs_cls", cls, "timetable", t("前往課表", "Open Timetable"))
        _linked("hs_bus", bus, "bus", t("前往公車班表", "Open Campus Bus"))
        _linked("hs_exam", exam, "exams", t("前往考試 / 作業清單", "Open upcoming exams & homework"), **to_list)
        _linked("hs_food", food, "food", t("前往校園餐廳", "Open Restaurants"))
    with st.container(key="home_grid"):
        _linked("hc_cls", class_summary(now), "timetable", t("前往課表", "Open Timetable"))
        _linked("hc_exam", exam_summary(now), "exams", t("前往考試 / 作業清單", "Open upcoming exams & homework"), **to_list)
        _linked("hc_bus", bus_summary(now), "bus", t("前往公車班表", "Open Campus Bus"))
        food_box(now)


FEATURE = Feature(title="首頁", icon="🏠", render=render, slug="home", default=True, ico="home",
                  title_en="Home")
