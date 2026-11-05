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
- 🚌 公車班表：兩條校內線 + 一條校外線，同一個出發地

## 填公車時間
編輯 `data/bus_schedule.json`：
```json
{
  "origin": "校門口",
  "routes": [
    {"name": "校內線 1", "type": "campus", "weekday": "07:30, 08:00, 08:30", "weekend": "09:00, 10:00"}
  ]
}
```
- `weekday` 平日、`weekend` 假日；逗號或空格分隔，順序不用排，也可寫成陣列 `["07:30", "08:00"]`
- `type`：`campus`（校內）或 `offcampus`（校外）
- 引號與逗號請用半形；寫錯時頁面會顯示提示

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
