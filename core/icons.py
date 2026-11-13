"""自訂 icon：圖檔放在 static/icons/<名稱>.png（透明背景的黑色圖示）。

用 CSS mask 顯示，圖示會自動套用文字顏色，所以淺色 / 深色主題、選取狀態都會跟著變色。
新增 icon：把 png 放進 static/icons/，在 ICONS 加一行即可；頁面裡用 icon("名稱") 產生 HTML。
"""
from __future__ import annotations

from pathlib import Path

ICON_DIR = Path(__file__).resolve().parent.parent / "static" / "icons"
URL = "/app/static/icons/{}.png"  # Streamlit 靜態檔網址（需 .streamlit/config.toml 開 enableStaticServing）

ICONS = {  # 名稱 -> 用途
    "home": "首頁",
    "calendar": "課表",
    "alarm": "考試 / 作業提醒",
    "food": "校園餐廳",
    "bus": "公車班表",
    "map": "校園地圖",
    "clock": "時間 / 營業時間 / 上課時段",
    "settings": "帳號設定",
    "key": "密碼欄位",
    "logout": "登出",
    "star": "關注路線",
    "hourglass": "考試倒數",
    "person": "教授",
    "pin": "地點 / 教室 / 出發站",
    "cap": "App 標誌（側邊欄、登入畫面、分頁圖示）",
    "dice": "今天吃什麼轉盤",
    "school": "學校行事曆",
    "event": "行事曆事件（首頁跑馬燈、開館時間）",
    "megaphone": "校園公告",
    "book": "圖書館",
    "refresh": "重新整理",
    "chair": "圖書館空間使用",
    "news": "最新消息",
    "search": "搜尋 / 失物招領",
    "add": "新增",
    "manage-dates": "課程管理",
    "time-list": "完整時刻表",
    "arrow-up": "箭頭（用 rotate 轉成其他方向）",
}
FALLBACK = {  # 圖檔不存在時改用的 emoji
    "home": "🏠", "calendar": "📆", "alarm": "📅", "food": "🍱", "bus": "🚌", "map": "🗺️", "clock": "🕘",
    "settings": "⚙️", "key": "🔑", "logout": "🚪", "star": "⭐", "hourglass": "⏳", "person": "👤",
    "pin": "📍", "cap": "🎓", "dice": "🎲", "school": "🏫", "event": "🗓️", "megaphone": "📢", "book": "📚",
    "refresh": "🔄", "chair": "🪑", "news": "📰", "search": "🔍", "add": "➕", "manage-dates": "📚",
    "time-list": "📋", "arrow-up": "⬆️",
}
ARROWS = {0: "⬆️", 90: "➡️", 180: "⬇️", 270: "⬅️"}  # arrow-up 旋轉角度 -> 沒有圖時的 emoji


def has(name: str) -> bool:
    return name in ICONS and (ICON_DIR / f"{name}.png").exists()


def icon(name: str, cls: str = "", rotate: int = 0) -> str:
    """回傳一個 icon 的 HTML；沒有這張圖時改用對應的 emoji。rotate：順時針旋轉角度（箭頭用）。"""
    if has(name):
        style = f' style="transform:rotate({rotate}deg)"' if rotate else ""
        return f'<span class="ico ico-{name} {cls}"{style} aria-hidden="true"></span>'
    if name == "arrow-up":
        return ARROWS.get(rotate % 360, "→")
    return FALLBACK.get(name, "")


def arrow(rotate: int = 90) -> str:
    """文字中的箭頭（預設向右 →）。"""
    return icon("arrow-up", "arrow", rotate)


def label(name: str, text: str) -> str:
    """給分頁、按鈕這類「只能放純文字」的標籤：有圖時只留文字（圖由 before_css 畫上），沒圖時前面加 emoji。"""
    return text if has(name) else f"{FALLBACK.get(name, '')} {text}".strip()


