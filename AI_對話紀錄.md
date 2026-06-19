# AI 對話紀錄 — 健身房會員管理系統

**專案名稱**：GymCRM 健身房會員管理系統  
**技術選擇**：Python + Streamlit + SQLite  
**部署目標**：Replit  
**開發者**：劉芳妤  
**課程**：MIS 自主學習  

---

## 階段一：需求分析與系統設計

### Prompt 1 — 系統核心概念與功能需求

**我的描述：**
> 把 CRM 套用到健身房情境。功能包含：會員資料管理（個人資料、目標、身體測量紀錄）、課程預約、訓練紀錄（追蹤進步如深蹲 60kg→80kg）、RFM 分析（辨識可能流失的會員）、轉換成本設計（訓練紀錄都在系統裡，換健身房就失去所有紀錄）。目標使用者是健身房前台人員和管理者。

**這個系統跟一般 CRM 的差異：**
- 多了訓練紀錄和身體數據維度
- 轉換成本來自訓練歷史的累積
- 回訪提醒來自課程週期而非消費週期

---

### Prompt 2 — 缺口分析與設計決策

**AI 指出的六個缺口，以及我的決策：**

**缺口一：RFM 的 M（消費）是空心的**  
原系統沒有金流設計，RFM 只能算 R 和 F。  
→ 決策：補上會籍方案（月費制 / 堂數包 / 私教課）、會籍狀態（active / 凍結 / 到期）、M 計算來源為過去一年會籍費用加購課費用。

**缺口二：出席資料怎麼進系統**  
整套 RFM 分析都建立在「知道會員有沒有來」，但簽到方式未定。  
→ 決策：選擇前台手動打卡，技術最簡單，符合後台網頁的設計目標。

**缺口三：三個支柱接成一個迴圈**  
訓練紀錄、流失預警、個人化推薦原本是三個分開的功能，但它們應該是同一件事：  
> 進步停滯 = 最想放棄的時刻 = 轉換成本最弱的時刻 = 最該觸發個人化推薦的時刻  

→ 決策：採納。定義「同一動作連續三週重量沒有進步」為進步停滯，自動觸發流失預警 + 推薦相關課程，三個功能串成一個留存引擎。

**缺口四：銷售漏斗（潛在客戶 → 體驗課 → 轉換）**  
→ 決策：v2 再做，v1 只管已是會員的管理。

**缺口五：溝通管道（提醒要能發得出去）**  
LINE 整合等推播基礎建設。  
→ 決策：v1 先做系統內提醒清單，讓前台看到後手動聯繫，LINE 整合放 v2。

**缺口六：其他結構性問題**  
- 教練角色 → v1 實作，教練可登入輸入訓練紀錄，但不能看財務數據  
- 課程預約細節（候補名單、取消政策）→ v2  
- 管理者儀表板 → v1 包含：出席率、RFM 分布、流失預警清單  
- 個資合規 → 加同意收集資料的勾選框  
- 里程碑慶祝 → v1 包含，達到目標體重或目標重量時系統顯示恭喜訊息  
- 適地性推播 → v2  

---

### Prompt 3 — ER 圖設計與 v1 範圍確認

**AI 提出兩個設計選擇：**

1. `check_ins`（到館簽到）和 `bookings`（課程預約）拆成兩張表  
   → 因為 RFM 的 R 和 F 應來自到館，而非只來自上課，會員可能只用器材不上團課  

2. RFM / 流失預警 / 進步停滯不設計成資料表，而是即時查詢（SELECT）  
   → 每次 Streamlit 載入時跑查詢，避免資料不同步  

**v1 確認的 11 張資料表：**

| 類別 | 資料表 |
|------|--------|
| 會員核心 | members、body_measurements、member_goals |
| 會籍與金流 | membership_plans、memberships、payments |
| 出席 | check_ins |
| 訓練紀錄 | exercises、training_sessions、training_logs |
| 人員 | staff |

**v2 才做的三張表**：classes、class_sessions、bookings（課程預約相關）

---

### Prompt 4 — goal_type 設計決策

**問題背景：**  
我原本想把 `members` 表的 `goal_type` 刪除，統一放在 `member_goals`，認為這樣符合正規化。

**AI 的分析：**  
- `goal_type`（減重 / 增肌 / 維持）是會員的整體方向，一個會員只有一個值  
- `member_goals` 是具體數值里程碑（目標體重 65kg、深蹲目標 100kg），可以有多筆  
- 兩者是不同概念，`goal_type` 放在 `members` 符合 3NF，不是冗餘  
- 如果刪掉，個人化推薦引擎就沒有整體方向可以讀  

**決策：**  
`goal_type` 留在 `members`，與 `member_goals` 分工——前者管方向，後者管數值里程碑。

---

