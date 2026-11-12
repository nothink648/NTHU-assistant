"""🗺️ 校園地圖：
- 3D 校園導覽：把清華 3D 校園導覽嵌入頁面，直接在介面裡操作。
- 2D 校園道路圖：static/maps/campus_roads.jpg，可滾輪 / 按鈕縮放、拖曳移動、雙擊放大。
"""
from __future__ import annotations

from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

from core.ui import hero
from features.base import Feature

MAP_URL = "https://3dcampusguide.nthu.edu.tw/?openExternalBrowser=1"
ROADS_FILE = Path(__file__).resolve().parent.parent / "static" / "maps" / "campus_roads.jpg"
ROADS_URL = "/app/static/maps/campus_roads.jpg"  # 需 .streamlit/config.toml 開 enableStaticServing
SIZES = {"小": 480, "中": 650, "大": 850}  # 視窗高度（px）

# 2D 地圖檢視器：純前端的縮放 / 拖曳，不需重新執行 Python
VIEWER = """
<style>
  html,body{margin:0;height:100%;font-family:"Source Sans Pro",sans-serif}
  #wrap{position:relative;width:100%;height:100%;overflow:hidden;cursor:grab;touch-action:none;
        background:#f6f6f6;border-radius:16px}
  #wrap.drag{cursor:grabbing}
  #img{position:absolute;left:0;top:0;transform-origin:0 0;user-select:none;-webkit-user-drag:none;will-change:transform}
  .tools{position:absolute;right:12px;top:12px;display:flex;flex-direction:column;gap:6px;z-index:2}
  .tools button{width:38px;height:38px;border:none;border-radius:12px;background:rgba(255,255,255,.92);
        box-shadow:0 4px 14px rgba(30,20,90,.18);font-size:20px;font-weight:700;color:#5a52e0;cursor:pointer}
  .tools button:hover{background:#6C63FF;color:#fff}
  .hint{position:absolute;left:12px;bottom:12px;padding:4px 10px;border-radius:999px;font-size:12px;
        background:rgba(0,0,0,.55);color:#fff;pointer-events:none;transition:opacity .4s}
</style>
<div id="wrap">
  <img id="img" src="__SRC__" alt="清華校園道路圖" draggable="false">
  <div class="tools">
    <button id="zin" title="放大">＋</button>
    <button id="zout" title="縮小">－</button>
    <button id="fit" title="整張顯示">⤢</button>
  </div>
  <div class="hint" id="hint">滾輪 / ＋－ 縮放　·　拖曳移動　·　雙擊放大</div>
</div>
<script>
const wrap = document.getElementById('wrap'), img = document.getElementById('img');
let s = 1, x = 0, y = 0, minS = 0.1;
const apply = () => { img.style.transform = `translate(${x}px,${y}px) scale(${s})`; };
const clamp = () => {  // 不讓地圖整張被拖出視窗
  const W = wrap.clientWidth, H = wrap.clientHeight, w = img.naturalWidth * s, h = img.naturalHeight * s;
  x = w <= W ? (W - w) / 2 : Math.min(0, Math.max(W - w, x));
  y = h <= H ? (H - h) / 2 : Math.min(0, Math.max(H - h, y));
};
const fit = () => {
  minS = Math.min(wrap.clientWidth / img.naturalWidth, wrap.clientHeight / img.naturalHeight);
  s = minS; x = 0; y = 0; clamp(); apply();
};
const zoomAt = (f, cx, cy) => {
  const ns = Math.min(4, Math.max(minS, s * f));
  x = cx - (cx - x) * ns / s; y = cy - (cy - y) * ns / s; s = ns; clamp(); apply();
};
const center = () => [wrap.clientWidth / 2, wrap.clientHeight / 2];
img.onload = fit; if (img.complete) fit();
window.addEventListener('resize', fit);
wrap.addEventListener('wheel', e => {
  e.preventDefault(); const r = wrap.getBoundingClientRect();
  zoomAt(e.deltaY < 0 ? 1.15 : 1 / 1.15, e.clientX - r.left, e.clientY - r.top);
}, {passive: false});
wrap.addEventListener('dblclick', e => { const r = wrap.getBoundingClientRect(); zoomAt(1.8, e.clientX - r.left, e.clientY - r.top); });
document.getElementById('zin').onclick = e => { e.stopPropagation(); zoomAt(1.4, ...center()); };
document.getElementById('zout').onclick = e => { e.stopPropagation(); zoomAt(1 / 1.4, ...center()); };
document.getElementById('fit').onclick = e => { e.stopPropagation(); fit(); };
document.querySelectorAll('.tools button').forEach(b => b.addEventListener('dblclick', e => e.stopPropagation()));
// 拖曳（滑鼠與觸控）；兩指縮放
const pts = new Map(); let last = null, pinch = null;
wrap.addEventListener('pointerdown', e => {
  if (e.target.closest('.tools')) return;
  wrap.setPointerCapture(e.pointerId); pts.set(e.pointerId, [e.clientX, e.clientY]);
  last = [e.clientX, e.clientY]; wrap.classList.add('drag');
});
wrap.addEventListener('pointermove', e => {
  if (!pts.has(e.pointerId)) return;
  pts.set(e.pointerId, [e.clientX, e.clientY]);
  if (pts.size === 2) {
    const [a, b] = [...pts.values()], d = Math.hypot(a[0] - b[0], a[1] - b[1]);
    const r = wrap.getBoundingClientRect();
    if (pinch) zoomAt(d / pinch, (a[0] + b[0]) / 2 - r.left, (a[1] + b[1]) / 2 - r.top);
    pinch = d; return;
  }
  x += e.clientX - last[0]; y += e.clientY - last[1]; last = [e.clientX, e.clientY]; clamp(); apply();
});
const up = e => { pts.delete(e.pointerId); pinch = null; if (!pts.size) wrap.classList.remove('drag');
                  else last = [...pts.values()][0]; };
wrap.addEventListener('pointerup', up); wrap.addEventListener('pointercancel', up);
setTimeout(() => { document.getElementById('hint').style.opacity = 0; }, 4000);
</script>
"""


def render() -> None:
    hero("校園地圖", "3D 校園導覽　·　2D 校園道路圖", "map")

    c1, c2 = st.columns([3, 1], vertical_alignment="center")
    size = c1.radio("視窗大小", list(SIZES), index=1, horizontal=True, key="map_size")
    tab_3d, tab_2d = st.tabs(["3D 校園導覽", "2D 校園道路圖"])

    with tab_3d:
        st.link_button("↗ 在新分頁開啟 3D 導覽", MAP_URL)
        components.iframe(MAP_URL, height=SIZES[size], scrolling=False)
        st.caption("地圖由國立清華大學 3D 校園導覽提供。若視窗內無法載入，請改用「在新分頁開啟」。")

    with tab_2d:
        if not ROADS_FILE.exists():
            st.warning("找不到 static/maps/campus_roads.jpg")
        else:
            st.link_button("↗ 在新分頁開啟原圖", ROADS_URL)
            components.html(VIEWER.replace("__SRC__", ROADS_URL), height=SIZES[size])
            st.caption("清華校園道路圖：各道路行經的館舍（校園規劃組、駐警隊製，113.12.30 更新底圖）。")


FEATURE = Feature(title="校園地圖", icon="🗺️", render=render, slug="map", ico="map")
