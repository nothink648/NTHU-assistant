"""全域設定：之後想改名稱、圖示、資料夾位置、節次時間，都在這裡改。"""
import os
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

# ---------- 時區：全站一律用台灣時間（UTC+8），不管伺服器部署在哪個時區 ----------
try:
    from zoneinfo import ZoneInfo
    TZ = ZoneInfo("Asia/Taipei")
except Exception:  # Windows 沒裝 tzdata 時找不到時區資料；台灣沒有日光節約，固定 +8 即可
    TZ = timezone(timedelta(hours=8), "Asia/Taipei")

# 保險：讓沒經過 now_tw() 的 time.localtime() 等也用台灣時間（Windows 沒有 tzset，略過）
os.environ["TZ"] = "Asia/Taipei"
if hasattr(time, "tzset"):
    time.tzset()


def now_tw() -> datetime:
    """現在的台灣時間（不帶時區資訊，方便跟資料檔裡存的時間直接比較）。取代 datetime.now()。"""
    return datetime.now(TZ).replace(tzinfo=None)


def today_tw() -> date:
    """今天的台灣日期。取代 date.today()。"""
    return now_tw().date()


APP_TITLE = "校園助手"
APP_TITLE_EN = "Campus Assistant"
APP_ICON = "🎓"

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)



def app_title() -> str:
    from core.i18n import t  # 延遲 import：config 不依賴 streamlit
    return t(APP_TITLE, APP_TITLE_EN)


WEEKDAYS = ["週一", "週二", "週三", "週四", "週五", "週六", "週日"]

# 課表節次：(代號, 開始, 結束)。學校改時間只要改這裡。
PERIODS = [
    ("1", "08:00", "08:50"),
    ("2", "09:00", "09:50"),
    ("3", "10:10", "11:00"),
    ("4", "11:10", "12:00"),
    ("n", "12:10", "13:00"),
    ("5", "13:20", "14:10"),
    ("6", "14:20", "15:10"),
    ("7", "15:30", "16:20"),
    ("8", "16:30", "17:20"),
    ("9", "17:30", "18:20"),
    ("a", "18:30", "19:20"),
    ("b", "19:30", "20:20"),
    ("c", "20:30", "21:20"),
    ("d", "21:30", "22:20"),
]
