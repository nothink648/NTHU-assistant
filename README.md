# 🎓 校園助手

## 執行
```bash
pip install -r requirements.txt
streamlit run app.py
```

## 新增功能
1. 複製 `features/_template.py`，改名（如 `todo.py`）並撰寫 `render()`
2. 在 `features/__init__.py` import 並加入 `FEATURES`
3. 重新整理頁面，側邊欄就會出現新功能

## 結構
- `app.py` 入口與導覽　`config.py` 全域設定
- `core/` 共用工具（資料存取）
- `features/` 每個功能一個檔案
- `data/` JSON 資料（考試、班表）
