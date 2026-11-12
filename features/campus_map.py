"""🗺️ 校園地圖：把清華 3D 校園導覽嵌入頁面，直接在介面裡操作。"""
from __future__ import annotations

import streamlit as st
import streamlit.components.v1 as components

from core.ui import hero
from features.base import Feature

MAP_URL = "https://3dcampusguide.nthu.edu.tw/?openExternalBrowser=1"
SIZES = {"小": 480, "中": 650, "大": 850}  # 視窗高度（px）


def render() -> None:
    hero("校園地圖", "清華 3D 校園導覽　·　可拖曳、縮放、點選建築物", "🗺️")

    c1, c2 = st.columns([3, 1], vertical_alignment="center")
    size = c1.radio("視窗大小", list(SIZES), index=1, horizontal=True, key="map_size")
    c2.link_button("↗ 在新分頁開啟", MAP_URL, use_container_width=True)

    components.iframe(MAP_URL, height=SIZES[size], scrolling=False)
    st.caption("地圖由國立清華大學 3D 校園導覽提供。若視窗內無法載入，請改用「在新分頁開啟」。")


FEATURE = Feature(title="校園地圖", icon="🗺️", render=render, slug="map")
