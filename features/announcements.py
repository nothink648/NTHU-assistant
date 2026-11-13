"""📢 校園公告：各處室、系所網站的最新公告（資料來自 NTHU Data API 的 /announcements）。

可依語言、單位、關鍵字篩選；同一則公告出現在多個來源時只列一次。
"""
from __future__ import annotations

import re

import streamlit as st

from core import nthu_api
from core.i18n import is_en, t
from core.icons import icon
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


def _row(a: dict) -> str:
    title = (f'<a href="{esc(a["link"])}" target="_blank" rel="noopener">{esc(a["title"])}</a>'
             if a["link"] else esc(a["title"]))
    src = " · ".join(x for x in (a["dept"], a["source"]) if x)
    when = badge(a["date"].replace("-", "/"), "#6C63FF") if a["date"] else ""
    return f'<div class="row"><span class="t">{title}<span class="src">{esc(src)}</span></span><span class="e">{when}</span></div>'


def render() -> None:
    html(CSS)
    hero(t("校園公告", "Announcements"), t("各處室、系所網站的最新消息　·　資料來源 NTHU Data API",
                                         "Latest news from NTHU offices and departments　·　Source: NTHU Data API"), "megaphone")
    items, err = load_announcements()
    if err:
        st.warning(err)
    if not items:
        html(card(empty("📭", t("目前沒有公告", "No announcements"))))
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

    kw = keyword.strip().lower()
    shown = [a for a in pool if (dept == ALL or a["dept"] == dept) and (not kw or kw in a["title"].lower())]
    key = f"ann_limit_{lang}_{dept}_{kw}"
    limit = st.session_state.get(key, PAGE_SIZE)

    head = (f'<div class="card-head"><span class="card-title">{icon("megaphone")}{esc(dept if dept != ALL else t("最新公告", "Latest announcements"))}</span>'
            f'{badge(t(f"{len(shown)} 則", f"{len(shown)} items"), "#6C63FF")}</div>')
    body = "".join(_row(a) for a in shown[:limit]) if shown else empty("🔍", t("找不到符合的公告", "No matching announcements"))
    html(card(head + body, "ann"))

    if len(shown) > limit:
        if st.button(t(f"顯示更多（還有 {len(shown) - limit} 則）", f"Show more ({len(shown) - limit} left)"), use_container_width=True):
            st.session_state[key] = limit + PAGE_SIZE
            st.rerun()


FEATURE = Feature(title="校園公告", icon="📢", render=render, slug="announcements", ico="megaphone",
                  title_en="Announcements")
