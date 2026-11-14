# 🎓 校園助手

## 執行
```bash
pip install -r requirements.txt
python -m streamlit run app.py
```
建議用 `python -m streamlit`，確保 Streamlit 跑在你安裝套件的那個 Python 上（電腦裡同時有 Anaconda 與一般 Python 時，直接打 `streamlit` 可能會用到另一個版本）。需要 Python 3.9 以上。

### 讓外網也能用（開著這台電腦）
雙擊 `start_public.bat`：會啟動 App，並用 [Cloudflare Tunnel](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/do-more-with-tunnels/trycloudflare/) 產生一個 `https://xxxx.trycloudflare.com` 外網網址（自動複製到剪貼簿、存在 `public_url.txt`、並用瀏覽器打開）。
- 需要先安裝一次 cloudflared：`winget install Cloudflare.cloudflared`
- 不用設定路由器或開 port；App 只聽 127.0.0.1，外面的人只能透過這個 HTTPS 網址連進來
- 每次啟動網址都不同；電腦不能睡眠或關機。按任意鍵或關掉視窗就會停止服務
- 執行紀錄在 `logs/`（已加入 .gitignore）

## 帳號
- 第一次開啟會看到登入畫面，先「註冊新帳號」。每個帳號的課表、考試、關注路線都是自己的；公車班表與餐廳資料大家共用
- **第一個註冊的帳號**會自動接收原本放在 `data/` 的課表與考試資料
- 勾選「保持登入」會在瀏覽器存 30 天的登入憑證，重新整理不用再登入；公用電腦請取消勾選並記得登出
- 側邊欄「帳號設定」可切換介面語言、修改帳號名稱（需輸入目前密碼）與密碼；下方有登出。密碼只存加鹽雜湊（PBKDF2），帳號清單在 `data/users.json`，個人資料在 `data/users/<id>/`（兩者都已加入 .gitignore）
- 忘記密碼目前沒有自助重設；需要時可刪掉 `data/users.json` 裡該帳號的那一筆再重新註冊（個人資料夾仍在，可手動搬回）

## 功能
- 🏠 首頁：依時段隨機挑一句問候語（帶入帳號名稱）、四格速覽 + 今日課程、下一場考試、最近公車（依關注路線）、營業中餐廳；所有分頁都有流動極光背景
- 📆 課表：輸入課號、課名或老師搜尋課程資料庫，一鍵把整門課（老師、學分、教室、所有上課時段）加入課表；也可依學校節次（或自訂時間）手動填寫，同一門課第二次起可直接選用
- 📅 考試 / 作業提醒：新增前先選「考試」或「作業」；考試可填地點與歷屆考古題連結，作業只需截止時間（預設 23:59），都有倒數，也都能連結課表科目
- 🍱 校園餐廳：各餐廳營業時間與「現在是否營業」，加上「今天吃什麼」隨機轉盤；資料來自 NTHU Data API 的 `/dining`，每小時自動更新（`data/restaurants.json` 只當離線備份）
- 🚌 公車班表：綠線、紅線（各分上山 / 下山，頁面以綠色、紅色標示）、往返南大校區的南大線一（經台積館）/ 南大線二（經教育大樓）；南大線一有假日班次。頁面上方可選「關注路線」（校本部 / 南大校區 / 全部），首頁只顯示關注的公車。「到站時間」分頁可選自己所在的站點（會記住），列出接下來經過該站的公車、預估抵達時間與沿途各站時間（來自 NTHU Data API，依時刻表推算，非 GPS）
- 🗺️ 校園地圖：嵌入清華 3D 校園導覽，以及 2D 校園道路圖（`static/maps/campus_roads.jpg`，可縮放、拖曳）
- 🗓️ 學校行事曆：清華行事曆與總圖 / 人社 / 南大分館開館日曆，可搜尋、看已結束事件；首頁上方的跑馬燈顯示學校行事曆接下來的一個事件
- 📢 校園公告：各處室、系所網站的最新公告，可依語言、單位、關鍵字篩選；點公告下方的單位名稱會展開該單位的網站、電話、分機、Email 與承辦人員（校園通訊錄），頁面底部也能查詢任何單位或承辦人
- 📚 圖書館：空間即時使用狀況、各館開館時間、圖書館最新消息、失物招領
- 🏀 體育場館：體育館、重訓室、游泳池、網球場等 17 個場館的開放時間表（取自體育室網站的 PDF，自動選出今天適用的學期版本並轉成圖片顯示，需要 `pymupdf`），以及前往體育室場地預約系統的按鈕

