"""頁面跳轉：app.py 建好 st.Page 後登記在 PAGES，其他頁面用 goto() 切換（不重新整理瀏覽器，登入狀態不會掉）。"""
from __future__ import annotations

import json

import streamlit as st
import streamlit.components.v1 as components

from core import icons

PAGES: dict = {}  # slug → st.Page（app.py 填入）


def goto(slug: str, **state) -> None:
    """先把要帶到目標頁的資訊放進 session_state，再切換頁面。"""
    st.session_state.update(state)
    page = PAGES.get(slug)
    if page is not None:
        st.switch_page(page)


# 裝到外層頁面執行的程式（不放在 iframe 裡：換頁時 iframe 會被拆掉，外層的程式才會一直在）。
# 把小房子按鈕放進頂部列左側、>> 展開鈕的右邊；Streamlit 重畫頂部列時用 MutationObserver 補回去並維持在 >> 後面。
# 按下時去點側邊欄裡藏起來的 st.button（key=nthu_home_go），走 goto("home")：不重新整理瀏覽器，登入狀態不會掉。
_HOME_JS = r"""(function(){
var d=document;window.__nthuHomeLabel=%(label)s;
if(window.__nthuHome){window.__nthuHome();return;}
function real(){return d.querySelector('.st-key-nthu_home_go button');}
function make(){var b=d.createElement('button');b.id='nthu-home';b.type='button';b.innerHTML=%(ico)s;
  b.addEventListener('click',function(e){e.preventDefault();var r=real();if(r){r.click();}});return b;}
function ensure(){
  var el=d.getElementById('nthu-home')||make(),lb=window.__nthuHomeLabel;
  if(el.title!==lb){el.title=lb;el.setAttribute('aria-label',lb);}
  var show=real()?'':'none';if(el.style.display!==show){el.style.display=show;}  /* 登出（登入畫面）時不顯示 */
  var tb=d.querySelector('[data-testid="stToolbar"]'),exp=d.querySelector('[data-testid="stExpandSidebarButton"]');
  var host=exp&&exp.parentElement?exp.parentElement.parentElement:null;
  if(!host&&tb&&tb.firstElementChild){host=tb.firstElementChild.firstElementChild;}
  if(host&&tb&&tb.contains(host)){
    if(el.classList.contains('fixed')){el.classList.remove('fixed');}
    if(el.parentElement!==host||host.lastElementChild!==el){host.appendChild(el);}
  }else{
    if(!el.classList.contains('fixed')){el.classList.add('fixed');}
    if(el.parentElement!==d.body){d.body.appendChild(el);}
  }
}
var queued=false;
window.__nthuHome=function(){if(queued){return;}queued=true;requestAnimationFrame(function(){queued=false;ensure();});};
new MutationObserver(window.__nthuHome).observe(d.body,{childList:true,subtree:true});
ensure();
})();"""


def home_button(label: str) -> None:
    """頂部列左側（側邊欄 >> 旁）的「一鍵回首頁」小房子按鈕。每次執行都要呼叫（需在 st.navigation 之後）。"""
    with st.sidebar:
        if st.button(label, key="nthu_home_go"):  # 真正的按鈕：CSS 藏起來，由頂部列的小房子代按
            goto("home")
        # 圖示沿用專案的首頁 icon（static/icons/home.png，和側邊欄「首頁」同一張；沒有圖檔時是 🏠）
        code = _HOME_JS % {"label": json.dumps(label), "ico": json.dumps(icons.icon("home"))}
        components.html(
            "<script>/* nthu_assistant_home：core/ui.py 依這個字串把 iframe 藏起來 */"
            "(function(){const doc=window.parent.document;const s=doc.createElement('script');"
            f"s.textContent={json.dumps(code)};doc.head.appendChild(s);s.remove();}})();</script>",
            height=0)


def scroll_to(selector: str) -> None:
    """頁面畫好後把指定元素捲到畫面中間。

    用高度 0 的 components.html（同網域 iframe）操作外層頁面；元素可能晚一點才出現、
    上方內容也可能還在長高，所以找到後隔一下再對準一次。
    """
    components.html(
        "<script>/* nthu_assistant_scroll：core/ui.py 依這個字串把 iframe 藏起來，不佔版面 */"
        "(function(){const doc=window.parent.document;let n=0,hits=0;"
        f"const go=()=>{{const el=doc.querySelector({json.dumps(selector)});"
        "if(el){el.scrollIntoView({behavior:'smooth',block:'center'});if(++hits<4){setTimeout(go,400);}}"
        "else if(n++<50){setTimeout(go,100);}};setTimeout(go,200);})();</script>",
        height=0)
