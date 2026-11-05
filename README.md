# 🎓 校園助手

## 執行
```bash
pip install -r requirements.txt
streamlit run app.py
```

## 功能
- 🏠 首頁：下一場考試、最近公車、今日課程
- 📆 課表：依學校節次（或自訂時間）填入課程，可填教授 / 教室 / 學分 / 備註；同一門課第二次起可直接選用
- 📅 考試提醒：新增 / 刪除考試與倒數
- 🚌 公車班表：兩條校內線（上山 / 下山）+ 一條校外線，目前僅平日

## 填公車時間
編輯 `data/bus_schedule.json`。每條路線有一到多個「方向」，各自有出發地與時刻表：
```json
{
  "routes": [
    {"name": "校內線 1", "type": "campus", "directions": [
      {"name": "上山", "origin": "校門口", "weekday": "07:30, 08:00, 08:30"},
      {"name": "下山", "origin": "台積館", "weekday": "07:45, 08:15"}
    ]}
  ]
}
```
- 校內線：上山（校門口出發）、下山（台積館出發）；校外線只有一個方向
- `weekday` 平日；逗號或空格分隔，順序不用排，也可寫成陣列 `["07:30", "08:00"]`
- `type`：`campus`（校內）或 `offcampus`（校外）
- 目前公車只有平日；之後要加假日，在 `features/bus_schedule.py` 的 `SERVICE_DAYS` 加一行，並在各方向補 `weekend`
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
