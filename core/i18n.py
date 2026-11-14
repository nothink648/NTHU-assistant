"""介面語言（中文 / English / Bahasa Indonesia / Tiếng Việt）。

用法：在顯示文字的地方寫 t("中文", "English")，依目前語言回傳其中一個。
- 印尼文、越南文不用改程式：t() 會拿英文那一句去 core/locales/<語言>.json 查翻譯
  （"strings" 是整句對照；"templates" 給 f-string 用，{0}、{1} 代表變數），查不到就顯示英文。
  新增或修改英文句子後，記得也更新這兩個檔案。
- is_en() 代表「不是中文介面」：外部資料只有中文 / 英文兩種時（行事曆標題、站名、場館名稱…），
  印尼文、越南文介面也使用英文版。
- 目前語言存在 st.session_state["lang"]；登入後也存進個人設定（data/users/<id>/settings.json 的 "lang"），
  下次登入自動套用。
- 來自外部的資料（餐廳名稱、公告標題、圖書館消息等）沒有英文版，維持原文。
"""
from __future__ import annotations

import json
import re
from datetime import date, datetime
from functools import lru_cache
from pathlib import Path

import streamlit as st

LANGS = {"zh": "中文", "en": "English", "id": "Bahasa Indonesia", "vi": "Tiếng Việt"}
LOCALE_DIR = Path(__file__).resolve().parent / "locales"
WEEKDAYS = {"id": ["Sen", "Sel", "Rab", "Kam", "Jum", "Sab", "Min"], "vi": ["T2", "T3", "T4", "T5", "T6", "T7", "CN"]}
MONTHS = {"en": ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
                 "November", "December"],
          "id": ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus", "September", "Oktober",
                 "November", "Desember"]}
SETTINGS_FILE = "settings.json"
WEEKDAYS_ZH = ["週一", "週二", "週三", "週四", "週五", "週六", "週日"]
WEEKDAYS_EN = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def lang() -> str:
    if "lang" not in st.session_state:  # 第一次：讀登入者的個人設定
        saved = None
        if st.session_state.get("auth_uid"):
            from core.storage import load_user_json  # 延遲 import，避免循環
            data = load_user_json(SETTINGS_FILE, {})
            saved = data.get("lang") if isinstance(data, dict) else None
        st.session_state["lang"] = saved if saved in LANGS else "zh"
    return st.session_state["lang"]


def is_en() -> bool:
    """不是中文介面（英文、印尼文、越南文都算）；外部資料改用英文版。"""
    return lang() != "zh"


@lru_cache(maxsize=None)
def _locale(code: str) -> tuple[dict, list]:
    try:
        data = json.loads((LOCALE_DIR / f"{code}.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}, []
    templates = []
    for src, dst in (data.get("templates") or {}).items():
        parts = re.split(r"(\{\d+\})", src)
        pattern = "".join("(.+?)" if re.fullmatch(r"\{\d+\}", p) else re.escape(p.replace("{{", "{").replace("}}", "}"))
                          for p in parts)
        order = [int(p[1:-1]) for p in parts if re.fullmatch(r"\{\d+\}", p)]
        literal = len(re.sub(r"\{\d+\}", "", src))
        templates.append((literal, re.compile(f"^{pattern}$", re.S), order, dst))
    templates.sort(key=lambda x: -x[0])  # 固定文字越多的越優先，避免被太短的樣板搶走
    return data.get("strings") or {}, templates


@lru_cache(maxsize=4096)
def _translate(code: str, en: str) -> str:
    strings, templates = _locale(code)
    if en in strings:
        return strings[en]
    for _, rx, order, dst in templates:
        m = rx.match(en)
        if m:
            values = dict(zip(order, m.groups()))
            return re.sub(r"\{(\d+)\}", lambda g: values.get(int(g.group(1)), g.group(0)), dst)
    return en


def tr(en: str) -> str:
    """把英文句子翻成目前的介面語言（印尼文 / 越南文查對照表；其他語言原樣回傳）。"""
    code = lang()
    return _translate(code, en) if code not in ("zh", "en") and en else en


def t(zh: str, en: str) -> str:
    """依目前語言回傳中文、英文，或由英文翻成的印尼文 / 越南文。"""
    return zh if lang() == "zh" else tr(en)


def set_lang(code: str) -> None:
    st.session_state["lang"] = code
    if st.session_state.get("auth_uid"):
        from core.storage import load_user_json, save_user_json
        data = load_user_json(SETTINGS_FILE, {})
        data = data if isinstance(data, dict) else {}
        data["lang"] = code
        save_user_json(SETTINGS_FILE, data)


def weekdays() -> list[str]:
    code = lang()
    return WEEKDAYS_ZH if code == "zh" else WEEKDAYS.get(code, WEEKDAYS_EN)


def weekday(i: int) -> str:
    return weekdays()[i]


def month_year(y: int, m: int) -> str:
    """2026 年 11 月 / November 2026 / November 2026 / Tháng 11 2026。"""
    code = lang()
    if code == "zh":
        return f"{y} 年 {m} 月"
    if code == "vi":
        return f"Tháng {m} {y}"
    return f"{MONTHS.get(code, MONTHS['en'])[m - 1]} {y}"


def fmt_day(d: date | datetime, year: bool = False) -> str:
    """11/20（週五） / 11/20 (Fri)；year=True 時加上年份。"""
    head = f"{d:%Y/%m/%d}" if year else f"{d:%m/%d}"
    return f"{head} ({weekday(d.weekday())})" if is_en() else f"{head}（{weekday(d.weekday())}）"


def _on_lang_select(key: str) -> None:
    set_lang(st.session_state[key])


def lang_select(key: str = "lang_select", label_visibility: str = "collapsed") -> None:
    """語言下拉選單（登入頁、帳號設定共用）；選了立刻切換並記住。"""
    st.session_state[key] = lang()  # 與目前語言同步
    st.selectbox(t("介面語言", "Language"), list(LANGS), format_func=LANGS.get, key=key,
                 on_change=_on_lang_select, args=(key,), label_visibility=label_visibility,
                 help=t("切換介面語言", "Switch interface language"))
