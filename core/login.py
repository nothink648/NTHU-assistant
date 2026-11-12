"""登入 / 註冊畫面，以及側邊欄的帳號區塊。"""
from __future__ import annotations

import streamlit as st

from config import APP_ICON, APP_TITLE
from core import auth
from core.icons import has, icon
from core.ui import esc, html

_CSS = """<style>
.login-brand{text-align:center;margin:4vh 0 18px;animation:fadeUp .5s var(--ease) both}
.login-brand .logo{display:inline-grid;place-items:center;width:84px;height:84px;border-radius:26px;font-size:2.8rem;
  background:linear-gradient(135deg,#6C63FF,#B39DFF);box-shadow:0 14px 34px rgba(108,99,255,.35);
  animation:floaty 4s ease-in-out infinite}
.login-brand h1{margin:14px 0 2px!important;padding:0!important;font-size:1.9rem!important}
.login-brand p{opacity:.65;margin:0}
.login-perks{display:flex;justify-content:center;flex-wrap:wrap;gap:8px;margin-top:14px}
.login-brand .logo .ico{width:3rem;height:3rem;color:#fff}
.login-perks .ico{width:1.05em;height:1.05em;vertical-align:-.17em;margin-right:2px;opacity:1;background:currentColor}
.login-perks span{font-size:.78rem;font-weight:600;padding:3px 10px;border-radius:999px;background:var(--acc-soft);color:var(--acc-text)}
.user-chip{display:flex;align-items:center;gap:10px;padding:10px 12px;border-radius:14px;background:var(--card-bg);
  border:1px solid var(--line);margin:4px 0 8px;animation:fadeUp .4s var(--ease) both}
.user-chip .av{flex:none;width:36px;height:36px;border-radius:50%;display:grid;place-items:center;font-weight:800;color:#fff;
  background:linear-gradient(135deg,#6C63FF,#B39DFF)}
.user-chip .nm{font-weight:700;line-height:1.2}
.user-chip .sm{font-size:.75rem;opacity:.6}
</style>"""


def render_login() -> None:
    """未登入時顯示的畫面。"""
    html(_CSS)
    _, mid, _ = st.columns([1, 1.25, 1])
    with mid:
        html(f'<div class="login-brand"><div class="logo">{icon("cap")}</div><h1>{APP_TITLE}</h1>'
             f'<p>登入後，課表、考試與設定都只屬於你</p>'
             f'<div class="login-perks"><span>{icon("calendar")} 個人課表</span><span>{icon("alarm")} 考試提醒</span>'
             f'<span>{icon("star")} 關注的公車路線</span></div></div>')
        if "auth_flash" in st.session_state:
            st.success(st.session_state.pop("auth_flash"))
        tab_in, tab_up = st.tabs(["登入", "✨ 註冊新帳號"])
        with tab_in:
            with st.form("login"):
                name = st.text_input("帳號", key="li_name")
                pw = st.text_input("密碼", type="password", key="li_pw")
                remember = st.checkbox(f"保持登入（{auth.REMEMBER_DAYS} 天）", value=True,
                                       help="重新整理頁面也不用再登入；在公用電腦上請取消勾選")
                if st.form_submit_button("登入", type="primary", use_container_width=True):
                    uid = auth.authenticate(name, pw)
                    if uid:
                        auth.login(uid, remember)
                        st.rerun()
                    st.error("帳號或密碼錯誤")
        with tab_up:
            with st.form("register"):
                name = st.text_input("帳號", key="rg_name", help="2–20 個字，可用中文、英文、數字或底線")
                pw = st.text_input("密碼", type="password", key="rg_pw", help=f"至少 {auth.MIN_PASSWORD} 個字元")
                pw2 = st.text_input("再輸入一次密碼", type="password", key="rg_pw2")
                if st.form_submit_button("建立帳號並登入", type="primary", use_container_width=True):
                    uid, msg = auth.register(name, pw, pw2)
                    if uid:
                        auth.login(uid, remember=True)
                        st.session_state.auth_welcome = msg
                        st.rerun()
                    st.error(msg)


def render_account(uid: str) -> None:
    """側邊欄：目前使用者 + 修改密碼 + 登出。"""
    name = auth.username(uid)
    with st.sidebar:
        html(_CSS + f'<div class="user-chip"><div class="av">{name[:1].upper()}</div>'
             f'<div><div class="nm">{esc(name)}</div><div class="sm">已登入</div></div></div>')
        with st.expander("帳號設定" if has("settings") else "⚙️ 帳號設定"):
            with st.form("chpw", clear_on_submit=True):
                old = st.text_input("目前密碼", type="password")
                new = st.text_input("新密碼", type="password")
                new2 = st.text_input("再輸入一次新密碼", type="password")
                if st.form_submit_button("更新密碼"):
                    ok, msg = auth.change_password(uid, old, new, new2)
                    (st.success if ok else st.error)(msg)
        if st.button("登出" if has("logout") else "🚪 登出", use_container_width=True):
            auth.logout()
            st.session_state.auth_flash = "已登出"
            st.rerun()
    if "auth_welcome" in st.session_state:
        st.toast(st.session_state.pop("auth_welcome"), icon="🎉")

