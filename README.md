# 🎓 校園助手

## 執行
```bash
pip install -r requirements.txt
python -m streamlit run app.py
```
建議用 `python -m streamlit`，確保 Streamlit 跑在你安裝套件的那個 Python 上（電腦裡同時有 Anaconda 與一般 Python 時，直接打 `streamlit` 可能會用到另一個版本）。需要 Python 3.9 以上。

## 功能
- 🏠 首頁：下一場考試、最近公車、今日課程
- 📆 課表：依學校節次（或自訂時間）填入課程，可填教授 / 教室 / 學分 / 備註；同一門課第二次起可直接選用
- 📅 考試提醒：新增 / 刪除考試與倒數，可附上歷屆考古題連結
- 🍱 校園餐廳：各餐廳營業時間與「現在是否營業」，加上「今天吃什麼」隨機轉盤；資料來自總務處網頁，頁面底部可一鍵從官網更新（`data/restaurants.json`）
- 🚌 公車班表：綠線、紅線（各分上山 / 下山，頁面以綠色、紅色標示）、往返南大校區的南大線一（經台積館）/ 南大線二（經教育大樓），以及一條校外線；南大線一有假日班次
- 🗺️ 校園地圖：嵌入清華 3D 校園導覽，可直接在頁面裡拖曳、縮放、點選建築物

## 填公車時間
編輯 `data/bus_schedule.json`。每條路線有一到多個「方向」，各自有出發地與時刻表：
```json
{
  "routes": [
    {"name": "綠線", "type": "campus", "color": "#2E9E6A", "directions": [
      {"name": "上山", "origin": "校門口", "weekday": "07:30, 08:00, 08:30"},
      {"name": "下山", "origin": "台積館", "weekday": "07:45, 08:15"}
    ]}
  ]
}
```
- 綠線、紅線：上山（校門口出發）、下山（台積館出發）；校外線只有一個方向
- 南大線一、二：往南大（北校門口出發）、往校本部（南大校區校門口出發），`stops` 為停靠站
- `color`：路線標示顏色（#RRGGBB），綠線 `#2E9E6A`、紅線 `#E5486F`、南大線一 `#2F7FD8`、南大線二 `#9B59D0`
- `weekday` 平日、`weekend` 假日（沒有就省略）；逗號或空格分隔，順序不用排，也可寫成陣列 `["07:30", "08:00"]`
- 時間後可加註記：`10:55♦` 週五停駛（週五自動略過）、`07:30※` 付費市區公車 83 號
- `type`：`campus`（校內）、`offcampus`（校外）或 `nanda`（南大校區）
- 引號與逗號請用半形；寫錯時頁面會顯示提示

## 淺色 / 深色 / 自動
用 Streamlit 內建的主題切換：右上角 ⋮ → Settings → Theme（Light / Dark / Use system setting）。
`.streamlit/config.toml` 刻意不設定 `[theme]`，預設就是跟隨系統（自動）。

## 課表節次
節次與時間定義在 `config.py` 的 `PERIODS`，學校調整時間只要改那裡。
課表資料存在 `data/timetable.json`（自動產生）。

## 新增功能
1. 複製 `features/_template.py`，改名（如 `todo.py`）並撰寫 `render()`
2. 在 `features/__init__.py` import 並加入 `FEATURES`
3. 重新整理頁面，側邊欄就會出現新功能

## 結構
- `app.py` 入口與導覽　`config.py` 全域設定（名稱、節次）
- `.streamlit/config.toml` 主題色
- `core/` 共用工具（`storage.py` 資料存取、`ui.py` 樣式與卡片元件）
- `features/` 每個功能一個檔案
- `data/` JSON 資料（考試、班表、課表）
