"""
checkin_page.py — 到館簽到（前台手動打卡）
  1. 搜尋會員姓名
  2. 結果列出，每人一個「登記到館」按鈕
  3. 按下 -> check_ins 新增一筆(member_id / 現在時間 / 登記的 staff_id)
  4. 成功提示「XXX 到館登記完成」
  5. 頁面下方顯示今日到館清單
撈出的資料一律 dict(r)，避免 sqlite3.Row 序列化問題。
"""
from datetime import datetime

import streamlit as st

from db import get_connection

# 時區：用台北時間取「現在」與「今天」，避免伺服器在 UTC 時記錯時間
try:
    from zoneinfo import ZoneInfo
    _TZ = ZoneInfo("Asia/Taipei")
except Exception:
    _TZ = None  # 萬一系統缺 tzdata，退回伺服器本地時間


def _now():
    return datetime.now(_TZ) if _TZ else datetime.now()


def now_str() -> str:
    return _now().strftime("%Y-%m-%d %H:%M:%S")


def today_str() -> str:
    return _now().strftime("%Y-%m-%d")


# ==================== 資料 ====================
def search_members(search: str):
    conn = get_connection()
    rows = conn.execute(
        "SELECT member_id, name, phone FROM members "
        "WHERE name LIKE '%' || ? || '%' ORDER BY name",
        (search,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def create_checkin(member_id: int, staff_id: int):
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO check_ins(member_id, check_in_at, checked_in_by) VALUES (?, ?, ?)",
            (member_id, now_str(), staff_id),
        )
        conn.commit()
    finally:
        conn.close()


def fetch_today_checkins():
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT c.check_in_at, m.name AS member_name, s.name AS staff_name
        FROM check_ins c
        JOIN members m ON m.member_id = c.member_id
        LEFT JOIN staff s ON s.staff_id = c.checked_in_by
        WHERE date(c.check_in_at) = ?
        ORDER BY c.check_in_at DESC
        """,
        (today_str(),),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ==================== 畫面 ====================
def render(user: dict):
    st.subheader("到館簽到")

    # 登記成功的提示（按鈕觸發 rerun 後顯示）
    flash = st.session_state.pop("checkin_flash", None)
    if flash:
        st.success(flash)

    # --- 搜尋並登記 ---
    search = st.text_input("搜尋會員姓名", placeholder="輸入姓名…", key="checkin_search")
    if search.strip():
        members = search_members(search.strip())
        if not members:
            st.info("查無符合的會員。")
        else:
            for m in members:
                c1, c2, c3 = st.columns([3, 2, 1.5])
                c1.write(m["name"])
                c2.write(m["phone"] or "—")
                if c3.button("登記到館", key=f"checkin_{m['member_id']}"):
                    create_checkin(m["member_id"], user["staff_id"])
                    st.session_state["checkin_flash"] = f"{m['name']} 到館登記完成"
                    st.rerun()
    else:
        st.caption("輸入姓名搜尋會員後登記到館。")

    # --- 今日到館清單 ---
    st.divider()
    st.subheader("今日到館清單")
    rows = fetch_today_checkins()
    if rows:
        st.dataframe(
            [{
                "時間": r["check_in_at"][11:16],          # HH:MM
                "會員": r["member_name"],
                "登記人": r["staff_name"] or "—",
            } for r in rows],
            hide_index=True, use_container_width=True,
        )
        st.caption(f"今日到館 {len(rows)} 人次")
    else:
        st.caption("今天還沒有人到館。")
