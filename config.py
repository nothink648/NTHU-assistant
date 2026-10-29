"""全域設定：之後想改名稱、圖示、資料夾位置，都在這裡改。"""
from pathlib import Path

APP_TITLE = "校園助手"
APP_ICON = "🎓"

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)
