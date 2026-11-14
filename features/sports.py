"""🏀 體育場館開放時間：體育館、重訓室、游泳池、網球場……各場館每學期的開放時間表。

資料來源：清華體育室「開放時間」頁面（https://nthupeo.site.nthu.edu.tw/p/412-1265-14409.php）。
那一頁是一張表格，每個場館有「上學期 / 寒假 / 下學期 / 暑假」四個 PDF 連結；PDF 是排版好的週課表，
格子合併很多，硬轉成文字容易出錯，所以這裡把 PDF 轉成圖片直接顯示，並從 PDF 文字讀出適用日期，
自動選出「今天適用」的那一份。

- 表格（PDF 連結）每天重新抓一次；PDF 依網址存在 data/sports_cache/（網址不變 = 內容不變），
  官網連不上時仍可顯示看過的時間表。
- 需要 PyMuPDF（pip install pymupdf）把 PDF 轉成圖片；沒裝時只顯示 PDF 連結。
"""
from __future__ import annotations

import hashlib
import html as _html
import re
import urllib.parse
import urllib.request
from datetime import date

import streamlit as st

from config import DATA_DIR
from core.i18n import is_en, t, tr
from core.icons import before_css, icon, label
from core.ui import badge, card, esc, hero, html
from features.base import Feature

SOURCE_URL = "https://nthupeo.site.nthu.edu.tw/p/412-1265-14409.php"
BOOKING_URL = "https://peo178.et.nthu.edu.tw/login"  # 體育室場地預約系統
CACHE_DIR = DATA_DIR / "sports_cache"
HEADERS = {"User-Agent": "Mozilla/5.0 (campus-assistant)"}
TERMS = ["上學期", "寒假", "下學期", "暑假"]
TERM_EN = {"上學期": "Fall semester", "寒假": "Winter break", "下學期": "Spring semester", "暑假": "Summer break"}
VENUE_EN = {
    "體育館": "Gymnasium", "體能訓練室(重訓室)": "Fitness Center (Weight Room)", "體適能教室": "Physical Fitness Room",
    "舞蹈教室": "Dance Studio", "柔道教室": "Judo Room", "桌球館": "Table Tennis Hall", "游泳池": "Swimming Pool",
    "網球場": "Tennis Courts", "棒球場": "Baseball Field", "操場": "Track & Field", "足球場": "Soccer Field",
    "室外籃球場": "Outdoor Basketball Courts", "室外排球場": "Outdoor Volleyball Courts", "羽球場": "Badminton Courts",
    "韻律教室": "Aerobics Studio", "瑜珈教室": "Yoga Studio", "南大校區場館": "Nanda Campus Facilities",
    "校友體育館": "Alumni Gymnasium",
}
CSS = """<style>
.sp-sheet{border-radius:14px;overflow:hidden;border:1px solid var(--line);background:#fff;animation:fadeUp .4s var(--ease) both}
.sp-sheet img{display:block;width:100%;height:auto}
.sp-notes{margin:0;padding-left:1.3em;font-size:.86rem;line-height:1.6}
.sp-notes li{margin:2px 0}
.sp-rules{margin:0;padding-left:1.2em;font-size:.88rem;line-height:1.7}
</style>"""


def venue_name(name: str) -> str:
    return tr(VENUE_EN[name]) if is_en() and name in VENUE_EN else name


def term_name(term: str) -> str:
    return tr(TERM_EN[term]) if is_en() and term in TERM_EN else term


# ---------- 抓資料 ----------
def _download(url: str, timeout: int = 20) -> bytes:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


@st.cache_data(ttl=86400, show_spinner=False)
def load_venues() -> tuple[list[dict], str | None]:
    """[{name, place, links: {學期: PDF 網址}}]；第二個值是錯誤訊息（成功時為 None）。"""
    cache = CACHE_DIR / "page.html"
    err = None
    try:
        text = _download(SOURCE_URL).decode("utf-8", errors="replace")
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache.write_text(text, encoding="utf-8")
    except Exception:  # 官網連不上 → 用上次存的那一份
        if not cache.exists():
            return [], t("暫時連不上體育室網站，請稍後再試", "The PE Office website is unreachable, please try again later")
        text = cache.read_text(encoding="utf-8")
        err = t("暫時連不上體育室網站，目前顯示先前的資料", "The PE Office website is unreachable; showing earlier data")

    start = text.find("開放時間一覽表")
    table = text[start:text.find("</table>", start)] if start >= 0 else ""
    venues = []
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", table, re.S):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)
        if len(cells) < 5:
            continue
        clean = [re.sub(r"\s+", "", _html.unescape(re.sub(r"<[^>]+>", "", c))) for c in cells]
        links = {}
        for cell, term in zip(cells[1:5], clean[1:5]):
            m = re.search(r'href="([^"]+\.pdf)"', cell, re.I)
            if m and term in TERMS:
                links[term] = urllib.parse.urljoin(SOURCE_URL, _html.unescape(m.group(1)))
        if clean[0] and links:
            venues.append({"name": clean[0], "place": clean[6] if len(clean) > 6 else "", "links": links})
    if not venues and err is None:
        err = t("體育室網頁格式改變，讀不到場館清單", "The PE Office page layout changed; no facilities found")
    return venues, err


