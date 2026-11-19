"""共用介面元件與全域樣式：所有頁面的美化與動畫都集中在這裡。

設計原則：
- 主題中性：不寫死底色 / 文字色，跟著 Streamlit 的淺色、深色、自動主題走。
- 動畫短而輕（0.2–0.5 秒），只在「出現」時播放；系統開啟「減少動態效果」時全部關閉。
- 同時相容 Streamlit 1.37（Anaconda）與新版（1.5x+）的 DOM 結構。
"""
import html as _html

import streamlit as st

from core import icons

ACCENT = "#6C63FF"

_CSS = """
<style>
:root{
  --acc:#6C63FF; --acc2:#8E7CFF; --acc3:#B39DFF;
  --acc-soft:rgba(108,99,255,.12); --acc-line:rgba(108,99,255,.35);
  --acc-text:color-mix(in srgb,#6C63FF 82%,currentColor); /* 文字用：深色主題自動變亮 */
  --line:rgba(127,127,127,.20); --surface:rgba(127,127,127,.06);
  --ease:cubic-bezier(.22,.8,.24,1); --spring:cubic-bezier(.34,1.56,.64,1);
  --solid:transparent; /* 與頁面底色相同的不透明色（見下方 @supports） */
  --card-bg:linear-gradient(var(--surface),var(--surface)),var(--solid);
}
/* 依文字顏色推回頁面底色：深色文字 → 白底；淺色文字 → Streamlit 深色主題的底色。
   卡片先鋪這層不透明底，背景的極光就不會透進格子裡。舊瀏覽器不支援時維持原本的半透明。 */
@supports (color:hsl(from red h s l)){
  :root{--solid:hsl(from currentColor 220 24 clamp(7,calc((50 - l) * 999),100))}
}

/* ---------- 動態背景（所有分頁）：兩層緩慢漂移的極光色塊 + 一層飄動的光點 ---------- */
.stApp{isolation:isolate}
.stApp::before,.stApp::after,[data-testid="stAppViewContainer"]::before{
  content:"";position:fixed;pointer-events:none;z-index:-1}
.stApp::before,.stApp::after{will-change:transform;backface-visibility:hidden}
.stApp::before{inset:-25%;filter:blur(40px);
  background:radial-gradient(circle at 22% 28%,rgba(108,99,255,.30),transparent 34%),
             radial-gradient(circle at 78% 18%,rgba(229,72,111,.20),transparent 30%),
             radial-gradient(circle at 62% 82%,rgba(46,158,106,.18),transparent 32%);
  animation:auroraA 24s ease-in-out infinite alternate}
.stApp::after{inset:-25%;filter:blur(50px);
  background:radial-gradient(circle at 75% 62%,rgba(44,139,201,.22),transparent 30%),
             radial-gradient(circle at 28% 78%,rgba(224,138,30,.15),transparent 28%),
             radial-gradient(circle at 45% 40%,rgba(155,81,224,.14),transparent 30%);
  animation:auroraB 31s ease-in-out infinite alternate}
[data-testid="stAppViewContainer"]::before{inset:-68px 0 0 -34px;opacity:.5;will-change:transform;
  background-image:radial-gradient(rgba(108,99,255,.35) 1.2px,transparent 1.6px);background-size:34px 34px;
  -webkit-mask-image:radial-gradient(ellipse at 50% 30%,#000 10%,transparent 70%);
          mask-image:radial-gradient(ellipse at 50% 30%,#000 10%,transparent 70%);
  animation:dotsDrift 40s linear infinite}
@keyframes auroraA{0%{transform:translate(0,0) rotate(0deg) scale(1)}
  50%{transform:translate(7%,-5%) rotate(14deg) scale(1.1)}100%{transform:translate(-6%,6%) rotate(-10deg) scale(1)}}
@keyframes auroraB{0%{transform:translate(0,0) rotate(0deg) scale(1.05)}
  50%{transform:translate(-8%,4%) rotate(-12deg) scale(.95)}100%{transform:translate(5%,-6%) rotate(8deg) scale(1.1)}}
@keyframes dotsDrift{from{transform:translate3d(0,0,0)}to{transform:translate3d(34px,68px,0)}}
[data-testid="stHeader"]{background:transparent!important}
/* ---------- 頂部列與平台圖示 ----------
   保留：頂部列、右上工具列、三點選單（Rerun / Settings / Clear cache…）、本機的 Running 狀態提示、左上 >> 側邊欄鈕。
   只隱藏：Fork / GitHub 圖示、頂部裝飾彩條、Streamlit Cloud 右下角的皇冠與開發者頭像徽章。 */
[data-testid="stHeader"],[data-testid="stToolbar"]{display:flex!important;visibility:visible!important}
#MainMenu,[data-testid="stMainMenu"],[data-testid="stStatusWidget"]{display:block!important;visibility:visible!important;pointer-events:auto!important}
[data-testid="stToolbarActions"],[data-testid="stDecoration"],
[class*="viewerBadge"],[data-testid="manage-app-button"],.stAppDeployButton,[data-testid="stAppDeployButton"]{display:none!important}
/* 三點選單裡只隱藏 Print、Record screen（Rerun / Clear cache 等開發者選項由 config.toml 的 toolbarMode 決定） */
[data-testid="stMainMenuItem-print"],[data-testid="stMainMenuItem-recordScreencast"],[data-testid="stMainMenuDivider"]{display:none!important}
/* 寫登入 cookie 用的隱形元件（見 core/auth.py）不佔版面 */
:is([data-testid="stElementContainer"],.element-container):has(iframe[srcdoc*="nthu_assistant_s"]){display:none!important}
[data-testid="stExpander"] details{background:var(--solid)}

/* ---------- 動畫 ---------- */
@keyframes fadeUp{from{opacity:0;transform:translateY(12px)}to{opacity:1;transform:none}}
@keyframes fadeIn{from{opacity:0}to{opacity:1}}
@keyframes popIn{from{opacity:0;transform:scale(.94)}to{opacity:1;transform:none}}
@keyframes slideRight{from{opacity:0;transform:translateX(-10px)}to{opacity:1;transform:none}}
@keyframes heroShift{0%{background-position:0% 50%}50%{background-position:100% 50%}100%{background-position:0% 50%}}
@keyframes floaty{0%,100%{transform:translate3d(0,0,0)}50%{transform:translate3d(0,-5px,0)}}
@keyframes pulse{0%,100%{box-shadow:0 0 0 0 rgba(229,72,111,.35)}50%{box-shadow:0 0 0 6px rgba(229,72,111,0)}}
@keyframes livePulse{0%,100%{opacity:1}50%{opacity:.35}}
@keyframes barGrow{from{transform:scaleX(0)}to{transform:scaleX(1)}}

/* ---------- 版面 ---------- */
.block-container,[data-testid="stMainBlockContainer"]{padding-top:2.4rem;padding-bottom:3rem;max-width:1100px}
hr{border-color:var(--line)!important}

/* 換頁 / 切換分頁時，內容由下往上淡入 */
.block-container>div>[data-testid="stVerticalBlock"]>[data-testid="stElementContainer"],
.block-container>div>[data-testid="stVerticalBlock"]>[data-testid="element-container"],
.block-container>div>[data-testid="stVerticalBlock"]>[data-testid="stHorizontalBlock"],
.block-container>div>[data-testid="stVerticalBlock"]>div>[data-testid="stHorizontalBlock"],
.block-container>div>[data-testid="stVerticalBlock"]>[data-testid="stExpander"],
.block-container>div>[data-testid="stVerticalBlock"]>[data-testid="stTabs"],
.block-container>div>[data-testid="stVerticalBlock"]>div>[data-testid="stTabs"]{animation:fadeUp .45s var(--ease) both}
[data-testid="stTabPanel"],[data-baseweb="tab-panel"]{animation:fadeUp .38s var(--ease) both}
[data-testid="stExpanderDetails"]{animation:fadeIn .3s ease both}
[data-testid="stAlert"],[data-testid="stAlertContainer"]{animation:slideRight .35s var(--ease) both}

/* ---------- 側邊欄 ---------- */
@media (min-width:992px){
  [data-testid="stSidebar"]:is([aria-expanded="true"],[data-collapsed="false"]){width:340px!important;min-width:340px!important;max-width:340px!important}
  [data-testid="stSidebarNavLink"]{padding:10px 14px!important;margin:2px 0}
  [data-testid="stSidebarNavLink"] span{font-size:1.12rem!important}
  [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,[data-testid="stSidebar"] label p{font-size:1.02rem}
}
[data-testid="stSidebar"] h1{font-size:1.6rem;font-weight:800;letter-spacing:.5px}
[data-testid="stSidebarNavLink"]{display:flex!important;align-items:center}
/* 1.37 會把導覽清單限高並出現「View more」，全部展開 */
[data-testid="stSidebarNavItems"]{max-height:none!important}
[data-testid="stSidebarNavViewButton"]{display:none!important}
[data-testid="stSidebarNavLink"]{border-radius:10px;transition:background .2s ease,transform .2s var(--ease)}
[data-testid="stSidebarNavLink"]:hover{transform:translateX(3px);background:var(--acc-soft)!important}
[data-testid="stSidebarNavLink"][aria-current="page"],[data-testid="stSidebarNavLink"].active{background:var(--acc-soft)!important;box-shadow:inset 3px 0 0 var(--acc)}
[data-testid="stSidebarNavLink"] span{transition:color .2s}
[data-testid="stSidebarNavLink"][aria-current="page"] span{color:var(--acc)!important;font-weight:700}

/* ---------- 按鈕 ---------- */
.stButton>button,.stFormSubmitButton>button{border-radius:12px;font-weight:600;transition:transform .18s var(--ease),box-shadow .18s ease,background .18s ease,border-color .18s ease}
.stButton>button:hover,.stFormSubmitButton>button:hover{transform:translateY(-1px);box-shadow:0 6px 16px rgba(108,99,255,.22);border-color:var(--acc);color:var(--acc)}
.stButton>button:active,.stFormSubmitButton>button:active{transform:translateY(0) scale(.97)}
[data-testid="stBaseButton-primary"],[data-testid="stBaseButton-primaryFormSubmit"],
[data-testid="baseButton-primary"],[data-testid="baseButton-primaryFormSubmit"]{background:linear-gradient(120deg,var(--acc),var(--acc2))!important;border:none!important;color:#fff!important}
[data-testid="stBaseButton-primary"]:hover,[data-testid="stBaseButton-primaryFormSubmit"]:hover,
[data-testid="baseButton-primary"]:hover,[data-testid="baseButton-primaryFormSubmit"]:hover{filter:brightness(1.08);color:#fff!important;box-shadow:0 8px 20px rgba(108,99,255,.35)}
/* 連結按鈕（st.link_button type="primary"）也用主題紫 */
[data-testid="stBaseLinkButton-primary"]{background:linear-gradient(120deg,var(--acc),var(--acc2))!important;border:none!important;color:#fff!important}
[data-testid="stBaseLinkButton-primary"]:hover{filter:brightness(1.08);color:#fff!important;box-shadow:0 8px 20px rgba(108,99,255,.35)}

/* ---------- Streamlit 內建元件改成主題紫（取代預設紅） ---------- */
[data-testid="stTab"]{transition:color .2s}
[data-testid="stTab"][aria-selected="true"],[data-testid="stTab"][aria-selected="true"] p{color:var(--acc)!important}
[data-testid="stTab"][aria-selected="true"]>div:not([data-testid]){background:var(--acc)!important}
[data-baseweb="tab-highlight"]{background-color:var(--acc)!important}
[data-testid="stTab"]:hover p{color:var(--acc)}
[data-testid="stTabs"] [role="tab"]{font-weight:600;font-size:1rem}
[data-baseweb="input"]:focus-within,[data-baseweb="base-input"]:focus-within,[data-baseweb="textarea"]:focus-within,
[data-testid="stTextInputRootElement"]:focus-within,[data-testid="stNumberInputContainer"]:focus-within,
[data-baseweb="select"]>div:focus-within{border-color:var(--acc)!important}
[data-baseweb="tag"],[data-testid="stMultiSelectTagsContainer"] [role="group"]>span{background:var(--acc)!important;animation:popIn .25s var(--spring) both}
label[data-testid="stRadioOption"]:has(input:checked)>div:first-of-type>div:not([data-testid]),
[data-baseweb="radio"]:has(input:checked)>div:first-of-type{background:var(--acc)!important;border-color:var(--acc)!important}
[data-testid="stCheckbox"] label:has(input:checked)>div:first-of-type,
[data-testid="stCheckbox"] label:has(input:checked)>span:first-of-type{background-color:var(--acc)!important;border-color:var(--acc)!important}
[data-testid="stExpander"] details{border-radius:14px;border-color:var(--line);transition:border-color .2s,box-shadow .2s}
[data-testid="stExpander"] details:hover{border-color:var(--acc-line)}
[data-testid="stExpander"] details[open]{box-shadow:0 6px 20px rgba(108,99,255,.08)}
[data-testid="stVerticalBlockBorderWrapper"]:has(>div>[data-testid="stVerticalBlock"]){border-radius:16px}
[data-testid="stMetric"]{background:var(--card-bg);border:1px solid var(--line);border-radius:14px;padding:12px 16px;animation:popIn .4s var(--ease) both}
[data-testid="stMetricValue"]{color:var(--acc-text)}
iframe[title="st.iframe"],[data-testid="stIFrame"]{border-radius:16px;border:1px solid var(--line)!important;
  box-shadow:0 10px 28px rgba(108,99,255,.12);animation:fadeUp .5s var(--ease) both;background:var(--card-bg)}

/* ---------- 頁首 Hero ---------- */
.hero{position:relative;overflow:hidden;display:flex;align-items:center;gap:18px;padding:22px 26px;margin-bottom:8px;border-radius:20px;
  background:linear-gradient(120deg,#6C63FF,#8E7CFF,#B39DFF,#8E7CFF,#6C63FF);background-size:300% 300%;
  animation:heroShift 14s ease infinite,fadeUp .5s var(--ease) both;box-shadow:0 10px 28px rgba(108,99,255,.25)}
.hero::before,.hero::after{content:"";position:absolute;border-radius:50%;background:rgba(255,255,255,.13);pointer-events:none}
.hero::before{width:220px;height:220px;right:-60px;top:-110px}
.hero::after{width:120px;height:120px;right:140px;bottom:-80px}
.hero-icon{font-size:2.3rem;line-height:1;background:rgba(255,255,255,.2);border-radius:16px;padding:12px 14px;
  animation:floaty 4s ease-in-out infinite;will-change:transform;backface-visibility:hidden;display:grid;place-items:center}
.hero-icon .ico{width:2.6rem;height:2.6rem;color:#fff;vertical-align:0}
.hero h1{margin:0!important;padding:0!important;font-size:1.75rem!important;color:#fff!important;letter-spacing:.5px}
.hero p{margin:4px 0 0!important;opacity:.92;font-size:.95rem;color:#fff!important}

/* ---------- 卡片 ---------- */
.card{background:var(--card-bg);border:1px solid var(--line);border-radius:16px;padding:16px 18px;margin-bottom:14px;
  transition:transform .25s var(--ease),box-shadow .25s ease,border-color .25s ease;animation:fadeUp .5s var(--ease) both}
.card:hover{transform:translateY(-3px);box-shadow:0 12px 28px rgba(108,99,255,.14);border-color:var(--acc-line)}
:is([data-testid="stColumn"],[data-testid="column"]):nth-child(2) .card{animation-delay:.07s}
:is([data-testid="stColumn"],[data-testid="column"]):nth-child(3) .card{animation-delay:.14s}
:is([data-testid="stColumn"],[data-testid="column"]):nth-child(4) .card{animation-delay:.21s}
.card-head{display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;gap:8px}
.card-title{font-weight:700;font-size:1.05rem}
.sub{display:flex;justify-content:space-between;align-items:center;margin:12px 0 4px;font-weight:700;font-size:.92rem;color:var(--acc-text)}
.sub .muted{font-weight:400}
.big{font-size:1.5rem;font-weight:800;color:var(--acc-text);line-height:1.3}
.muted{opacity:.62;font-size:.85rem}
.empty{text-align:center;padding:10px 0 4px;opacity:.6;font-size:.9rem}
.empty .em{display:block;width:max-content;margin:0 auto 4px;font-size:1.8rem;animation:floaty 3.5s ease-in-out infinite;
  will-change:transform;backface-visibility:hidden}
.badge{display:inline-flex;align-items:center;gap:4px;padding:2px 10px;border-radius:999px;font-size:.75rem;font-weight:700;white-space:nowrap;
  color:color-mix(in srgb,var(--c,#6C63FF) 78%,currentColor);background:color-mix(in srgb,var(--c,#6C63FF) 15%,transparent)}
.badge.live::before{content:"";width:6px;height:6px;border-radius:50%;background:currentColor;animation:livePulse 1.4s ease-in-out infinite}
.row{display:flex;justify-content:space-between;align-items:center;padding:8px 6px;margin:0 -6px;border-bottom:1px dashed var(--line);gap:8px;border-radius:8px;
  transition:background .2s;animation:slideRight .4s var(--ease) both}
.row:hover{background:var(--acc-soft)}
.row:last-child{border-bottom:none}
.row:nth-child(2){animation-delay:.04s}.row:nth-child(3){animation-delay:.08s}.row:nth-child(4){animation-delay:.12s}
.row:nth-child(5){animation-delay:.16s}.row:nth-child(n+6){animation-delay:.2s}
.row .t{font-weight:700}
.row .e{color:var(--acc-text);font-weight:600;font-size:.9rem;text-align:right}
.row.dim{opacity:.45}
.progress{height:4px;border-radius:4px;background:var(--line);overflow:hidden;margin-top:10px}
.progress>i{display:block;height:100%;background:linear-gradient(90deg,var(--acc),var(--acc3));transform-origin:left;animation:barGrow .8s var(--ease) both}

/* ---------- 考試 ---------- */
.line-dot{display:inline-block;width:12px;height:12px;border-radius:50%;margin-right:8px;vertical-align:middle;flex:none}
.line-dot.sm{width:9px;height:9px;margin-right:6px}
.card.route{border-top-left-radius:14px;border-top-right-radius:14px}
.exam{border-left:5px solid var(--acc)}
.exam.urgent{border-left-color:#E5486F;background:linear-gradient(rgba(229,72,111,.07),rgba(229,72,111,.07)),var(--solid)}
.exam.urgent .badge{animation:pulse 2s ease-in-out infinite}
.links{display:flex;flex-wrap:wrap;gap:6px;margin-top:10px}
.link-chip{display:inline-flex;align-items:center;gap:4px;padding:3px 12px;border-radius:999px;font-size:.8rem;font-weight:600;
  text-decoration:none!important;color:var(--acc-text)!important;background:var(--acc-soft);border:1px solid var(--acc-line);
  transition:transform .18s var(--ease),background .18s,box-shadow .18s;animation:popIn .3s var(--ease) both}
.link-chip:hover{transform:translateY(-1px);background:rgba(108,99,255,.2);box-shadow:0 4px 12px rgba(108,99,255,.2)}

/* ---------- 課表 ---------- */
.tt-wrap{overflow-x:auto;padding-bottom:6px;margin-top:6px}
.ttg{display:grid;gap:4px;min-width:560px;background:var(--solid);border-radius:12px}
.ttg>div{box-sizing:border-box;border-radius:10px}
.tt-h{background:var(--acc-soft);padding:8px 4px;text-align:center;font-weight:700;font-size:.9rem}
.tt-h.today{background:var(--acc);color:#fff}
.tt-p{background:var(--surface);text-align:center;padding:4px;font-weight:800;display:flex;flex-direction:column;justify-content:center}
.tt-p small{display:block;opacity:.6;font-size:.62rem;line-height:1.15;font-weight:400}
.tt-e{background:rgba(127,127,127,.04)}
.ttg>.tt-c{justify-self:start;width:100%;padding:6px 8px;font-size:.78rem;line-height:1.35;overflow:hidden;
  animation:popIn .4s var(--ease) both;transition:transform .2s var(--ease),box-shadow .2s;cursor:default}
.ttg>.tt-c:hover{transform:scale(1.03);box-shadow:0 6px 16px rgba(0,0,0,.12);z-index:2}
.tt-c b{font-size:.86rem}

@media (prefers-reduced-motion:reduce){*,*::before,*::after{animation:none!important;transition:none!important}}
</style>
"""


