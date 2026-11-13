"""介面語言（中文 / English）。

用法：在顯示文字的地方寫 t("中文", "English")，依目前語言回傳其中一個。
- 目前語言存在 st.session_state["lang"]；登入後也存進個人設定（data/users/<id>/settings.json 的 "lang"），
  下次登入自動套用。
- 來自外部的資料（餐廳名稱、公告標題、圖書館消息等）沒有英文版，維持原文。
"""
from __future__ import annotations

from datetime import date, datetime

import streamlit as st

LANGS = {"zh": "中文", "en": "English"}
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
    return lang() == "en"


def t(zh: str, en: str) -> str:
    """依目前語言回傳中文或英文。"""
    return en if is_en() else zh


def set_lang(code: str) -> None:
    st.session_state["lang"] = code
    if st.session_state.get("auth_uid"):
        from core.storage import load_user_json, save_user_json
        data = load_user_json(SETTINGS_FILE, {})
        data = data if isinstance(data, dict) else {}
        data["lang"] = code
        save_user_json(SETTINGS_FILE, data)


def weekday(i: int) -> str:
    return (WEEKDAYS_EN if is_en() else WEEKDAYS_ZH)[i]


def weekdays() -> list[str]:
    return WEEKDAYS_EN if is_en() else WEEKDAYS_ZH


def fmt_day(d: date | datetime, year: bool = False) -> str:
    """11/20（週五） / 11/20 (Fri)；year=True 時加上年份。"""
    head = f"{d:%Y/%m/%d}" if year else f"{d:%m/%d}"
    return f"{head} ({weekday(d.weekday())})" if is_en() else f"{head}（{weekday(d.weekday())}）"


def lang_switch() -> None:
    """側邊欄 / 登入頁的語言切換按鈕：按一下在中文與英文之間切換。"""
    target = "zh" if is_en() else "en"
    if st.button("🌐 中文" if target == "zh" else "🌐 English", key="lang_switch", use_container_width=True,
                 help=t("切換介面語言", "Switch interface language")):
        set_lang(target)
        st.rerun()