def _pdf_bytes(url: str) -> bytes | None:
    """PDF 依網址存在硬碟；同一個網址只下載一次。"""
    path = CACHE_DIR / (hashlib.md5(url.encode("utf-8")).hexdigest() + ".pdf")
    if path.exists():
        return path.read_bytes()
    try:
        data = _download(url, timeout=30)
    except Exception:
        return None
    if not data.startswith(b"%PDF"):
        return None
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return data


def _fitz():
    try:
        import pymupdf  # PyMuPDF 1.24+
        return pymupdf
    except ImportError:
        try:
            import fitz  # 舊版 PyMuPDF
            return fitz
        except ImportError:
            return None


@st.cache_data(max_entries=200, show_spinner=False)
def sheet_info(url: str) -> dict | None:
    """讀 PDF：{title, start, end, notes, png}。png 是第一頁的圖片（沒有 PyMuPDF 時為 None）。"""
    data = _pdf_bytes(url)
    if data is None:
        return None
    lib = _fitz()
    if lib is None:
        return {"title": "", "start": None, "end": None, "notes": [], "png": None}
    doc = lib.open(stream=data, filetype="pdf")
    page = doc[0]
    text = page.get_text()
    title = next((ln.strip() for ln in text.splitlines() if "開放時間" in ln and "「" in ln), "")
    start, end = _date_range(text)
    notes = [re.sub(r"\s+", " ", m.group(2)).strip() for m in
             re.finditer(r"^\s*(\d{1,2})\s*[.．、]\s*(\S.*(?:\n {2,}\S.*)*)", text, re.M)]
    png = page.get_pixmap(matrix=lib.Matrix(2, 2), alpha=False).tobytes("png")
    return {"title": title, "start": start, "end": end, "notes": notes, "png": png}


def _date_range(text: str) -> tuple[date | None, date | None]:
    """「115 年 9 月 07 日（一） ~ 115 年 12 月 28 日（日）」→ (2026-09-07, 2026-12-28)。"""
    m = re.search(r"(\d{3})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日[^~～\n]*[~～至]\s*(?:(\d{3})\s*年\s*)?(\d{1,2})\s*月\s*(\d{1,2})\s*日",
                  text)
    if not m:
        return None, None
    y1 = int(m.group(1)) + 1911
    y2 = int(m.group(4)) + 1911 if m.group(4) else y1
    try:
        start, end = date(y1, int(m.group(2)), int(m.group(3))), date(y2, int(m.group(5)), int(m.group(6)))
    except ValueError:
        return None, None
    if end < start and not m.group(4):  # 跨年但沒寫年份
        end = end.replace(year=end.year + 1)
    return start, end


def guess_term(links: dict, today: date) -> str:
    """今天適用的時間表：PDF 上的日期範圍包含今天的那一份；都沒有就依月份猜。"""
    for term in TERMS:
        if term in links:
            info = sheet_info(links[term])
            if info and info["start"] and info["end"] and info["start"] <= today <= info["end"]:
                return term
    m = today.month
    guess = "上學期" if m in (9, 10, 11, 12) else "寒假" if m in (1,) else "下學期" if m in (2, 3, 4, 5, 6) else "暑假"
    return guess if guess in links else next(iter(links))


# ---------- 頁面 ----------
def _rules() -> None:
    items = [t("國定假日、天災（地方政府宣布停班）、校內活動或工程期間閉館，各場館另行公告。",
               "Closed on national holidays, typhoon/disaster days and during campus events or construction (announced per facility)."),
             t("上課時間不開放；校隊訓練時段也不開放。", "Not open during PE classes or varsity team practice."),
             t("詳細規定、收費與票卡請見各時間表下方的備註或洽體育室：(03)571-5131 #34677。",
               "See the notes under each timetable for rules, fees and passes, or call the PE Office: (03)571-5131 ext. 34677.")]
    html(card(f'<div class="card-head"><span class="card-title">{icon("event") or "🗓️"} {t("開放須知", "Good to know")}</span></div>'
              '<ul class="sp-rules">' + "".join(f"<li>{esc(i)}</li>" for i in items) + "</ul>"))


