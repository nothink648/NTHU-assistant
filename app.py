"""入口：streamlit run app.py"""
import streamlit as st

from config import APP_ICON, app_title
from core.auth import current_uid, sync_cookie
from core.login import render_account, render_login
from core import icons, nav as page_nav
from core.ui import inject_css
from features import FEATURES

st.set_page_config(page_title=app_title(), page_icon=icons.path("cap") or APP_ICON, layout="wide")
inject_css(icons.css([f.ico for f in FEATURES]))

uid = current_uid()
sync_cookie()
if not uid:  # 未登入：只顯示登入 / 註冊畫面
    render_login()
    st.stop()

pages = [
    st.Page(f.render, title=f.label(), icon=None if icons.has(f.ico) else f.icon,
            url_path=None if f.default else f.slug, default=f.default)
    for f in FEATURES
]
page_nav.PAGES.update({f.slug: p for f, p in zip(FEATURES, pages)})  # 讓首頁卡片可以跳到各頁

nav = st.navigation(pages)
current = next((i for i, p in enumerate(pages, 1) if p.title == nav.title), 0)
if current:  # 目前所在頁面：icon 與底色用主題色（舊版 Streamlit 沒有 aria-current 可以判斷）
    st.sidebar.markdown(f"<style>[data-testid='stSidebarNavItems'] li:nth-child({current}) [data-testid='stSidebarNavLink']"
                f"{{background:var(--acc-soft)!important;box-shadow:inset 3px 0 0 var(--acc)}}"
                f"[data-testid='stSidebarNavItems'] li:nth-child({current}) [data-testid='stSidebarNavLink']::before"
                f"{{background:var(--acc)!important;opacity:1!important}}</style>", unsafe_allow_html=True)
st.sidebar.markdown(f'<div class="side-brand">{icons.icon("cap")}{app_title()}</div>', unsafe_allow_html=True)
render_account(uid)
nav.run()
