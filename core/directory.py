"""📇 校園通訊錄（NTHU Data API 的 /directory）：各處室、系所的網站、電話、分機、Email 與承辦人員。

- find_unit("總務處出納組") → 對應的單位資料；公告的「單位」名稱是「上層單位＋單位」連在一起，這裡負責對回去。
- contact_html(unit) → 可以直接放進卡片的聯絡資訊 HTML。
"""
from __future__ import annotations

import re

from core import nthu_api
from core.i18n import t
from core.icons import icon
from core.ui import esc

SAFE_URL = re.compile(r"^https?://", re.I)
EMAIL = re.compile(r"^[\w.+-]+@[\w-]+(\.[\w-]+)+$")


def _norm(text: str) -> str:
    return re.sub(r"\s+", "", text or "")


def load_directory() -> tuple[list[dict], str | None]:
    data, err = nthu_api.get("/directory", ttl=86400)  # 通訊錄很少變動，一天更新一次
    return [u for u in data or [] if isinstance(u, dict) and u.get("name")], err


def unit_title(u: dict) -> str:
    """「總務處 › 出納組」；最上層單位只顯示自己的名稱。"""
    return f"{u['parent_name']} › {u['name']}" if u.get("parent_name") else u["name"]


def _index(units: list[dict]) -> dict[str, dict]:
    idx: dict[str, dict] = {}
    for u in units:  # 「上層＋名稱」優先，其次才是單獨的名稱（不同處室可能都有「綜合業務組」）
        idx.setdefault(_norm((u.get("parent_name") or "") + u["name"]), u)
    for u in units:
        idx.setdefault(_norm(u["name"]), u)
    return idx


def find_unit(dept: str, units: list[dict], idx: dict[str, dict] | None = None) -> dict | None:
    """公告單位名稱 → 通訊錄單位。完全對不到時，改找名稱結尾相同、最長的單位（例如「…中心華德福教育中心」）。"""
    if not dept:
        return None
    idx = idx if idx is not None else _index(units)
    key = _norm(dept)
    if key in idx:
        return idx[key]
    tails = [k for k in idx if len(k) >= 3 and key.endswith(k)]
    return idx[max(tails, key=len)] if tails else None


def make_finder(units: list[dict]):
    """回傳 dept → unit 的查詢函式（索引只建一次，供整頁的公告共用）。"""
    idx = _index(units)
    cache: dict[str, dict | None] = {}

    def finder(dept: str) -> dict | None:
        if dept not in cache:
            cache[dept] = find_unit(dept, units, idx)
        return cache[dept]
    return finder


def _link(url: str, text: str) -> str:
    return f'<a href="{esc(url)}" target="_blank" rel="noopener">{esc(text)}</a>'


def _mail(addr: str) -> str:
    addr = (addr or "").strip()
    return f'<a href="mailto:{esc(addr)}">{esc(addr)}</a>' if EMAIL.match(addr) else esc(addr)


def contact_html(u: dict, people: bool = True) -> str:
    """單位的聯絡資訊：網站、電話、分機、傳真、Email，以及（可展開的）人員名單。"""
    c = (u.get("details") or {}).get("contact") or {}
    lines = []
    site = (c.get("website") or "").strip()
    if SAFE_URL.match(site):
        lines.append(f'{icon("globe") or "🌐"} {_link(site, t("單位網站", "Website"))}')
    if c.get("phone"):
        lines.append(f'☎️ {esc(c["phone"])}')
    if c.get("extension"):
        lines.append(f'📞 {t("分機", "Ext.")} {esc(c["extension"])}')
    if c.get("fax"):
        lines.append(f'📠 {t("傳真", "Fax")} {esc(c["fax"])}')
    if c.get("email"):
        lines.append(f'✉️ {_mail(c["email"])}')
    if SAFE_URL.match(u.get("url") or ""):
        lines.append(f'📇 {_link(u["url"], t("通訊錄頁面", "Directory page"))}')
    body = ('<div class="dir-lines">' + "".join(f"<span>{x}</span>" for x in lines) + "</div>") if lines else \
        f'<div class="muted">{t("通訊錄沒有這個單位的聯絡方式", "No contact info listed")}</div>'

    staff = (u.get("details") or {}).get("people") or []
    if people and staff:
        rows = "".join(
            f'<tr><td>{esc(p.get("name") or "")}</td><td>{esc(p.get("title") or "")}</td>'
            f'<td>{esc(p.get("extension") or "")}</td><td>{_mail(p.get("email") or "")}</td></tr>'
            for p in staff)
        body += (f'<details class="dir-people"><summary>{t(f"承辦人員（{len(staff)} 位）", f"Staff ({len(staff)})")}</summary>'
                 f'<div class="dir-table"><table><tr><th>{t("姓名", "Name")}</th><th>{t("職稱 / 業務", "Title / duties")}</th>'
                 f'<th>{t("分機", "Ext.")}</th><th>Email</th></tr>{rows}</table></div></details>')
    return body


def search_units(units: list[dict], query: str, limit: int = 20) -> list[dict]:
    """依單位名稱、上層單位、人員姓名或業務搜尋。"""
    words = [_norm(w).casefold() for w in query.split() if w.strip()]
    if not words:
        return []
    out = []
    for u in units:
        staff = " ".join(f"{p.get('name') or ''}{p.get('title') or ''}" for p in (u.get("details") or {}).get("people") or [])
        hay = _norm(f"{u.get('parent_name') or ''}{u['name']}{staff}").casefold()
        if all(w in hay for w in words):
            out.append(u)
    out.sort(key=lambda u: not any(w in _norm(u["name"]).casefold() for w in words))  # 名稱直接符合的排前面
    return out[:limit]


CSS = """<style>
.dir-lines{display:flex;flex-wrap:wrap;gap:6px 16px;font-size:.88rem}
.dir-lines a,.dir-table a{color:var(--acc-text)!important}
.dir-people{margin-top:8px;font-size:.85rem}
.dir-people summary{cursor:pointer;font-weight:600;color:var(--acc-text)}
.dir-table{overflow-x:auto;margin-top:6px}
.dir-table table{border-collapse:collapse;width:100%;font-size:.82rem}
.dir-table th,.dir-table td{text-align:left;padding:4px 8px;border-bottom:1px dashed var(--line);vertical-align:top}
.dir-table th{opacity:.65;font-weight:600}
details.dept-info{margin-top:2px}
details.dept-info>summary{cursor:pointer;list-style:none;display:inline-flex;align-items:center;gap:4px;font-weight:400;font-size:.8rem;
  opacity:.65;transition:opacity .15s}
details.dept-info>summary::-webkit-details-marker{display:none}
details.dept-info>summary:hover,details.dept-info[open]>summary{opacity:1;color:var(--acc-text)}
details.dept-info>summary .dept-name{text-decoration:underline dotted;text-underline-offset:3px}
details.dept-info>.dir-box{margin:6px 0 2px;padding:10px 12px;border-radius:10px;background:var(--acc-soft);
  border:1px solid var(--acc-line);font-weight:400;animation:popIn .25s var(--ease) both}
</style>"""