def _choose(label: str, options: list[str], key: str, default: str, fmt) -> str:
    if st.session_state.get(key) not in options:
        st.session_state[key] = default
    if hasattr(st, "pills"):
        picked = st.pills(label, options, key=key, format_func=fmt, selection_mode="single")
    else:
        picked = st.selectbox(label, options, key=key, format_func=fmt)
    return picked or default


def render() -> None:
    html(CSS)
    hero(t("體育場館", "Sports Facilities"),
         t("各場館開放時間　·　資料來源：清華體育室", "Opening hours of campus sports facilities　·　Source: NTHU PE Office"), "sport")
    with st.spinner(t("正在讀取體育室網站…", "Loading from the PE Office website…")):
        venues, err = load_venues()
    if err:
        st.warning(err)
    if not venues:
        st.link_button(t("前往體育室開放時間頁面", "Open the PE Office hours page"), SOURCE_URL)
        return

    with st.container(key="sp_booking"):
        b1, b2 = st.columns([3, 1.3], vertical_alignment="center")
        b1.caption(t("網球場、羽球場等場地可線上預約（需登入體育室場地預約系統）。",
                     "Courts such as tennis and badminton can be booked online (sign in to the PE Office booking system)."))
        b2.link_button(label("event", t("預約場地", "Book a court")), BOOKING_URL, type="primary", use_container_width=True)
    html(f"<style>{before_css('.st-key-sp_booking a p', 'event')}</style>")
    _rules()
    by_name = {v["name"]: v for v in venues}
    names = list(by_name)

    def venue_label(n: str) -> str:
        place = by_name[n]["place"]
        return venue_name(n) + (f"（{venue_name(place)}）" if place and not is_en() else f" ({venue_name(place)})" if place else "")

    name = _choose(t("場館", "Facility"), names, "sp_venue", names[0], venue_label)
    v = by_name[name]
    today = date.today()
    with st.spinner(t("正在讀取時間表…", "Loading the timetable…")):
        current = guess_term(v["links"], today)
    terms = [x for x in TERMS if x in v["links"]]
    term = _choose(t("時期", "Period"), terms, f"sp_term_{name}", current,
                   lambda x: term_name(x) + (t("（目前）", " (now)") if x == current else ""))

    url = v["links"][term]
    with st.spinner(t("正在讀取時間表…", "Loading the timetable…")):
        info = sheet_info(url)
    head_title = (info or {}).get("title") or f"{venue_name(name)} · {term_name(term)}"
    rng = ""
    if info and info["start"] and info["end"]:
        rng = f"{info['start']:%Y/%m/%d} – {info['end']:%Y/%m/%d}"
    tag = badge(t("今天適用", "In effect today"), "#2E9E6A", live=True) if (
        info and info["start"] and info["end"] and info["start"] <= today <= info["end"]) else ""

    c1, c2 = st.columns([4, 1.3], vertical_alignment="center")
    c1.markdown(f"#### {icon('sport') or '🏀'} {esc(head_title)}　{tag}", unsafe_allow_html=True)
    c2.link_button(t("開啟 PDF", "Open PDF"), url, use_container_width=True)
    if rng:
        st.caption(t(f"適用期間：{rng}", f"Valid: {rng}"))

    if info is None:
        st.info(t("暫時下載不到這份時間表，請直接開啟 PDF。", "Couldn't download this timetable; please open the PDF."))
    elif info["png"] is None:
        st.info(t("伺服器沒有安裝 PyMuPDF，無法在頁面上顯示時間表，請直接開啟 PDF。",
                  "PyMuPDF is not installed on the server, so the timetable can't be shown here; please open the PDF."))
    else:
        try:
            st.image(info["png"], width="stretch")
        except Exception:  # 舊版 Streamlit 沒有 width="stretch"
            st.image(info["png"], use_container_width=True)
        st.caption(t("時間表為體育室公告的原始內容；「Class time」為上課、「School team practice」為校隊訓練，這些時段不開放。",
                     "This is the PE Office's original timetable. “Class time” and “School team practice” slots are not open to the public."))
    if info and info["notes"]:
        with st.expander(t(f"備註與使用規定（{len(info['notes'])} 條）", f"Notes & rules ({len(info['notes'])})")):
            html('<ol class="sp-notes">' + "".join(f"<li>{esc(n)}</li>" for n in info["notes"]) + "</ol>")
    st.caption(t(f"資料來源：[清華體育室 — 開放時間]({SOURCE_URL})", f"Source: [NTHU PE Office — Opening hours]({SOURCE_URL})"))


FEATURE = Feature(title="體育場館", icon="🏀", render=render, slug="sports", ico="sport", title_en="Sports Facilities")
