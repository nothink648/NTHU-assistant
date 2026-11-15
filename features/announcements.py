"""📢 校園公告：各處室、系所網站的最新公告（資料來自 NTHU Data API 的 /announcements）。

可依語言、單位、關鍵字篩選；同一則公告出現在多個來源時只列一次。
點公告下方的單位名稱，會展開該單位的網站與聯絡方式（資料來自 /directory，見 core/directory.py）。
"""
from __future__ import annotations

import re

import streamlit as st

from core import directory, nthu_api
from core.i18n import is_en, t
from core.icons import before_css, icon, label
from core.ui import badge, card, empty, esc, hero, html
from features.base import Feature

PAGE_SIZE = 30
LANGS = {"zh-tw": "中文", "en": "English", "": "全部 / All"}

CSS = """<style>
.ann .row{align-items:flex-start}
.ann .t{flex:1;min-width:0}
.ann .t a{color:inherit!important;text-decoration:none!important;font-weight:700}
.ann .t a:hover{color:var(--acc-text)!important;text-decoration:underline!important}
.ann .src{display:block;font-weight:400;font-size:.8rem;opacity:.6;margin-top:2px}
.ann details.src{opacity:1;font-size:inherit}
.dir-hit{padding:6px 0;border-bottom:1px dashed var(--line)}
.dir-hit>summary{font-size:.92rem!important;font-weight:600!important;opacity:.9!important}
.ann .e{flex:none;padding-top:2px}
</style>"""


def _flatten(sources: list) -> list[dict]:
    """[{單位, 來源, articles: [...]}] → 每則公告一筆，依日期新到舊。"""
    seen, items = set(), []
    for s in sources or []:
        if not isinstance(s, dict):
            continue
        for a in s.get("articles") or []:
            link = str(a.get("link") or "")
            title = str(a.get("title") or "").strip()
            if not title or (link and link in seen):
                continue
            seen.add(link)
            items.append({"title": title, "link": link if link.lower().startswith(("http://", "https://")) else "",
                          "date": _date(a.get("date")), "dept": s.get("department") or "",
                          "source": s.get("title") or "", "lang": s.get("language") or ""})
    items.sort(key=lambda x: x["date"], reverse=True)  # 沒有日期的排在最後（維持原本順序）
    return items


def _date(value) -> str:
    """只接受 YYYY-MM-DD；很多來源沒有日期或格式不對，一律當成沒有日期。"""
    text = str(value or "").strip()
    return text if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text) else ""


def load_announcements() -> tuple[list[dict], str | None]:
    data, err = nthu_api.get("/announcements", ttl=1800)
    return _flatten(data or []), err


def _source_html(a: dict, finder, contacts: dict[str, str]) -> str:
    """公告來源。對得到通訊錄的單位 → 可點開的 <details>，展開後顯示聯絡方式（純 HTML，不用重新整理頁面）。"""
    src = " · ".join(x for x in (a["dept"], a["source"]) if x)
    unit = finder(a["dept"]) if a["dept"] else None
    if unit is None:
        return f'<span class="src">{esc(src)}</span>'
    if a["dept"] not in contacts:
        contacts[a["dept"]] = directory.contact_html(unit)
    rest = f' · {esc(a["source"])}' if a["source"] else ""
    return (f'<details class="dept-info src"><summary>{icon("school") or "🏢"}<span class="dept-name">{esc(a["dept"])}</span>'
            f'{rest}</summary><div class="dir-box">{contacts[a["dept"]]}</div></details>')


def _row(a: dict, finder, contacts: dict[str, str]) -> str:
    title = (f'<a href="{esc(a["link"])}" target="_blank" rel="noopener">{esc(a["title"])}</a>'
             if a["link"] else esc(a["title"]))
    when = badge(a["date"].replace("-", "/"), "#6C63FF") if a["date"] else ""
    return f'<div class="row"><span class="t">{title}{_source_html(a, finder, contacts)}</span><span class="e">{when}</span></div>'


def _unit_card(unit: dict) -> None:
    head = (f'<div class="card-head"><span class="card-title">{icon("school") or "🏢"} {esc(directory.unit_title(unit))}</span>'
            f'{badge(t("聯絡資訊", "Contact"), "#2C8BC9")}</div>')
    html(card(head + directory.contact_html(unit)))


