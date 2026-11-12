"""🍱 校園餐廳：顯示各餐廳營業時間、現在是否營業，並提供「隨機選一間」轉盤。

資料來源：清華總務處經營管理組「餐廳及服務性廠商」頁面
（網頁把資料寫在 JavaScript 的 restaurantsData 變數裡），存在 data/restaurants.json。
頁面底部的「從官網更新」按鈕可以重新抓取。

營業時間是官網的自由文字（例如「週一至週五7:30-19:30,假日8:30-14:30」、
「11月每周六暫停營業」），這裡盡量解析成「現在營業中 / 休息中 / 今日公休」，
但國定假日、寒暑假等無法判斷，實際以店家公告為準。
"""
from __future__ import annotations

import ast
import random
import re
import urllib.request
import uuid
from datetime import date, datetime

import streamlit as st

from core.storage import load_json, save_json
from core.ui import badge, esc, hero, html
from features.base import Feature

DATA_FILE = "restaurants.json"
SOURCE_URL = "https://ddfm.site.nthu.edu.tw/p/404-1494-256455.php?Lang=zh-tw"
SERVICE_WORDS = ("眼鏡", "洗衣", "理髮", "打字", "書苑", "書局", "郵局", "影印")  # 非餐廳，不參加轉盤
HIDDEN_NAMES = {"straight a"}  # 不想顯示的店家（小寫）；從官網更新後也會被排除
SPIN_SECONDS = 4.2  # 轉盤轉動時間
ROW_PX = 58  # 轉盤每一列高度

CN_DAYS = "一二三四五六日"
_D = f"[{CN_DAYS}]"
TIME_RANGE = re.compile(r"(\d{1,2})[:：](\d{1,2})\s*[-~～－–:]\s*(\d{1,2})[:：](\d{1,2})")
SEG_SPLIT = re.compile(r"[,，;；]|、(?=[週周])")

STATUS_STYLE = {  # key -> 顏色
    "open": "#2E9E6A", "closing": "#E08A1E", "later": "#2C8BC9",
    "done": "#8A8A9A", "closed": "#E5486F",
}

_CSS = """
<style>
.food-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:14px;margin-top:6px}
.food-grid .card{margin:0;display:flex;flex-direction:column;gap:6px}
.food-grid .card:nth-child(n+2){animation-delay:.03s}.food-grid .card:nth-child(n+4){animation-delay:.06s}
.food-grid .card:nth-child(n+7){animation-delay:.09s}.food-grid .card:nth-child(n+10){animation-delay:.12s}
.fhead{display:flex;gap:12px;align-items:center}
.fimg{width:52px;height:52px;border-radius:12px;object-fit:cover;flex:none;background:var(--acc-soft)}
.fname{font-weight:800;font-size:1.02rem;line-height:1.25}
.farea{opacity:.6;font-size:.78rem}
.ftoday{font-weight:700;font-size:.9rem}
.fweek{font-size:.78rem;opacity:.7;line-height:1.5}
.fweek b{font-weight:600;opacity:.85;margin-right:4px}
.fnote{font-size:.78rem;color:#E5486F;opacity:.9}
.fphone{font-size:.76rem;opacity:.55}
.card.is-off{opacity:.6}
.card.is-off:hover{opacity:1}

.reel-win{position:relative;height:%(win)spx;overflow:hidden;border-radius:18px;border:1px solid var(--line);background:var(--surface);
  -webkit-mask-image:linear-gradient(transparent,#000 28%%,#000 72%%,transparent);mask-image:linear-gradient(transparent,#000 28%%,#000 72%%,transparent)}
.reel-frame{position:absolute;left:10px;right:10px;top:%(row)spx;height:%(row)spx;border-radius:14px;border:2px solid var(--acc);
  background:var(--acc-soft);box-shadow:0 0 0 4px rgba(108,99,255,.08);z-index:0}
.reel{position:relative;z-index:1;will-change:transform}
.reel-item{height:%(row)spx;display:flex;align-items:center;justify-content:center;gap:10px;font-weight:800;font-size:1.15rem}
.reel-item small{font-weight:500;font-size:.75rem;opacity:.55}
@keyframes framePulse{0%%{transform:scale(1)}40%%{transform:scale(1.04);box-shadow:0 0 0 10px rgba(108,99,255,.0),0 0 24px rgba(108,99,255,.45)}100%%{transform:scale(1)}}
@keyframes winGlow{from{color:inherit}to{color:var(--acc-text);letter-spacing:.5px}}
.reel-win.anim .reel-frame{animation:framePulse .6s ease %(dur)ss 2 both}
.reel-win.anim .win{animation:winGlow .4s ease %(dur)ss both}
.reel-win:not(.anim) .win{color:var(--acc-text)}
.spin-result{margin-top:14px}
.spin-result.anim{animation:popIn .5s var(--spring) %(dur2)ss both}
.spin-result .card{border:1.5px solid var(--acc-line);background:linear-gradient(135deg,rgba(108,99,255,.10),rgba(179,157,255,.06))}
</style>
""" % {"win": ROW_PX * 3, "row": ROW_PX, "dur": SPIN_SECONDS, "dur2": SPIN_SECONDS + 0.1}


