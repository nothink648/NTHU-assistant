from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class Feature:
    """一個功能頁面 = 標題 + 圖示 + render 函式 + 網址代稱。"""
    title: str
    icon: str
    render: Callable[[], None]
    slug: str
    default: bool = False  # 只能有一個功能設為首頁
