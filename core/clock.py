"""全站統一的「現在時間」：一律用台灣時間（Asia/Taipei，UTC+8）。

部署到 Streamlit Community Cloud 時伺服器是 UTC+0，直接用 datetime.now() / date.today() 會慢 8 小時，
所以所有需要「現在」的地方都改呼叫這裡的 now() / today()。

- 台灣沒有日光節約時間，固定 +8 小時即可（不需要 tzdata 套件，Windows 也能用）。
- 回傳「不帶時區」的 datetime：資料檔裡的考試時間等都是不帶時區的台灣時間，這樣比較大小不會出錯。
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

TAIPEI = timezone(timedelta(hours=8), "Asia/Taipei")


def now() -> datetime:
    """現在的台灣時間（naive datetime）。"""
    return datetime.now(TAIPEI).replace(tzinfo=None)


def today() -> date:
    """今天的台灣日期。"""
    return now().date()


def to_taipei(dt: datetime) -> datetime:
    """帶時區的 datetime 轉成台灣時間（naive）；本來就不帶時區的視為台灣時間，原樣回傳。"""
    return dt.astimezone(TAIPEI).replace(tzinfo=None) if dt.tzinfo else dt
