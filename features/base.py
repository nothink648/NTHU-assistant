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
    ico: str = ""  # 自訂 icon 名稱（static/icons/<ico>.png）；有圖就用圖，沒有就用上面的 emoji