## 階段二：資料庫建置

### Prompt 5 — schema.sql 設計與版本比較

**背景：**  
我自己寫了一版 schema，AI 寫了一版，兩版比較後取各自優點合併。

**我的版本比 AI 好的設計：**
- 日期全用 `TEXT` 存 ISO 格式，SQLite 沒有真正的 DATETIME，這樣最一致
- `is_active` 軟刪除旗標（staff / exercises / membership_plans）——舊的已下架方案還要保留給付款紀錄參考，不能真的刪
- `member_goals` 的 cross-field CHECK 約束：`lift` 目標必須有 `exercise_id`，`weight` 目標不可有 `exercise_id`，直接在 DB 層強制完整性
- `consent_date` 記錄個資同意時間（個資合規需要）
- `staff` 用 `username` 而非 `email` 登入，更有彈性
- `memberships` 不存 `type`，因為可從 `plan_id → membership_plans.type` 查到，存在這裡才是真正的冗餘
- `exercises` 加 `exercise_type`（strength / cardio），決定前端要顯示重量欄位還是時間欄位

**AI 版本補充的兩個欄位：**
- `height_cm` 移到 `members`（不是 `body_measurements`）——成人身高幾乎不變，是會員層級屬性，適合放在 members
- `duration_seconds` 加到 `training_logs`——有氧動作（跑步機、划船機）沒有重量，需要用秒數記錄

**最終 schema 結構（11 張表）：**

| 表名 | 用途 | 關鍵設計 |
|------|------|---------|
| members | 會員基本資料 | goal_type 管方向，height_cm 在此 |
| staff | 員工帳號 | username 登入，password_hash 存雜湊 |
| membership_plans | 會籍方案定義 | is_active 軟刪除 |
| exercises | 動作字典 | exercise_type 區分重訓/有氧 |
| memberships | 會員持有的合約 | sessions_remaining 堂數剩餘 |
| payments | 金流紀錄 | RFM 的 M 來源 |
| check_ins | 到館簽到 | RFM 的 R / F 來源 |
| body_measurements | 身體測量 | 多筆追蹤變化 |
| member_goals | 目標里程碑 | cross-field CHECK 確保資料一致 |
| training_sessions | 一次訓練的表頭 | 連結教練與日期 |
| training_logs | 訓練明細 | 進步停滯偵測的資料來源 |

---

### Prompt 6 — db.py 設計

**功能：**
- `get_connection()` 回傳 SQLite 連線
- 每次連線自動開啟 `PRAGMA foreign_keys = ON`（SQLite 預設不開）
- `row_factory = sqlite3.Row`，查詢結果可用欄位名稱取值（`row["member_id"]`）
- 第一次執行自動讀 `schema.sql` 建表（`CREATE TABLE IF NOT EXISTS` 保證冪等）

**驗證結果：**  
執行 `python seed.py` 成功，資料庫寫入確認：
- 3 個會員，goal_type 正確
- check_ins 89 筆（高貢獻會員密集到館）
- training_logs 18 筆（8 次 session × 平均 2-3 個動作）

---

## 階段三：Streamlit 頁面開發

### Prompt 7 — auth.py 與 app.py 架構設計

**auth.py 設計重點：**

`PAGE_ACCESS` 字典集中管理所有頁面權限，要調整只改這裡：
```python
PAGE_ACCESS = {
    "會員管理":  {"manager", "front_desk"},
    "訓練紀錄":  {"manager", "front_desk", "trainer"},
    "到館簽到":  {"manager", "front_desk"},
    "RFM 分析":  {"manager"},
    "流失預警":  {"manager"},
}
```

`verify_login` 用 bcrypt 比對密碼雜湊，不還原明碼。  
`can_access` 做二次把關，防止直接跳頁繞過側邊欄。

**app.py 設計重點：**
- 用 `st.session_state.user` 保存登入狀態，頁面重跑不會掉
- `st.form` 包住登入輸入，避免每打一個字就觸發重跑
- 登出時 `del st.session_state.user` 再 `st.rerun()`

**三個角色的權限驗證結果：**

| 角色 | 能看的頁面 |
|------|-----------|
| manager | 全部 5 頁 |
| front_desk | 會員管理、訓練紀錄、到館簽到 |
| trainer | 訓練紀錄 |

---

### Prompt 8 — 會員管理頁面（Part 1 列表 + Part 2 新增）

**新增檔案：**
- `members_page.py`：會員列表、詳細頁、新增會員，資料查詢與畫面渲染分開（fetch_* / render_*）
- `labels.py`：資料庫代碼 → 中文對照表，供所有頁面共用

**修改檔案：**
- `auth.py`：補上 `can_see_financials(role)`，前台無法檢視消費紀錄
- `app.py`：會員管理頁接入 `members_page.render(user)`
- `schema.sql` / `seed.py`：移除 `members` 表的 `height_cm`（存了但未顯示的孤兒欄位）

