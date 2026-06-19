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