def _directory_search(units: list[dict]) -> None:
    """查詢任何單位（含沒有發公告的單位）的聯絡方式；也可以用人員姓名或業務搜尋。"""
    html(f"<style>{before_css('.st-key-dir_search summary p', 'contact-book')}</style>")
    with st.container(key="dir_search"), st.expander(label("contact-book", t("校園通訊錄：查詢其他單位或承辦人",
                                                                             "Campus directory: find any office or staff member"))):
        q = st.text_input(t("單位、姓名或業務", "Office, name or duty (in Chinese)"), key="dir_q",
                          placeholder=t("例如：出納組、註冊組、宿舍、獎學金", "e.g. 出納組, 註冊組, 宿舍"))
        if not q.strip():
            st.caption(t(f"共 {len(units)} 個單位，資料來源：清華校園通訊錄", f"{len(units)} offices · Source: NTHU campus directory"))
            return
        found = directory.search_units(units, q)
        if not found:
            st.info(t("找不到符合的單位或人員。", "No matching office or staff."))
            return
        for u in found:
            html(f'<details class="dept-info dir-hit"><summary>{icon("school") or "🏢"}<span class="dept-name">'
                 f'{esc(directory.unit_title(u))}</span></summary><div class="dir-box">{directory.contact_html(u)}</div></details>')


def render() -> None:
    html(CSS + directory.CSS)
    hero(t("校園公告", "Announcements"), t("各處室、系所網站的最新消息　·　資料來源 NTHU Data API",
                                         "Latest news from NTHU offices and departments　·　Source: NTHU Data API"), "megaphone")
    items, err = load_announcements()
    if err:
        st.warning(err)
    if not items:
        html(card(empty(icon("mail-box") or "📭", t("目前沒有公告", "No announcements"))))
        return

    c1, c2, c3 = st.columns([1.2, 2, 2.4])
    # 英文介面：語言預設選 English（key 依介面語言分開，切換介面語言時預設值會跟著換）
    lang = c1.selectbox(t("語言", "Language"), list(LANGS), index=1 if is_en() else 0, format_func=LANGS.get,
                        key=f"ann_lang_{'en' if is_en() else 'zh'}")
    ALL = t("全部單位", "All departments")
    pool = [a for a in items if not lang or a["lang"] == lang]
    depts = sorted({a["dept"] for a in pool if a["dept"]})
    dept = c2.selectbox(t("單位", "Department"), [ALL] + depts)
    keyword = c3.text_input(t("關鍵字", "Keyword"), placeholder=t("搜尋標題，例如：獎學金、停電、選課",
                                                               "Search titles, e.g. scholarship, course"))

    units, _ = directory.load_directory()
    finder = directory.make_finder(units)
    if dept != ALL and finder(dept):
        _unit_card(finder(dept))

    kw = keyword.strip().lower()
    shown = [a for a in pool if (dept == ALL or a["dept"] == dept) and (not kw or kw in a["title"].lower())]
    key = f"ann_limit_{lang}_{dept}_{kw}"
    limit = st.session_state.get(key, PAGE_SIZE)

    head = (f'<div class="card-head"><span class="card-title">{icon("megaphone")}{esc(dept if dept != ALL else t("最新公告", "Latest announcements"))}</span>'
            f'{badge(t(f"{len(shown)} 則", f"{len(shown)} items"), "#6C63FF")}</div>')
    contacts: dict[str, str] = {}
    body = "".join(_row(a, finder, contacts) for a in shown[:limit]) if shown else empty(icon("search") or "🔍", t("找不到符合的公告", "No matching announcements"))
    html(card(head + body, "ann"))

    if len(shown) > limit:
        if st.button(t(f"顯示更多（還有 {len(shown) - limit} 則）", f"Show more ({len(shown) - limit} left)"), use_container_width=True):
            st.session_state[key] = limit + PAGE_SIZE
            st.rerun()
    if units:
        _directory_search(units)


FEATURE = Feature(title="校園公告", icon="📢", render=render, slug="announcements", ico="megaphone",
                  title_en="Announcements")