**關鍵設計決策：**

1. **會籍狀態「算出來的」**：一個會員可能有多筆會籍，列表用優先序 active > frozen > expired 取代表值；詳細頁列出全部
2. **列表用 st.columns 而非 st.dataframe**：dataframe 無法在格子裡放按鈕，彩色狀態膠囊也需要 HTML
3. **頁面切換靠 session_state**：`view_member_id`（詳細頁）和 `member_add_mode`（新增頁）控制顯示哪個畫面
4. **三表原子交易**：新增會員時 members + memberships + payments 包在同一個 transaction，失敗全部 rollback，不會留半套資料
5. **財務資料權限**：歷史消費紀錄用 `can_see_financials()` 擋前台，前台看到「無檢視權限」字樣

---

### Prompt 9 — 到館簽到頁面（checkin_page.py）


**新增檔案：**
- `checkin_page.py`：搜尋會員 → 登記到館 → 今日到館清單

**修改檔案：**
- `app.py`：加入 `import checkin_page`，到館簽到頁接入 `checkin_page.render(user)`

**功能流程：**
1. 搜尋框輸入姓名關鍵字
2. 結果列出，每人一個「登記到館」按鈕
3. 按下 → `check_ins` 寫入一筆（member_id / 現在時間 / staff_id）
4. 成功提示「XXX 到館登記完成」並 rerun
5. 頁面下方顯示今日到館清單（時間 / 會員 / 登記人）

**設計重點：**
- **時區處理**：優先用 `zoneinfo.ZoneInfo("Asia/Taipei")` 取台北時間，避免伺服器在 UTC 環境記錯時間；若系統缺 tzdata 則 fallback 到本地時間
- **sqlite3.Row 問題**：所有 `fetchall()` 結果一律 `[dict(r) for r in rows]`，沿用問題 2 的教訓

### Prompt 10 — members_page 更新：最近訓練紀錄 + selectbox 序列化根本修正

**修改檔案：**
- `members_page.py`

**新增功能：**
- 會員詳細頁底部加入「最近訓練紀錄」區塊，顯示最近 5 次訓練，每次展開為動作明細（動作 / 重量 / 組數 / 次數）

**新增函式：**
- `fetch_recent_trainings(member_id, limit)`：用子查詢取最近 N 個 session_id，再 JOIN training_logs + exercises 一次撈完所有明細，Python 端按 session 分組渲染，避免 N+1 查詢

**問題 2 根本修正（selectbox 序列化）：**
舊版是在 `fetch_active_plans()` 回傳前轉 dict，但 dict 放進 selectbox 仍可能有序列化疑慮。
新版改成 selectbox 選項只放純整數 `plan_id`，`format_func` 從 `plan_by_id` 字典查顯示文字，送出後再由 `plan_id` 取回完整方案 dict——selectbox 從頭到尾只存整數，徹底避開序列化問題。

---

### Prompt 11 — 訓練紀錄頁面 Part 1（training_page.py 初版）

**新增檔案：**
- `training_page.py`：新增訓練紀錄（Part 1），進步曲線待開發（Part 2）

**修改檔案：**
- `app.py`：加入 `import training_page`，訓練紀錄頁接入 `training_page.render(user)`

**功能流程：**
1. 選會員 + 訓練日期
2. 動作清單：用小表單（`clear_on_submit=True`）逐筆加入，每筆顯示動作 / 重量 / 組數 / 次數，可移除
3. 填備註（選填）
4. 送出 → `training_sessions`（表頭）+ `training_logs`（每個動作）包成一筆交易寫入
5. 成功清空動作清單，顯示提示

**設計重點：**
- **購物車模式**：動作清單存在 `session_state["training_cart"]`，用小表單逐筆加入，不需一次填完再送出，符合實際在教練旁邊一組一組記的使用情境
- **表單與送出按鈕分離**：「加入動作」用 `st.form`，「送出訓練紀錄」是表單外的按鈕，兩個操作互不干擾
- **兩層原子交易**：`training_sessions` + `training_logs` 包成一筆 transaction，任一動作明細失敗就整批 rollback

### Prompt 13 — RFM 分析頁面（rfm_page.py）

**新增檔案：**
- `rfm_page.py`：RFM 分析（管理者限定）

**修改檔案：**
- `app.py`：加入 `import rfm_page`，RFM 分析頁接入 `rfm_page.render(user)`

**RFM 計算邏輯：**
- **R（Recency）**：最近一次到館距今天數，1~5 分（≤7 天=5，≤14=4，≤30=3，≤60=2，其餘=1）
- **F（Frequency）**：近一年到館次數（≥52=5，≥26=4，≥12=3，≥4=2，其餘=1）
- **M（Monetary）**：近一年消費金額（≥20000=5，≥10000=4，≥5000=3，≥2000=2，其餘=1）

