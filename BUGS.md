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
