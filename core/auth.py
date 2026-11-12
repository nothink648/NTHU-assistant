"""帳號系統：註冊 / 登入 / 登出 / 保持登入 / 修改密碼。

- 帳號存在 data/users.json；密碼只存「加鹽的 PBKDF2 雜湊」，不存明碼。
- 每個帳號有自己的資料夾 data/users/<id>/（課表、考試、設定），見 core/storage.py。
- 「保持登入」：登入時發一組隨機憑證存在瀏覽器 cookie（30 天），重新整理也不會登出；
  伺服器只存憑證的 SHA-256，登出或改密碼時作廢。
"""
from __future__ import annotations

import hashlib
import hmac
import re
import secrets
import shutil
import uuid
from datetime import datetime, timedelta
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

from config import DATA_DIR
from core.storage import load_json, save_json, user_folder

USERS_FILE = "users.json"
ITERATIONS = 200_000
REMEMBER_DAYS = 30
NAME_RE = re.compile(r"^[A-Za-z0-9_一-鿿]{2,20}$")
MIN_PASSWORD = 6
LEGACY_FILES = ("timetable.json", "exams.json", "settings.json")  # 加入登入功能前、放在 data/ 底下的個人資料
COOKIE = "nthu_assistant_s"


# ---------- 底層 ----------
def _load() -> dict:
    data = load_json(USERS_FILE, {})
    data = data if isinstance(data, dict) else {}
    data.setdefault("users", {})
    data.setdefault("tokens", {})
    return data


def _save(data: dict) -> None:
    save_json(USERS_FILE, data)


def _hash(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), ITERATIONS).hex()