## 校園資料 API
行事曆、公告、通訊錄、課程、餐廳、圖書館的資料來自清華學生會的 [NTHU Data API](https://api.nthusa.tw/docs)，存取工具在 `core/nthu_api.py`：
- 各端點有自己的更新頻率（圖書館空間 1 分鐘、公告 30 分鐘、行事曆與餐廳 1 小時、課程與通訊錄 1 天），期間內所有使用者共用同一份資料
- 每次成功抓到資料都會存一份到 `data/api_cache/`（已加入 .gitignore）；API 連不上時改用這份暫存，頁面會提示資料時間

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
- 綠線、紅線：上山（校門口出發）、下山（台積館出發）
- 南大線一、二：往南大（北校門口出發）、往校本部（南大校區校門口出發），`stops` 為停靠站
- `color`：路線標示顏色（#RRGGBB），綠線 `#2E9E6A`、紅線 `#E5486F`、南大線一 `#2F7FD8`、南大線二 `#9B59D0`
- `weekday` 平日、`weekend` 假日（沒有就省略）；逗號或空格分隔，順序不用排，也可寫成陣列 `["07:30", "08:00"]`
- 時間後可加註記：`10:55♦` 週五停駛（週五自動略過）、`07:30※` 付費市區公車 83 號
- `type`：`campus`（校本部）或 `nanda`（南大校區），「關注路線」依此分類；選擇存在 `data/settings.json`
- 引號與逗號請用半形；寫錯時頁面會顯示提示

## 介面語言（中文 / English / Bahasa Indonesia / Tiếng Việt）
在側邊欄「帳號設定 → 介面語言」（未登入時在登入頁右上方）切換，選擇會存在個人設定，下次登入自動套用。
- 程式裡的文字寫成 `t("中文", "English")`（`core/i18n.py`），新增功能時照這個寫法即可
- 印尼文、越南文由英文句子對照翻譯：`core/locales/id.json`、`core/locales/vi.json`（`strings` 整句對照，`templates` 給含變數的 f-string，`{0}`、`{1}` 代表變數）。新增或修改英文句子後記得補上翻譯，沒翻到的會顯示英文
- 外部資料（餐廳名稱、公告標題、圖書館消息等）沒有英文版，維持原文；行事曆有英文標題時，非中文介面以英文顯示
- 校園公告在非中文介面下，語言篩選預設為 English

## 淺色 / 深色 / 自動
用 Streamlit 內建的主題切換：右上角 ⋮ → System / Light / Dark。選單裡的 Print、Record screen、Rerun、Clear cache 已隱藏（`.streamlit/config.toml` 的 `toolbarMode` 與 `core/ui.py` 的 CSS）。
`.streamlit/config.toml` 刻意不設定 `[theme]`，預設就是跟隨系統（自動）。

## 課表節次
節次與時間定義在 `config.py` 的 `PERIODS`，學校調整時間只要改那裡。
課表資料存在各帳號的 `data/users/<id>/timetable.json`（自動產生）。

## 新增功能
1. 複製 `features/_template.py`，改名（如 `todo.py`）並撰寫 `render()`
2. 在 `features/__init__.py` import 並加入 `FEATURES`
3. 重新整理頁面，側邊欄就會出現新功能

## 結構
- `app.py` 入口與導覽　`config.py` 全域設定（名稱、節次）
- `.streamlit/config.toml` 主題色
- `core/` 共用工具（`storage.py` 資料存取、`nthu_api.py` 校園資料 API、`auth.py` 帳號、`login.py` 登入畫面、`ui.py` 樣式與卡片元件）
- `features/` 每個功能一個檔案
- `data/` 共用 JSON 資料（公車班表、餐廳、帳號清單）；`data/users/<id>/` 各帳號的課表、考試、設定
