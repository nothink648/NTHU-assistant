"""簡易 JSON 存取工具。之後想換成 SQLite 或雲端資料庫，只要改這個檔案。"""
import json
from typing import Any

from config import DATA_DIR


def load_json(filename: str, default: Any):
    path = DATA_DIR / filename
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def save_json(filename: str, data: Any) -> None:
    path = DATA_DIR / filename
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
