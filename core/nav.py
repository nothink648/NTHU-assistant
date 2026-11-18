"""頁面跳轉：app.py 建好 st.Page 後登記在 PAGES，其他頁面用 goto() 切換（不重新整理瀏覽器，登入狀態不會掉）。"""
from __future__ import annotations

import json

import streamlit as st
import streamlit.components.v1 as components

PAGES: dict = {}  # slug → st.Page（app.py 填入）


def goto(slug: str, **state) -> None:
    """先把要帶到目標頁的資訊放進 session_state，再切換頁面。"""
    st.session_state.update(state)
    page = PAGES.get(slug)
    if page is not None:
        st.switch_page(page)


def scroll_to(selector: str) -> None:
    """頁面畫好後把指定元素捲到畫面中間。

    用高度 0 的 components.html（同網域 iframe）操作外層頁面；元素可能晚一點才出現、
    上方內容也可能還在長高，所以找到後隔一下再對準一次。
    """
    components.html(
        "<script>/* nthu_assistant_scroll：core/ui.py 依這個字串把 iframe 藏起來，不佔版面 */"
        "(function(){const doc=window.parent.document;let n=0,hits=0;"
        f"const go=()=>{{const el=doc.querySelector({json.dumps(selector)});"
        "if(el){el.scrollIntoView({behavior:'smooth',block:'center'});if(++hits<4){setTimeout(go,400);}}"
        "else if(n++<50){setTimeout(go,100);}};setTimeout(go,200);})();</script>",
        height=0)
