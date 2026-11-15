"""登入 / 註冊畫面，以及側邊欄的帳號區塊。"""
from __future__ import annotations

import streamlit as st

from config import app_title
from core import auth
from core.i18n import lang_select, t
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
.acct-h{display:flex;align-items:center;gap:6px;font-weight:700;font-size:.9rem;margin:10px 0 2px;color:var(--acc-text)}
.acct-h:first-child{margin-top:0}
.acct-h .ico{width:1.05em;height:1.05em}
</style>"""


def render_login() -> None:
    """未登入時顯示的畫面。"""
    html(_CSS)
    _, mid, _ = st.columns([1, 1.25, 1])
    with mid:
        _, sw = st.columns([2.2, 1.3])
        with sw, st.container(key="login_lang_box"):
            lang_select("login_lang")
        html(f'<div class="login-brand"><div class="logo">{icon("cap")}</div><h1>{app_title()}</h1>'
             f'<p>{t("登入後，課表、考試與設定都只屬於你", "Sign in to keep your timetable, exams and settings to yourself")}</p>'
             f'<div class="login-perks"><span>{icon("calendar")} {t("個人課表", "Personal timetable")}</span>'
             f'<span>{icon("alarm")} {t("考試 / 作業提醒", "Exam & homework reminders")}</span>'
             f'<span>{icon("star")} {t("關注的公車路線", "Favorite bus routes")}</span></div></div>')
        if "auth_flash" in st.session_state:
            st.success(st.session_state.pop("auth_flash"))
        tab_in, tab_up = st.tabs([t("登入", "Sign in"), t("註冊新帳號", "Create account")])
        with tab_in:
            with st.form("login"):
                name = st.text_input(t("帳號", "Username"), key="li_name")
                pw = st.text_input(t("密碼", "Password"), type="password", key="li_pw")
                remember = st.checkbox(t(f"保持登入（{auth.REMEMBER_DAYS} 天）", f"Keep me signed in ({auth.REMEMBER_DAYS} days)"), value=True,
                                       help=t("重新整理頁面也不用再登入；在公用電腦上請取消勾選",
                                              "Stay signed in after refreshing; uncheck on shared computers"))
                if st.form_submit_button(t("登入", "Sign in"), type="primary", use_container_width=True):
                    uid = auth.authenticate(name, pw)
                    if uid:
                        auth.login(uid, remember)
                        st.rerun()
                    st.error(t("帳號或密碼錯誤", "Incorrect username or password"))
        with tab_up:
            with st.form("register"):
                name = st.text_input(t("帳號", "Username"), key="rg_name",
                                     help=t("2–20 個字，可用中文、英文、數字或底線", "2–20 characters: Chinese, letters, digits or underscores"))
                pw = st.text_input(t("密碼", "Password"), type="password", key="rg_pw",
                                   help=t(f"至少 {auth.MIN_PASSWORD} 個字元", f"At least {auth.MIN_PASSWORD} characters"))
                pw2 = st.text_input(t("再輸入一次密碼", "Confirm password"), type="password", key="rg_pw2")
                if st.form_submit_button(t("建立帳號並登入", "Create account and sign in"), type="primary", use_container_width=True):
                    uid, msg = auth.register(name, pw, pw2)
                    if uid:
                        auth.login(uid, remember=True)
                        st.session_state.auth_welcome = msg
                        st.rerun()
                    st.error(msg)


def render_account(uid: str) -> None:
    """側邊欄：目前使用者 + 帳號設定（介面語言、帳號名稱、密碼）+ 登出。"""
    name = auth.username(uid)
    with st.sidebar:
        html(_CSS + f'<div class="user-chip"><div class="av">{name[:1].upper()}</div>'
             f'<div><div class="nm">{esc(name)}</div><div class="sm">{t("已登入", "Signed in")}</div></div></div>')
        acct = t("帳號設定", "Account settings")
        # 有 key 時，切換語言（標題文字改變）後展開狀態仍會保留；舊版 Streamlit 不支援 key 就略過
        try:
            box = st.expander(acct if has("settings") else "⚙️ " + acct, key="acct_box")
        except TypeError:
            box = st.expander(acct if has("settings") else "⚙️ " + acct)
        with box:
            _account_settings(uid, name)
        if "acct_flash" in st.session_state:
            st.toast(st.session_state.pop("acct_flash"), icon=":material/check_box:")
        out = t("登出", "Sign out")
        if st.button(out if has("logout") else "🚪 " + out, use_container_width=True, key="logout_btn"):
            auth.logout()
            st.session_state.auth_flash = t("已登出", "Signed out")
            st.rerun()
    if "auth_welcome" in st.session_state:
        st.toast(st.session_state.pop("auth_welcome"), icon=":material/celebration:")


def _account_settings(uid: str, name: str) -> None:
    """帳號設定的內容：介面語言、帳號名稱、密碼。"""
    html(f'<div class="acct-h">{icon("web") or "🌐"} {t("介面語言", "Language")}</div>')
    lang_select("acct_lang")

    html(f'<div class="acct-h">{icon("person") or "👤"} {t("帳號名稱", "Username")}</div>')
    with st.form("chname", clear_on_submit=True, border=False):
        new_name = st.text_input(t("新帳號名稱", "New username"), placeholder=name, key="chname_new",
                                 help=t("2–20 個字，可用中文、英文、數字或底線", "2–20 characters: Chinese, letters, digits or underscores"))
        pw = st.text_input(t("目前密碼", "Current password"), type="password", key="chname_pw")
        if st.form_submit_button(t("更新帳號名稱", "Update username"), use_container_width=True):
            ok, msg = auth.change_username(uid, new_name, pw)
            if ok:
                st.session_state.acct_flash = msg
                st.rerun()  # 讓上方的名稱、首頁問候語立刻換成新名字
            st.error(msg)

    html(f'<div class="acct-h">{icon("key") or "🔑"} {t("修改密碼", "Change password")}</div>')
    with st.form("chpw", clear_on_submit=True, border=False):
        old = st.text_input(t("目前密碼", "Current password"), type="password", key="chpw_old")
        new = st.text_input(t("新密碼", "New password"), type="password", key="chpw_new")
        new2 = st.text_input(t("再輸入一次新密碼", "Confirm new password"), type="password", key="chpw_new2")
        if st.form_submit_button(t("更新密碼", "Update password"), use_container_width=True):
            ok, msg = auth.change_password(uid, old, new, new2)
            (st.success if ok else st.error)(msg)
