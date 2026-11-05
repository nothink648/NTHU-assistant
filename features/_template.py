"""新功能範本：複製此檔 → 改名（例如 todo.py）→ 修改內容 → 到 features/__init__.py 註冊。"""
import streamlit as st

from core.storage import load_json, save_json
from core.ui import card, hero, html
from features.base import Feature


def render() -> None:
    hero("新功能標題", "一句話說明這個功能", "🧩")
    html(card('<div class="card-head"><span class="card-title">卡片標題</span></div>在這裡寫你的功能。'))

    # 範例：讀寫資料
    # items = load_json("my_data.json", [])
    # save_json("my_data.json", items)

    # 跨重新整理保存的暫存狀態用 st.session_state
    # st.session_state.setdefault("counter", 0)


FEATURE = Feature(title="新功能", icon="🧩", render=render, slug="new-feature")