def _token_key(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _find(data: dict, username: str) -> str | None:
    name = username.strip().casefold()
    return next((uid for uid, u in data["users"].items() if u["username"].casefold() == name), None)


def user_dir(uid: str) -> Path:
    path = user_folder(uid)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _adopt_legacy(uid: str) -> list[str]:
    """第一個註冊的帳號接收舊的共用資料（課表、考試、設定），避免加入登入後資料不見。"""
    moved = []
    for name in LEGACY_FILES:
        src = DATA_DIR / name
        if src.exists():
            shutil.move(str(src), str(user_dir(uid) / name))
            moved.append(name)
    return moved


# ---------- 帳號操作 ----------
def register(username: str, password: str, confirm: str) -> tuple[str | None, str]:
    """回傳 (uid, 訊息)；失敗時 uid 為 None。"""
    username = username.strip()
    if not NAME_RE.match(username):
        return None, "帳號需為 2–20 個字，可用中文、英文、數字或底線"
    if len(password) < MIN_PASSWORD:
        return None, f"密碼至少 {MIN_PASSWORD} 個字元"
    if password != confirm:
        return None, "兩次輸入的密碼不一樣"
    data = _load()
    if _find(data, username):
        return None, "這個帳號已經有人使用"
    first = not data["users"]
    uid = uuid.uuid4().hex
    salt = secrets.token_hex(16)
    data["users"][uid] = {"username": username, "salt": salt, "hash": _hash(password, salt),
                          "created": datetime.now().isoformat(timespec="seconds")}
    _save(data)
    user_dir(uid)
    moved = _adopt_legacy(uid) if first else []
    return uid, ("註冊成功！已把原本的課表與考試資料轉到你的帳號" if moved else "註冊成功！")


def authenticate(username: str, password: str) -> str | None:
    data = _load()
    uid = _find(data, username)
    if not uid:
        _hash(password, secrets.token_hex(16))  # 帳號不存在也花一樣的時間，不洩漏帳號是否存在
        return None
    u = data["users"][uid]
    return uid if hmac.compare_digest(_hash(password, u["salt"]), u["hash"]) else None


def change_password(uid: str, old: str, new: str, confirm: str) -> tuple[bool, str]:
    data = _load()
    u = data["users"].get(uid)
    if not u or not hmac.compare_digest(_hash(old, u["salt"]), u["hash"]):
        return False, "目前密碼不正確"
    if len(new) < MIN_PASSWORD:
        return False, f"新密碼至少 {MIN_PASSWORD} 個字元"
    if new != confirm:
        return False, "兩次輸入的新密碼不一樣"
    u["salt"] = secrets.token_hex(16)
    u["hash"] = _hash(new, u["salt"])
    # 改密碼後，其他裝置的「保持登入」全部失效，只留目前這個
    keep = _token_key(st.session_state.get("auth_token") or "")
    data["tokens"] = {k: v for k, v in data["tokens"].items() if v.get("uid") != uid or k == keep}
    _save(data)
    return True, "密碼已更新"


def username(uid: str | None) -> str:
    return _load()["users"].get(uid or "", {}).get("username", "")


# ---------- 保持登入 ----------
def _issue_token(uid: str) -> str:
    token = secrets.token_urlsafe(24)
    data = _load()
    now = datetime.now()
    data["tokens"] = {k: v for k, v in data["tokens"].items()  # 順便清掉過期的
                      if datetime.fromisoformat(v.get("exp", "2000-01-01")) > now}
    data["tokens"][_token_key(token)] = {"uid": uid,
                                         "exp": (now + timedelta(days=REMEMBER_DAYS)).isoformat(timespec="seconds")}
    _save(data)
    return token


def _resolve_token(token: str) -> str | None:
    data = _load()
    t = data["tokens"].get(_token_key(token))
    if not t or datetime.fromisoformat(t.get("exp", "2000-01-01")) <= datetime.now():
        return None
    return t["uid"] if t.get("uid") in data["users"] else None


def _revoke_token(token: str) -> None:
    data = _load()
    if data["tokens"].pop(_token_key(token), None):
        _save(data)


# ---------- 與 Streamlit session 的銜接 ----------
def _reset_session() -> None:
    """換人登入 / 登出時清掉所有暫存狀態，避免看到上一個人的選項。"""
    for k in list(st.session_state.keys()):
        del st.session_state[k]


def login(uid: str, remember: bool) -> None:
    _reset_session()
    st.session_state.auth_uid = uid
    if remember:
        token = _issue_token(uid)
        st.session_state.auth_token = token
        st.session_state.auth_cookie = (token, REMEMBER_DAYS * 86400)  # 下一次畫面輸出時寫進瀏覽器


def logout() -> None:
    token = st.session_state.get("auth_token") or _cookie_token()
    if token:
        _revoke_token(token)
    _reset_session()
    st.session_state.auth_cookie = ("", 0)  # 清掉瀏覽器上的 cookie
    st.session_state.auth_logged_out = True  # 這個分頁內不要再用（已作廢的）舊 cookie 自動登入


def _cookie_token() -> str | None:
    try:
        return st.context.cookies.get(COOKIE)
    except Exception:  # 極舊版 Streamlit 沒有 st.context
        return None


def sync_cookie() -> None:
    """把待寫入的 cookie 透過一個看不見的小元件寫到瀏覽器（Streamlit 本身不能直接設 cookie）。"""
    pending = st.session_state.pop("auth_cookie", None)
    if pending is None:
        return
    value, max_age = pending
    # 這個元件的版面格子由 core/ui.py 的 CSS 依 cookie 名稱隱藏（不能用 JS 改 DOM：Streamlit 會重複使用那個格子）
    components.html(
        f"<script>parent.document.cookie = '{COOKIE}={value}; max-age={max_age}; path=/; SameSite=Lax';</script>",
        height=0)


def current_uid() -> str | None:
    """目前登入的帳號 id。新開的分頁會用 cookie 裡的「保持登入」憑證自動登入。"""
    ss = st.session_state
    uid = ss.get("auth_uid")
    if uid and username(uid):
        return uid
    token = None if ss.get("auth_logged_out") else _cookie_token()
    if token:
        uid = _resolve_token(token)
        if uid:
            ss.auth_uid, ss.auth_token = uid, token
            return uid
    return None