**分群規則（R 優先）：**
- R≤2 → 流失風險（不管 FM 多高，太久沒來就是危險）
- R≥4 且 F≥4 → 核心會員
- F≥3 → 穩定會員
- 其餘 → 一般會員

**畫面：**
- 頂部 4 格 metric 顯示各分群人數
- 明細表按總分高到低排序，欄位：最近到館天數 / 近一年次數 / 消費 / R/F/M 分 / 總分 / 分群

**設計重點：**
- 評分門檻集中在模組頂部，方便日後調整（不散落在查詢 SQL 裡）
- `segment()` 以 R 優先判斷，反映健身房場景：到館頻率才是黏著度的核心訊號，消費金額可以一次付清但人已經不來了

---

### Prompt 12 — 訓練紀錄頁面 Part 2：進步曲線 + 停滯偵測

**修改檔案：**
- `training_page.py`

**新增檔案：**
- `requirements.txt`：`streamlit` / `bcrypt` / `plotly`

**新增功能：**
- `render()` 改用 `st.tabs` 拆成「新增訓練紀錄」和「進步曲線」兩個 tab
- 「進步曲線」tab：選會員 + 動作，顯示每次訓練最大重量的折線圖（plotly），並在停滯時顯示警告

**新增函式：**
- `fetch_progress(member_id, exercise_id)`：每次訓練取 `MAX(weight)`，按日期排序，給折線圖使用
- `detect_stall(progress)`：週間比較式停滯偵測。比較「最近一週最高重量」與「前三週最高重量」，最近 ≤ 之前則判定停滯。用每週取最大而非單筆，避免熱身組或測試組重量誤觸警告
- `has_checkin_on(member_id, date_str)`：新增訓練時軟性提示，當日無到館紀錄會顯示警告但仍可送出

**設計重點：**
- **停滯偵測邏輯**：只在兩邊都有資料才判斷，缺一邊回傳 False，不輕易誤報
- **plotly 延遲 import**：`import plotly.graph_objects as go` 放在 `render_progress()` 內，只有實際進入進步曲線 tab 才載入，避免啟動時多一個 import
- **停滯 → 流失預警的串聯設計**（為後續 RFM 頁面預留）：進步停滯是「最想放棄的時刻 = 轉換成本最弱的時刻」，未來 RFM 流失預警會把停滯狀態納入計算

---

## 遇到的問題與解法

### 問題 1 — ImportError: cannot import name 'can_see_financials'
**狀況**：修改 auth.py 新增 `can_see_financials()` 後，重啟 Streamlit 仍報 ImportError，但檔案內容已正確  
**錯誤訊息**：`ImportError: cannot import name 'can_see_financials' from 'auth' (D:\GymCRM\auth.py)`  
**原因**：Python 的 `__pycache__` 快取了舊版 bytecode，Streamlit 重啟不會強制重新編譯  
**解法**：刪除快取資料夾再重啟
```powershell
Remove-Item -Path "D:\GymCRM\__pycache__" -Recurse -Force
streamlit run app.py
```

### 問題 3 — ModuleNotFoundError: No module named 'plotly'
**狀況**：進入訓練紀錄頁面即報錯，即使 import 放在函式內部（lazy import）也無法避免  
**錯誤訊息**：`ModuleNotFoundError: No module named 'plotly'`  
**原因**：plotly 尚未安裝。另外，`import plotly` 雖放在 `render_progress()` 內，但 Streamlit 的 `st.tabs` 每次 render 會執行所有 tab 的內容，不是只跑當前 tab，所以只要進訓練紀錄頁，`render_progress()` 就一定被呼叫，plotly 必須安裝  
**解法**：
```
pip install plotly
```
裝完重啟 `streamlit run app.py`

---

### 問題 2 — selectbox 傳入 sqlite3.Row 導致 TypeError + Missing Submit Button
**狀況**：進入新增會員頁面，同時出現兩個錯誤  
**錯誤訊息**：
```
TypeError: cannot pickle 'sqlite3.Row' object
Missing Submit Button（Streamlit 警告）
```
**原因**：`fetch_active_plans()` 回傳 sqlite3.Row list，Streamlit 的 selectbox 渲染時會對選項做 `deepcopy`，但 sqlite3.Row 是 C extension 物件，不支援 pickle。form 在到達 `st.form_submit_button()` 之前就崩潰，才同時觸發兩個錯誤（根本原因只有一個）  
**解法**：`fetch_active_plans()` 回傳前轉成 dict list，修改後仍需清除 `__pycache__` 才會生效
```python
return [dict(r) for r in rows]
```