# ---------- 資料 ----------
def load_data() -> dict:
    data = load_json(DATA_FILE, {})
    if isinstance(data, list):  # 只有清單時視為 buildings
        data = {"buildings": data}
    data.setdefault("buildings", [])
    return data


def building_label(name: str) -> str:
    """「水木生活中心(商場聯絡窗口 …)」→「水木生活中心」。"""
    return re.sub(r"\s*[（(].*?[)）]\s*", "", name).strip() or name


def all_restaurants(data: dict) -> list[dict]:
    out = []
    for b in data["buildings"]:
        for r in b.get("restaurants", []):
            if not isinstance(r, dict) or not r.get("name"):
                continue
            if r["name"].strip().casefold() in HIDDEN_NAMES:
                continue
            r = dict(r)
            r["building"] = building_label(b.get("building", ""))
            r["id"] = f'{r["building"]}|{r.get("area", "")}|{r["name"]}'
            r["is_food"] = not any(w in r["name"] for w in SERVICE_WORDS)
            out.append(r)
    return out


def fetch_from_site() -> dict:
    """從官網重新抓資料。官網把資料寫成 JS 陣列（Python 字面值格式），用 literal_eval 安全解析。"""
    req = urllib.request.Request(SOURCE_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        text = resp.read().decode("utf-8", errors="replace")
    key = "restaurantsData ="
    i = text.index(key) + len(key)
    i = text.index("[", i)
    depth, j = 0, i
    for j, ch in enumerate(text[i:], i):
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                break
    buildings = ast.literal_eval(text[i:j + 1])
    if not isinstance(buildings, list) or not buildings:
        raise ValueError("官網資料格式改變，找不到餐廳清單")
    return {"source": SOURCE_URL, "updated": datetime.now().isoformat(timespec="minutes"),
            "buildings": buildings}


# ---------- 營業時間解析 ----------
def _to_min(h: str, m: str) -> int:
    return int(h) * 60 + int(m)


def day_set(text: str) -> set[int] | None:
    """從「週一至週五」「週六、日」「假日」這類文字取出星期（0=週一）。沒有指定星期則回傳 None。"""
    t = text
    for w in ("國定假日", "寒暑假", "寒假", "暑假"):
        t = t.replace(w, "")
    days: set[int] = set()
    found = False
    if "假日" in t:
        days |= {5, 6}
        found = True
        t = t.replace("假日", "")
    for a, b in re.findall(rf"[週周]({_D})\s*[至到~～\-－]\s*[週周]?({_D})", t):
        i, k = CN_DAYS.index(a), CN_DAYS.index(b)
        days |= set(range(i, k + 1)) if i <= k else set(range(i, 7)) | set(range(0, k + 1))
        found = True
    t = re.sub(rf"[週周]{_D}\s*[至到~～\-－]\s*[週周]?{_D}", "", t)
    for grp in re.findall(rf"[週周]({_D}(?:\s*[、及和,，]\s*{_D})*)", t):
        days |= {CN_DAYS.index(c) for c in grp if c in CN_DAYS}
        found = True
    return days if found else None


def day_field(weekday: int) -> str:
    return "weekday" if weekday < 5 else ("saturday" if weekday == 5 else "sunday")


def parse_hours(text: str, weekday: int) -> tuple[list[tuple[int, int]], bool]:
    """回傳 (今天的營業區間[(開始分, 結束分)], 今天是否明寫公休)。"""
    text = text or ""
    if "24小時" in text or "24 小時" in text:
        return [(0, 1440)], False
    ranges, closed, last_days = [], False, None
    for seg in SEG_SPLIT.split(text):
        if not seg.strip():
            continue
        first_digit = re.search(r"\d", seg)
        prefix = seg[:first_digit.start()] if first_digit else seg
        days = day_set(prefix)
        if days is None:
            days = last_days  # 沒寫星期 → 沿用前一段（例如「週一至週五11:00-13:00,16:30-19:00」）
        else:
            last_days = days
        applies = days is None or weekday in days
        if not applies:
            continue
        if re.search(r"暫停|公休|休息", seg) and not TIME_RANGE.search(seg):
            closed = True
            continue
        for h1, m1, h2, m2 in TIME_RANGE.findall(seg):
            s, e = _to_min(h1, m1), _to_min(h2, m2)
            if e <= s:
                e += 1440
            ranges.append((s, e))
    return sorted(ranges), closed


def note_rules(note: str, today: date) -> tuple[bool, str | None, bool]:
    """解析備註裡的公休規則。回傳 (今天整天公休, 只停 'lunch'/'dinner', 有無法判斷的規則)。"""
    closed, meal, irregular = False, None, False
    for sent in re.split(r"[。.]", note or ""):
        if not re.search(r"暫停營業|公休|休息", sent):
            continue
        # 特定日期：11/14、11/23-11/28、11/13晚餐
        for m in re.finditer(r"(\d{1,2})/(\d{1,2})(?:\s*[-~～至]\s*(?:(\d{1,2})/)?(\d{1,2}))?\s*(午餐|晚餐)?", sent):
            m1, d1 = int(m[1]), int(m[2])
            m2 = int(m[3]) if m[3] else m1
            d2 = int(m[4]) if m[4] else d1
            try:
                start, end = date(today.year, m1, d1), date(today.year, m2, d2)
            except ValueError:
                continue
            if start <= today <= end:
                if m[5]:
                    meal = "lunch" if m[5] == "午餐" else "dinner"
                else:
                    closed = True
        sent = re.sub(r"\d{1,2}/\d{1,2}(?:\s*[-~～至]\s*(?:\d{1,2}/)?\d{1,2})?\s*(午餐|晚餐)?", "", sent)
        if re.search(r"第[\d、,，\s]+[週周]", sent):  # 第2、4週… 無法可靠判斷
            irregular = True
            continue
        mm = re.match(r"\s*(\d{1,2})月", sent)
        if mm:
            if int(mm[1]) != today.month:
                continue
            sent = sent[mm.end():]
        days = day_set(sent)
        if days and today.weekday() in days:
            closed = True
    return closed, meal, irregular


def fmt_min(m: int) -> str:
    if m == 1440:
        return "24:00"
    m %= 1440  # 跨夜的結束時間
    return f"{m // 60:02d}:{m % 60:02d}"


def fmt_ranges(ranges: list[tuple[int, int]]) -> str:
    if ranges == [(0, 1440)]:
        return "24 小時"
    return "、".join(f"{fmt_min(s)}–{fmt_min(e)}" for s, e in ranges)


def status(r: dict, now: datetime) -> dict:
    """計算這間店此刻的狀態。"""
    wd = now.weekday()
    sched = r.get("schedule") or {}
    ranges, closed = parse_hours(sched.get(day_field(wd), ""), wd)
    n_closed, meal, irregular = note_rules(r.get("note", ""), now.date())
    if meal == "lunch":
        ranges = [x for x in ranges if x[0] >= 15 * 60]
    elif meal == "dinner":
        ranges = [x for x in ranges if x[0] < 15 * 60]
    cur = now.hour * 60 + now.minute
    if closed or n_closed:
        key, label = "closed", "今日公休"
    elif not ranges:
        key, label = "closed", "今日未營業"
    else:
        live = next((x for x in ranges if x[0] <= cur < x[1]), None)
        upcoming = next((x for x in ranges if x[0] > cur), None)
        if live and live == (0, 1440):
            key, label = "open", "24 小時營業"
        elif live:
            left = live[1] - cur
            key = "closing" if left <= 30 else "open"
            label = f"即將打烊 · {fmt_min(live[1])}" if key == "closing" else f"營業中 · 至 {fmt_min(live[1])}"
        elif upcoming:
            key, label = "later", f"{fmt_min(upcoming[0])} 開始營業"
        else:
            key, label = "done", "今日已打烊"
    today = "今日公休" if key == "closed" else fmt_ranges(ranges)
    return {"key": key, "label": label, "today": today, "irregular": irregular,
            "is_open": key in ("open", "closing")}


def week_lines(r: dict) -> str:
    s = r.get("schedule") or {}
    wk, sa, su = s.get("weekday", ""), s.get("saturday", ""), s.get("sunday", "")
    if wk == sa == su:
        label = "時間" if re.search(r"[週周]|假日", wk) else "每日"  # 文字本身已寫星期就不加「每日」
        return f"<b>{label}</b>{esc(wk)}"
    return f"<b>平日</b>{esc(wk)}<br><b>週六</b>{esc(sa)}<br><b>週日</b>{esc(su)}"


# ---------- 卡片 ----------
def restaurant_card(r: dict, st_: dict, extra_cls: str = "") -> str:
    img = f'<img class="fimg" src="{esc(r["image"])}" alt="" loading="lazy">' if r.get("image") else '<div class="fimg"></div>'
    area = esc(r.get("area") or r.get("building", ""))
    note = f'<div class="fnote">⚠️ {esc(r["note"])}</div>' if r.get("note") else ""
    phone = f'<div class="fphone">☎ {esc(r["phone"])}</div>' if r.get("phone") else ""
    off = "" if st_["is_open"] else "is-off"
    return (f'<div class="card {off} {extra_cls}"><div class="fhead">{img}<div>'
            f'<div class="fname">{esc(r["name"])}</div><div class="farea">📍 {area}</div></div></div>'
            f'<div>{badge(st_["label"], STATUS_STYLE[st_["key"]], live=st_["is_open"])}</div>'
            f'<div class="ftoday">今日　{esc(st_["today"])}</div>'
            f'<div class="fweek">{week_lines(r)}</div>{note}{phone}</div>')


# ---------- 轉盤 ----------
def _spin(cands: list[dict]) -> None:
    if not cands:
        return
    winner = random.choice(cands)
    reel = [random.choice(cands) for _ in range(30)]
    for k in range(1, len(reel)):  # 盡量不要連續出現同一間
        if len(cands) > 1 and reel[k]["id"] == reel[k - 1]["id"]:
            reel[k] = random.choice([c for c in cands if c["id"] != reel[k - 1]["id"]])
    tail = [random.choice(cands) for _ in range(2)]
    st.session_state.food_spin = {"nonce": uuid.uuid4().hex[:8], "reel": reel + [winner] + tail,
                                  "win_idx": len(reel), "winner_id": winner["id"]}
    st.session_state.food_anim = True  # 只有按下按鈕的那一次播放動畫


def reel_html(spin: dict, animate: bool) -> str:
    items = "".join(
        f'<div class="reel-item{" win" if i == spin["win_idx"] else ""}">{esc(r["name"])}'
        f'<small>{esc(r.get("area") or r.get("building", ""))}</small></div>'
        for i, r in enumerate(spin["reel"]))
    offset = (spin["win_idx"] - 1) * ROW_PX  # 讓得獎者停在中間那一列
    style, anim_css = f"transform:translateY(-{offset}px);", ""
    if animate:
        name = f"reel_{spin['nonce']}"  # 每次不同名稱，保證動畫重新播放
        anim_css = (f"<style>@keyframes {name}{{0%{{transform:translateY(0);filter:blur(0)}}"
                    f"10%{{filter:blur(1.6px)}}75%{{filter:blur(.5px)}}"
                    f"100%{{transform:translateY(-{offset}px);filter:blur(0)}}}}</style>")
        style += f"animation:{name} {SPIN_SECONDS}s cubic-bezier(.12,.8,.16,1) both;"
    return (f'{anim_css}<div class="reel-win{" anim" if animate else ""}"><div class="reel-frame"></div>'
            f'<div class="reel" style="{style}">{items}</div></div>')


def _roulette(rests: list[dict], stats: dict[str, dict], buildings: list[str]) -> None:
    ss = st.session_state
    with st.container(border=True):
        st.markdown("**🎲 今天吃什麼？**　讓轉盤幫你決定")
        c1, c2 = st.columns([3, 2], vertical_alignment="bottom")
        picked = c1.multiselect("抽選範圍", buildings, default=buildings, key="food_areas",
                                placeholder="全部區域")
        only_open = c2.toggle("只抽現在營業中的", value=True, key="food_only_open")
        areas = set(picked or buildings)
        cands = [r for r in rests if r["is_food"] and r["building"] in areas
                 and (not only_open or stats[r["id"]]["is_open"])]
        st.button(f"🎲 隨機選一間（{len(cands)} 間候選）", type="primary", on_click=_spin, args=(cands,),
                  disabled=not cands, key="food_spin_btn")
        if not cands:
            st.caption("目前沒有符合條件的餐廳，試著關掉「只抽現在營業中的」或放寬範圍。")

        spin = ss.get("food_spin")
        if spin:
            animate = ss.pop("food_anim", False)
            html(reel_html(spin, animate))
            winner = next((r for r in rests if r["id"] == spin["winner_id"]), None)
            if winner:
                html(f'<div class="spin-result{" anim" if animate else ""}">'
                     f'{restaurant_card(winner, stats[winner["id"]])}</div>')


# ---------- 頁面 ----------
def render() -> None:
    html(_CSS)
    hero("校園餐廳", "營業時間一覽　·　選擇困難就交給轉盤", "🍱")
    if "food_flash" in st.session_state:
        st.toast(st.session_state.pop("food_flash"), icon="✅")
    data = load_data()
    rests = all_restaurants(data)
    if not rests:
        st.warning("還沒有餐廳資料，請按下方「從官網更新」。")
    now = datetime.now()
    stats = {r["id"]: status(r, now) for r in rests}
    buildings = list(dict.fromkeys(r["building"] for r in rests))

    if rests:
        _roulette(rests, stats, buildings)

        n_open = sum(stats[r["id"]]["is_open"] for r in rests if r["is_food"])
        n_food = sum(r["is_food"] for r in rests)
        st.markdown(f"#### 🕘 營業時間　{badge(f'現在營業 {n_open} / {n_food} 間餐廳', '#2E9E6A', live=n_open > 0)}",
                    unsafe_allow_html=True)
        f1, f2, f3 = st.columns([3, 1.3, 1.3], vertical_alignment="bottom")
        q = f1.text_input("搜尋", placeholder="店名或位置，例如：咖哩、風雲2樓", key="food_q",
                          label_visibility="collapsed")
        open_only = f2.toggle("只看營業中", key="food_open_only")
        show_service = f3.toggle("顯示服務類店家", key="food_service")

        def match(r: dict) -> bool:
            if not show_service and not r["is_food"]:
                return False
            if open_only and not stats[r["id"]]["is_open"]:
                return False
            if q.strip():
                hay = f'{r["name"]} {r.get("area", "")} {r["building"]}'.casefold()
                return all(w in hay for w in q.casefold().split())
            return True

        order = {"open": 0, "closing": 1, "later": 2, "done": 3, "closed": 4}
        tabs = st.tabs(["全部"] + buildings)
        for tab, bname in zip(tabs, [None] + buildings):
            with tab:
                items = [r for r in rests if (bname is None or r["building"] == bname) and match(r)]
                items.sort(key=lambda r: order[stats[r["id"]]["key"]])
                if not items:
                    st.info("沒有符合條件的店家。")
                    continue
                html('<div class="food-grid">' + "".join(restaurant_card(r, stats[r["id"]]) for r in items) + "</div>")

    with st.expander("ℹ️ 資料來源與更新"):
        updated = data.get("updated", "")
        st.markdown(f"資料來自 [清華總務處經營管理組 — 餐廳及服務性廠商]({SOURCE_URL})"
                    + (f"，最後更新：{updated.replace('T', ' ')}" if updated else ""))
        st.caption("營業狀態是從官網文字推算的；國定假日、寒暑假與臨時公休請以店家公告為準。")
        if st.button("🔄 從官網更新", key="food_refresh"):
            try:
                with st.spinner("正在抓取官網資料…"):
                    new = fetch_from_site()
                save_json(DATA_FILE, new)
                st.session_state.pop("food_spin", None)
                n = sum(len(b.get("restaurants", [])) for b in new["buildings"])
                st.session_state.food_flash = f"已從官網更新 {n} 間店家"
                st.rerun()
            except Exception as e:  # 網路錯誤、官網改版等
                st.error(f"更新失敗：{e}")


FEATURE = Feature(title="校園餐廳", icon="🍱", render=render, slug="food")
