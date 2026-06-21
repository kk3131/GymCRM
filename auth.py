"""
auth.py — 登入驗證與角色權限
權限集中管理：要調整哪個角色看得到哪一頁，只改 PAGE_ACCESS 這張表即可。
"""
import bcrypt
from db import get_connection

# 頁面 -> 允許看到的角色
# manager 看全部；front_desk 看不到財務(RFM/流失預警)；trainer 只看訓練相關
PAGE_ACCESS = {
    "🎮 ADVENTURE MAP": {"manager", "front_desk", "trainer"},
    "🗺️ DASHBOARD":     {"manager"},
    "🏠 PLAYER SELECT": {"manager", "front_desk"},
    "💪 TRAINING LOG":  {"manager", "front_desk", "trainer"},
    "📋 CHECK IN":      {"manager", "front_desk"},
    "🏆 GOALS":         {"manager", "front_desk", "trainer"},
    "📊 STATS":         {"manager"},
    "⚠️ DANGER ZONE":   {"manager"},
}

# 角色代碼 -> 中文顯示
ROLE_LABELS = {"manager": "管理者", "front_desk": "前台", "trainer": "教練"}


def verify_login(username: str, password: str):
    """驗證帳密。成功回傳 user dict，失敗回傳 None。"""
    conn = get_connection()
    row = conn.execute(
        "SELECT staff_id, name, role, password_hash, is_active FROM staff WHERE username = ?",
        (username,),
    ).fetchone()
    conn.close()

    if row is None or not row["is_active"]:
        return None
    # bcrypt 比對：把使用者輸入的明碼跟資料庫的雜湊比，絕不還原雜湊
    hashed = row["password_hash"]
    if isinstance(hashed, str):          # 可能是 str 也可能是 bytes，統一成 bytes
        hashed = hashed.encode("utf-8")
    if bcrypt.checkpw(password.encode("utf-8"), hashed):
        return {"staff_id": row["staff_id"], "name": row["name"], "role": row["role"]}
    return None


def pages_for_role(role: str):
    """回傳這個角色能看到的頁面清單（依 PAGE_ACCESS 定義的順序）。"""
    return [page for page, roles in PAGE_ACCESS.items() if role in roles]


def can_access(role: str, page: str) -> bool:
    """單獨檢查某角色能否進某頁（防止直接跳頁繞過側邊欄）。"""
    return role in PAGE_ACCESS.get(page, set())


def can_see_financials(role: str) -> bool:
    """能否檢視財務資料（消費紀錄、金額）。前台看不到。"""
    return role == "manager"