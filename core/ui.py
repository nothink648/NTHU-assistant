"""共用介面元件與全域樣式：所有頁面的美化都集中在這裡。"""
import html as _html

import streamlit as st

_CSS = """
<style>
/* 主題中性：不寫死底色 / 文字色，跟著 Streamlit 的淺色、深色、自動主題走 */
.block-container{padding-top:2.2rem;padding-bottom:3rem;max-width:1100px}
[data-testid="stSidebar"] h1{font-size:1.5rem;font-weight:800}
[data-testid="stBaseButton-primary"],[data-testid="stBaseButton-primaryFormSubmit"]{background:#6C63FF;border-color:#6C63FF;color:#fff}
[data-testid="stBaseButton-primary"]:hover,[data-testid="stBaseButton-primaryFormSubmit"]:hover{background:#5A52E0;border-color:#5A52E0;color:#fff}
[data-baseweb="tab-highlight"]{background-color:#6C63FF!important}
.stButton>button,.stFormSubmitButton>button{border-radius:12px;font-weight:600;transition:all .15s}
.stButton>button:hover,.stFormSubmitButton>button:hover{transform:translateY(-1px);box-shadow:0 4px 12px rgba(108,99,255,.25)}
[data-testid="stTabs"] button[role="tab"]{font-weight:600;font-size:1rem}
[data-testid="stExpander"]{border-radius:14px}
.hero{display:flex;align-items:center;gap:18px;padding:22px 26px;margin-bottom:22px;border-radius:20px;background:linear-gradient(120deg,#6C63FF 0%,#8E7CFF 55%,#B39DFF 100%);box-shadow:0 10px 28px rgba(108,99,255,.28)}
.hero-icon{font-size:2.4rem;line-height:1;background:rgba(255,255,255,.18);border-radius:16px;padding:12px 14px}
.hero h1{margin:0!important;padding:0!important;font-size:1.8rem!important;color:#fff!important}
.hero p{margin:4px 0 0!important;opacity:.92;font-size:.95rem;color:#fff!important}
.card{background:rgba(127,127,127,.08);border:1px solid rgba(127,127,127,.22);border-radius:16px;padding:16px 18px;margin-bottom:14px;transition:transform .15s,box-shadow .15s}
.card:hover{transform:translateY(-2px);box-shadow:0 8px 22px rgba(108,99,255,.18)}
.card-head{display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;gap:8px}
.card-title{font-weight:700;font-size:1.05rem}
.sub{display:flex;justify-content:space-between;align-items:center;margin:12px 0 4px;font-weight:700;font-size:.92rem;color:#7B73FF}
.sub .muted{font-weight:400}
.big{font-size:1.5rem;font-weight:800;color:#7B73FF;line-height:1.3}
.muted{opacity:.62;font-size:.85rem}
.badge{display:inline-block;padding:2px 10px;border-radius:999px;font-size:.75rem;font-weight:700;white-space:nowrap}
.row{display:flex;justify-content:space-between;align-items:center;padding:7px 0;border-bottom:1px dashed rgba(127,127,127,.3);gap:8px}
.row:last-child{border-bottom:none}
.row .t{font-weight:700}
.row .e{color:#7B73FF;font-weight:600;font-size:.9rem;text-align:right}
.row.dim{opacity:.45}
.exam{border-left:6px solid #6C63FF;margin-bottom:10px}
.exam.urgent{border-left-color:#E5486F;background:rgba(229,72,111,.10)}
.tt-wrap{overflow-x:auto;padding-bottom:6px}
.ttg{display:grid;gap:4px;min-width:560px}
.ttg>div{box-sizing:border-box;border-radius:10px}
.tt-h{background:rgba(108,99,255,.16);padding:8px 4px;text-align:center;font-weight:700;font-size:.9rem}
.tt-p{background:rgba(127,127,127,.08);text-align:center;padding:4px;font-weight:800;display:flex;flex-direction:column;justify-content:center}
.tt-p small{display:block;opacity:.6;font-size:.62rem;line-height:1.15;font-weight:400}
.tt-e{background:rgba(127,127,127,.05)}
.ttg>.tt-c{justify-self:start;width:100%;padding:6px 8px;font-size:.78rem;line-height:1.35;overflow:hidden}
.tt-c b{font-size:.86rem}
</style>
"""


def esc(text) -> str:
    """跳脫使用者輸入，避免破壞 HTML 或被當成 LaTeX（$）。"""
    return _html.escape(str(text)).replace("$", "&#36;")


def inject_css() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)


def html(markup: str) -> None:
    st.markdown(markup, unsafe_allow_html=True)


def hero(title: str, subtitle: str = "", icon: str = "") -> None:
    html(f'<div class="hero"><div class="hero-icon">{icon}</div>'
         f'<div><h1>{esc(title)}</h1><p>{esc(subtitle)}</p></div></div>')


def badge(text: str, fg: str = "#4B43D6", bg: str = "#ECEAFF") -> str:
    return f'<span class="badge" style="color:{fg};background:{bg}">{esc(text)}</span>'


def card(inner: str, cls: str = "") -> str:
    """回傳卡片 HTML（需用 html() 顯示）。inner 內的使用者文字請先用 esc()。"""
    return f'<div class="card {cls}">{inner}</div>'
