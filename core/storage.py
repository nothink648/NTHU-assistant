"""簡易 JSON 存取工具。之後想換成 SQLite 或雲端資料庫，只要改這個檔案。

- load_json / save_json：所有人共用的資料（公車班表、餐廳、帳號清單），放在 data/
- load_user_json / save_user_json：目前登入者自己的資料（課表、考試、設定），放在 data/users/<id>/
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import streamlit as st

from config import DATA_DIR

USERS_DIR = DATA_DIR / "users"


def _read(path: Path, default: Any):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def _write(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")  # 先寫暫存檔再取代，寫到一半當掉也不會弄壞原檔
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def load_json(filename: str, default: Any):
    return _read(DATA_DIR / filename, default)


def save_json(filename: str, data: Any) -> None:
    _write(DATA_DIR / filename, data)


def user_folder(uid: str) -> Path:
    return USERS_DIR / uid


def _user_path(filename: str) -> Path:
    uid = st.session_state.get("auth_uid")
    if not uid:
        raise RuntimeError("尚未登入：個人資料需要先登入才能讀寫")
    return user_folder(uid) / filename


def load_user_json(filename: str, default: Any):
    return _read(_user_path(filename), default)


def save_user_json(filename: str, data: Any) -> None:
    _write(_user_path(filename), data)