def esc(text) -> str:
    """跳脫使用者輸入，避免破壞 HTML 或被當成 LaTeX（$）。"""
    return _html.escape(str(text)).replace("$", "&#36;")


def inject_css(extra: str = "") -> None:
    st.markdown(_CSS + (f"<style>{extra}</style>" if extra else ""), unsafe_allow_html=True)


def html(markup: str) -> None:
    st.markdown(markup, unsafe_allow_html=True)


def hero(title: str, subtitle: str = "", icon: str = "") -> None:
    """icon 可以是自訂 icon 名稱（見 core/icons.py）或 emoji。"""
    icon = icons.icon(icon) if icons.has(icon) else icon
    html(f'<div class="hero"><div class="hero-icon">{icon}</div>'
         f'<div><h1>{esc(title)}</h1><p>{esc(subtitle)}</p></div></div>')


def badge(text: str, color: str = ACCENT, live: bool = False, ico: str = "") -> str:
    """膠囊標籤。只需給一個主色，淺色 / 深色主題會自動調整明暗；ico 是前面的自訂 icon 名稱。"""
    cls = "badge live" if live else "badge"
    # 直接寫入顏色（舊版 Streamlit 會濾掉 inline 的 CSS 變數）；color-mix 搭配 currentColor 讓深色主題自動變亮
    style = (f"color:color-mix(in srgb,{color} 78%,currentColor);"
             f"background:color-mix(in srgb,{color} 15%,transparent)")
    prefix = icons.icon(ico) + " " if ico else ""
    return f'<span class="{cls}" style="{style}">{prefix}{esc(text)}</span>'


def card(inner: str, cls: str = "") -> str:
    """回傳卡片 HTML（需用 html() 顯示）。inner 內的使用者文字請先用 esc()。"""
    return f'<div class="card {cls}">{inner}</div>'


def empty(emoji: str, text: str) -> str:
    """卡片內的空狀態。"""
    return f'<div class="empty"><span class="em">{emoji}</span>{esc(text)}</div>'
