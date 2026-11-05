"""共用介面元件與全域樣式：所有頁面的美化都集中在這裡。"""
import html as _html

import streamlit as st

_CSS = """
<style>
.block-container{padding-top:2.2rem;padding-bottom:3rem;max-width:1100px}
[data-testid="stSidebar"]{background:linear-gradient(180deg,#F1EFFF 0%,#FFFFFF 70%)}
[data-testid="stSidebar"] h1{font-size:1.5rem;font-weight:800;color:#4B43D6}
.stButton>button,.stFormSubmitButton>button{border-radius:12px;font-weight:600;transition:all .15s}
.stButton>button:hover,.stFormSubmitButton>button:hover{transform:translateY(-1px);box-shadow:0 4px 12px rgba(108,99,255,.25)}
[data-testid="stTabs"] button[role="tab"]{font-weight:600;font-size:1rem}
[data-testid="stExpander"]{border-radius:14px;border:1px solid #ECEAFB;background:#fff}
.hero{display:flex;align-items:center;gap:18px;padding:22px 26px;margin-bottom:22px;border-radius:20px;background:linear-gradient(120deg,#6C63FF 0%,#8E7CFF 55%,#B39DFF 100%);box-shadow:0 10px 28px rgba(108,99,255,.28)}
.hero-icon{font-size:2.4rem;line-height:1;background:rgba(255,255,255,.18);border-radius:16px;padding:12px 14px}
.hero h1{margin:0!important;padding:0!important;font-size:1.8rem!important;color:#fff!important}
.hero p{margin:4px 0 0!important;opacity:.92;font-size:.95rem;color:#fff!important}
.card{background:#fff;border:1px solid #ECEAFB;border-radius:16px;padding:16px 18px;margin-bottom:14px;box-shadow:0 4px 14px rgba(50,40,120,.06);transition:transform .15s,box-shadow .15s}
.card:hover{transform:translateY(-2px);box-shadow:0 8px 22px rgba(50,40,120,.12)}
.card-head{display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;gap:8px}
.card-title{font-weight:700;font-size:1.05rem;color:#2B2A4C}
.big{font-size:1.5rem;font-weight:800;color:#4B43D6;line-height:1.3}
.muted{color:#8A88A8;font-size:.85rem}
.badge{display:inline-block;padding:2px 10px;border-radius:999px;font-size:.75rem;font-weight:700;white-space:nowrap}
.row{display:flex;justify-content:space-between;align-items:center;padding:7px 0;border-bottom:1px dashed #ECEAFB;gap:8px}
.row:last-child{border-bottom:none}
.row .t{font-weight:700;color:#2B2A4C}
.row .e{color:#6C63FF;font-weight:600;font-size:.9rem;text-align:right}
.row.dim{opacity:.45}
.exam{border-left:6px solid #6C63FF;margin-bottom:10px}
.exam.urgent{border-left-color:#E5486F;background:#FFF6F8}
.tt-wrap{overflow-x:auto}
.tt{width:100%;border-collapse:separate;border-spacing:4px;table-layout:fixed;min-width:560px}
.tt th{background:#F1EFFF;color:#4B43D6;border-radius:10px;padding:8px 4px;text-align:center;font-size:.9rem}
.tt td{padding:0;vertical-align:top;height:46px}
.tt td.tt-p{background:#FAFAFF;border-radius:10px;text-align:center;width:62px;padding:4px;color:#4B43D6;font-weight:800}
.tt td.tt-p small{display:block;color:#8A88A8;font-size:.62rem;line-height:1.15;font-weight:400}
.tt td.tt-e{background:#FBFBFE;border-radius:10px}
.tt .tt-c{border-radius:10px;padding:5px 8px;font-size:.78rem;line-height:1.3;min-height:46px;margin-bottom:2px}
.tt .tt-c b{font-size:.84rem}
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