def before_css(selector: str, name: str, rotate: int = 0, size: str = "1.1em") -> str:
    """在 selector 元素前面用 ::before 畫上 icon（分頁、按鈕、選項文字不能放 HTML 時用）。沒有圖時回傳空字串。

    Streamlit 1.39+ 會給有 key 的元件（或 st.container(key=...)）加上 .st-key-<key> class，用它來限定範圍。
    """
    if not has(name):
        return ""
    rot = f";transform:rotate({rotate}deg)" if rotate else ""
    return (f"{selector}::before{{content:'';display:inline-block;width:{size};height:{size};margin-right:6px;"
            "vertical-align:-.18em;flex:none;background:currentColor;-webkit-mask-size:contain;mask-size:contain;"
            f"-webkit-mask-repeat:no-repeat;mask-repeat:no-repeat;{_mask(name)}{rot}}}")


def tab_css(key: str, names: list[str]) -> str:
    """st.container(key=key) 裡的 st.tabs：第 i 個分頁標籤前面畫 names[i]。"""
    return "".join(before_css(f".st-key-{key} [data-testid='stTab']:nth-of-type({i}) p", n)
                   for i, n in enumerate(names, 1) if n)


def path(name: str) -> str | None:
    """圖檔路徑（給 st.set_page_config 的分頁圖示用）。"""
    return str(ICON_DIR / f"{name}.png") if has(name) else None


def _mask(name: str) -> str:
    u = URL.format(name)
    return f"-webkit-mask-image:url({u});mask-image:url({u})"


def css(nav_icons: list[str]) -> str:
    """全域 icon 樣式。nav_icons：側邊欄各頁面依序使用的 icon 名稱（沒有圖就給空字串）。"""
    rules = [
        ".ico{display:inline-block;width:1.15em;height:1.15em;flex:none;vertical-align:-.2em;background:currentColor;"
        "-webkit-mask-size:contain;mask-size:contain;-webkit-mask-repeat:no-repeat;mask-repeat:no-repeat;"
        "-webkit-mask-position:center;mask-position:center}",
        ".card-title .ico,.sub .ico{margin-right:6px;color:var(--acc-text)}",
        ".sub .ico.arrow{color:inherit}",  # 公車方向箭頭跟著路線顏色
        ".badge .ico{width:1em;height:1em;vertical-align:-.12em}",
        ".muted .ico,.farea .ico{width:1em;height:1em;margin-right:2px;opacity:.85}",
        ".side-brand{display:flex;align-items:center;gap:10px;font-size:1.6rem;font-weight:800;letter-spacing:.5px;margin:6px 0 10px}",
        ".side-brand .ico{width:1.4em;height:1.4em;color:var(--acc-text)}",
    ]
    rules += [f".ico-{n}{{{_mask(n)}}}" for n in ICONS if has(n)]
    # 側邊欄導覽：用 ::before 畫 icon（Streamlit 的頁面 icon 只接受 emoji）
    nav = ("[data-testid='stSidebarNavItems'] li:nth-child({i}) [data-testid='stSidebarNavLink']::before"
           "{{content:'';width:22px;height:22px;flex:none;margin-right:12px;background:currentColor;opacity:.85;"
           "-webkit-mask-size:contain;mask-size:contain;-webkit-mask-repeat:no-repeat;mask-repeat:no-repeat;{mask}}}")
    for i, n in enumerate(nav_icons, 1):
        if has(n):
            rules.append(nav.format(i=i, mask=_mask(n)))
    rules.append("[data-testid='stSidebarNavLink'][aria-current='page']::before{background:var(--acc)!important;opacity:1!important}")
    # 側邊欄的「帳號設定」展開區塊與「登出」按鈕
    side = ("{sel}::before{{content:'';display:inline-block;width:18px;height:18px;margin-right:8px;flex:none;"
            "background:currentColor;vertical-align:-3px;-webkit-mask-size:contain;mask-size:contain;"
            "-webkit-mask-repeat:no-repeat;mask-repeat:no-repeat;{mask}}}")
    if has("settings"):
        rules.append(side.format(sel="[data-testid='stSidebar'] [data-testid='stExpander'] summary p",
                                 mask=_mask("settings")))
    if has("key"):  # 所有密碼欄位（登入、註冊、修改密碼）的標題前加上鑰匙
        rules.append(side.format(sel="[data-testid='stTextInput']:has(input[aria-label*='密碼']) label p",
                                 mask=_mask("key")))
    if has("logout"):
        rules.append(side.format(sel="[data-testid='stSidebar'] .stButton button p", mask=_mask("logout")))
    return "\n".join(rules)
