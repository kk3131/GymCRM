# 遇到的問題與解法

### 問題 1 — ImportError: cannot import name 'can_see_financials'
**狀況**：修改 auth.py 新增 `can_see_financials()` 後，重啟 Streamlit 仍報 ImportError  
**錯誤訊息**：`ImportError: cannot import name 'can_see_financials' from 'auth' (D:\GymCRM\auth.py)`  
**原因**：Python 的 `__pycache__` 快取了舊版 bytecode，Streamlit 重啟不會強制重新編譯  
**解法**：刪除快取資料夾再重啟
```
Remove-Item -Path "D:\GymCRM\__pycache__" -Recurse -Force
streamlit run app.py
```

### 問題 2 — selectbox 的 sqlite3.Row 無法序列化 + Missing Submit Button
**狀況**：新增會員表單出現兩個錯誤：Missing Submit Button 警告、TypeError  
**錯誤訊息**：`TypeError: cannot pickle 'sqlite3.Row' object`（members_page.py 第 311 行）  
**原因**：`fetch_active_plans()` 回傳的是 sqlite3.Row list，Streamlit 的 selectbox 需要能 pickle 的物件才能序列化進 session state；Row 物件不支援，導致 form 在渲染到 submit button 之前就崩潰，連帶觸發 Missing Submit Button 警告  
**解法**：`fetch_active_plans()` 回傳前加 `[dict(r) for r in rows]`，轉成普通 dict 即可
