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
- 側邊欄「帳號設定」可切換介面語言；按「修改帳號名稱」或「修改密碼」才會展開對應的表單（都需輸入目前密碼，可按「取消」收起）；下方有登出。密碼只存加鹽雜湊（PBKDF2），帳號清單在 `data/users.json`，個人資料在 `data/users/<id>/`（兩者都已加入 .gitignore）
- 忘記密碼目前沒有自助重設；需要時可刪掉 `data/users.json` 裡該帳號的那一筆再重新註冊（個人資料夾仍在，可手動搬回）

## 功能
- 🏠 首頁：依時段隨機挑一句問候語（帶入帳號名稱）、四格速覽 + 今日課程、下一場考試、最近公車（依關注路線）、營業中餐廳；所有分頁都有流動極光背景
- 📆 課表：新增時先選「自動帶入」或「手動輸入」。自動帶入：輸入課號（如 `CS 233601`、`cs233601`、開頭 `CS 2336`）、中英文課名（可只打一部分）或老師，多個關鍵字用空格隔開，一鍵把整門課（老師、學分、教室、所有上課時段）加入課表；手動輸入：先選「選擇已填過的課程」（自動帶入該課資料，加開其他時段）或「手動輸入新課程」，再依學校節次（或自訂時間）填寫
- 📅 考試 / 作業提醒：月曆檢視，月曆上只顯示類型、科目與標題；點日期可直接在那天新增，點項目會放大顯示完整資訊（倒數、地點、考古題）並可修改、連結科目或刪除。月曆右上角有醒目的「新增考試或作業」按鈕，月曆下方可展開倒數清單。新增前先選「考試」或「作業」；考試可填地點與歷屆考古題連結，作業只需截止時間（預設 23:59），都能連結課表科目
- 🍱 校園餐廳：各餐廳營業時間與「現在是否營業」，加上「今天吃什麼」隨機轉盤；資料來自 NTHU Data API 的 `/dining`，每小時自動更新（`data/restaurants.json` 只當離線備份）
- 🍜 我的餐廳：每個人可以按「校園餐廳」頁面轉盤右邊的「新增餐廳」，在跳出的視窗貼上 Google 地圖的店家連結（分享 → 複製連結），加入自己專屬的校外餐廳，只有自己看得到；會出現在「我的餐廳」分頁、轉盤和首頁的「現在營業的餐廳」。設定了 Google Maps API 金鑰時，營業時間、地址、電話、評分、網站、照片都會自動帶入（每 7 天自動更新，也可手動更新）；沒有金鑰時營業時間自己填
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

## Google 地圖店家資料（選用）
「我的餐廳」要自動帶入營業時間，需要 Google Places API (New) 的金鑰：
1. 到 [Google Cloud Console](https://console.cloud.google.com/) 建立專案、綁定帳單（Places API 每月有免費額度，個人使用通常不會超過）
2. 啟用 **Places API (New)**，在「憑證」建立 API 金鑰，建議限制只能呼叫 Places API (New)
3. 在 `.streamlit/secrets.toml`（已加入 .gitignore，不會上傳）加入一行：`GOOGLE_MAPS_API_KEY = "你的金鑰"`；或設定同名環境變數
4. 重新啟動 App

金鑰只在伺服器端使用，不會出現在網頁上；沒設定時這個功能仍可用，只是營業時間要自己填。程式在 `core/places.py`。

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
