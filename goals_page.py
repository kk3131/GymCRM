"""
goals_page.py — 目標達成慶祝
偵測「已達標但尚未標記」的目標，每個顯示慶祝卡片 +「標記為已達成」按鈕。
達標判定：
  lift 目標   -> 該動作歷史最大重量 >= 目標
  weight 目標 -> 依會員 goal_type：減重看「降到」、增肌看「達到」；維持方向不明則略過
資料一律 dict(r)；時區用 Asia/Taipei。
"""
from datetime import datetime

import streamlit as st

from db import get_connection

try:
    from zoneinfo import ZoneInfo
    _TZ = ZoneInfo("Asia/Taipei")
except Exception:
    _TZ = None


def _today_str():
    now = datetime.now(_TZ) if _TZ else datetime.now()
    return now.strftime("%Y-%m-%d")


# ==================== 達標判定 ====================
def _evaluate_goal(conn, g):
    """回傳 (是否達標, 目標描述文字)。"""
    if g["goal_category"] == "lift":
        row = conn.execute(
            "SELECT MAX(l.weight) AS best FROM training_logs l "
            "JOIN training_sessions ts ON ts.training_session_id = l.training_session_id "
            "WHERE ts.member_id = ? AND l.exercise_id = ?",
            (g["member_id"], g["exercise_id"]),
        ).fetchone()
        best = row["best"]
        met = best is not None and best >= g["target_value"]
        return met, f"{g['exercise_name']} 達到 {g['target_value']:g} 公斤"

    # weight 目標：方向看會員的 goal_type
    row = conn.execute(
        "SELECT weight FROM body_measurements "
        "WHERE member_id = ? AND weight IS NOT NULL "
        "ORDER BY measured_date DESC, measurement_id DESC LIMIT 1",
        (g["member_id"],),
    ).fetchone()
    latest = row["weight"] if row else None
    if latest is None:
        return False, ""

    if g["goal_type"] == "lose_weight":
        return latest <= g["target_value"], f"體重降到 {g['target_value']:g} 公斤"
    if g["goal_type"] == "gain_muscle":
        return latest >= g["target_value"], f"體重達到 {g['target_value']:g} 公斤"
    return False, ""  # maintain 或未設定：方向不明，不自動偵測


def detect_pending_celebrations():
    """已達標但 achieved=0 的目標。"""
    conn = get_connection()
    goals = [dict(g) for g in conn.execute(
        """
        SELECT g.goal_id, g.member_id, g.goal_category, g.exercise_id, g.target_value,
               m.name AS member_name, m.goal_type,
               e.name AS exercise_name
        FROM member_goals g
        JOIN members m   ON m.member_id = g.member_id
        LEFT JOIN exercises e ON e.exercise_id = g.exercise_id
        WHERE g.achieved = 0
        ORDER BY m.name
        """
    ).fetchall()]

    result = []
    for g in goals:
        met, desc = _evaluate_goal(conn, g)
        if met:
            result.append({
                "goal_id": g["goal_id"],
                "member_name": g["member_name"],
                "description": desc,
            })
    conn.close()
    return result


def mark_achieved(goal_id):
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE member_goals SET achieved = 1, achieved_date = ? WHERE goal_id = ?",
            (_today_str(), goal_id),
        )
        conn.commit()
    finally:
        conn.close()


# ==================== 畫面 ====================
def render(user: dict):
    st.subheader("目標達成")

    if st.session_state.pop("did_celebrate", False):
        st.balloons()
    flash = st.session_state.pop("celebrate_flash", None)
    if flash:
        st.success(flash)

    pending = detect_pending_celebrations()
    if not pending:
        st.info("目前沒有待慶祝的達標。")
        return

    st.caption(f"有 {len(pending)} 位會員達成目標，別忘了恭喜他們！")
    for p in pending:
        with st.container(border=True):
            st.markdown(f"### 恭喜 {p['member_name']} 達成目標：{p['description']}！")
            if st.button("標記為已達成", key=f"mark_goal_{p['goal_id']}", type="primary"):
                mark_achieved(p["goal_id"])
                st.session_state["did_celebrate"] = True
                st.session_state["celebrate_flash"] = f"已記錄 {p['member_name']} 的達標！"
                st.rerun()