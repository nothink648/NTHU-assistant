"""頁面切換：首頁速覽卡片、頂部「回首頁」按鈕都靠這裡在同一個 session 內換頁（不重新載入網頁、語言等設定不會掉）。

app.py 每次執行都會呼叫 register() 登記本次的頁面物件；其他地方用 go("slug") 切換。
"""
from __future__ import annotations

import streamlit as st

from core import icons
from core.i18n import t

_KEY = "_nav_pages"

# 頂部固定的「回首頁」按鈕：跟首頁紫色橫幅的 hero-icon 同一套圖示與配色（紫色漸層圓角方塊 + 白色小房子）。
# 位置在側邊欄展開鈕（>>）右邊；側邊欄打開時：寬螢幕移到側邊欄右側，窄螢幕（側邊欄蓋住畫面）先隱藏。
_FAB_CSS = """
:is([data-testid="stLayoutWrapper"],[data-testid="stElementContainer"]):has(>.st-key-home_fab){display:contents}
.st-key-home_fab{position:fixed!important;top:10px;left:56px;z-index:999999;width:40px!important;height:40px;
  min-width:0!important;gap:0!important;margin:0!important;padding:0!important;animation:none!important}
.st-key-home_fab :is([data-testid="stElementContainer"],.element-container,.stButton,div:has(>button)){
  width:40px!important;height:40px!important;min-width:0!important;margin:0!important}
.st-key-home_fab button{position:relative;width:40px!important;height:40px!important;min-height:0!important;padding:0!important;
  border:none!important;border-radius:12px!important;color:transparent!important;
  background:linear-gradient(120deg,#6C63FF,#8E7CFF,#B39DFF)!important;box-shadow:0 4px 14px rgba(108,99,255,.32)!important}
.st-key-home_fab button p{font-size:0!important;line-height:0}
.st-key-home_fab button::after{content:"";position:absolute;inset:9px;background:#fff;pointer-events:none;
  -webkit-mask-size:contain;mask-size:contain;-webkit-mask-repeat:no-repeat;mask-repeat:no-repeat;
  -webkit-mask-position:center;mask-position:center;{mask}}
.st-key-home_fab button:hover{transform:translateY(-1px)!important;filter:brightness(1.08);box-shadow:0 8px 20px rgba(108,99,255,.4)!important}
.st-key-home_fab button:focus-visible{outline:2px solid #fff;outline-offset:-4px}
@media (min-width:992px){
  body:has([data-testid="stSidebar"]:is([aria-expanded="true"],[data-collapsed="false"])) .st-key-home_fab{left:352px}}
@media (max-width:991.98px){
  body:has([data-testid="stSidebar"]:is([aria-expanded="true"],[data-collapsed="false"])) .st-key-home_fab{visibility:hidden}}
"""


def register(pages: dict) -> None:
    """登記這次執行的頁面：{slug: StreamlitPage}。"""
    st.session_state[_KEY] = pages


def go(slug: str) -> None:
    """切換到 slug 對應的頁面（找不到就不動作）。"""
    page = st.session_state.get(_KEY, {}).get(slug)
    if page is not None:
        st.switch_page(page)


def home_button() -> None:
    """畫面左上角固定的「回首頁」按鈕。"""
    mask = icons.mask_css("home") if icons.has("home") else ""
    st.markdown(f"<style>{_FAB_CSS.replace('{mask}', mask)}</style>", unsafe_allow_html=True)
    if not mask:  # 沒有 home.png：按鈕上改顯示 emoji
        st.markdown("<style>.st-key-home_fab button::after{content:'🏠';background:none;inset:0;display:grid;"
                    "place-items:center;font-size:1.2rem;color:#fff}</style>", unsafe_allow_html=True)
    with st.container(key="home_fab"):
        if st.button(t("回首頁", "Home"), key="go_home_fab", help=t("回首頁", "Back to Home")):
            go("home")
