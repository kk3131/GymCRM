"""
alert_page.py — 流失預警（管理者限定）
  清單一：高貢獻會員超過兩週未到館
          RFM 分群為核心/穩定，且最近一次到館 > 14 天
  清單二：進步停滯超過三週
          某動作「最近一週最大重量」未高於「前三週最大重量」
每列附備註欄，讓前台記錄聯繫狀況（目前暫存於 session，未落地資料庫）。
分群邏輯重用 rfm_page；停滯邏輯重用 training_page，維持單一來源。
"""
import streamlit as st

from db import get_connection
from rfm_page import compute_rfm_rows
from training_page import fetch_progress, detect_stall

RECENCY_THRESHOLD = 14


def get_lapsing_high_value(threshold: int = RECENCY_THRESHOLD):
    """核心/穩定會員，但最近到館超過 threshold 天。"""
    result = []
    for r in compute_rfm_rows():
        if (r["segment"] in ("核心會員", "穩定會員")
                and r["recency_days"] is not None
                and r["recency_days"] > threshold):
            result.append({
                "member_id": r["member_id"],
                "name": r["name"],
                "last_checkin": r["last_checkin"][:10] if r["last_checkin"] else "—",
                "recency_days": r["recency_days"],
                "segment": r["segment"],
            })
    result.sort(key=lambda x: x["recency_days"], reverse=True)  # 越久越前面
    return result


def get_stalled():
    """掃描每個(會員, 動作)，回傳進步停滯者。"""
    conn = get_connection()
    pairs = [dict(p) for p in conn.execute(
        """
        SELECT DISTINCT ts.member_id, m.name AS member_name,
               l.exercise_id, e.name AS exercise_name
        FROM training_logs l
        JOIN training_sessions ts ON ts.training_session_id = l.training_session_id
        JOIN members m   ON m.member_id = ts.member_id
        JOIN exercises e ON e.exercise_id = l.exercise_id
        WHERE l.weight IS NOT NULL
        """
    ).fetchall()]
    conn.close()

    result = []
    for p in pairs:
        progress = fetch_progress(p["member_id"], p["exercise_id"])
        is_stall, _recent, _baseline = detect_stall(progress)
        if is_stall:
            result.append({
                "member_id": p["member_id"],
                "member_name": p["member_name"],
                "exercise_id": p["exercise_id"],
                "exercise_name": p["exercise_name"],
                "last_training_date": progress[-1]["training_date"],
            })
    result.sort(key=lambda x: (x["member_name"], x["exercise_name"]))
    return result


def render(user: dict):
    st.subheader("流失預警")

    # ========== 清單一 ==========
    st.markdown("#### 1. 高貢獻會員超過兩週未到館")
    st.caption("RFM 分群為核心／穩定，且最近一次到館已超過 14 天")
    list1 = get_lapsing_high_value()
    if not list1:
        st.success("目前沒有符合條件的高貢獻會員。")
    else:
        h = st.columns([2, 2, 1.3, 1.5, 3])
        for col, t in zip(h, ["會員", "最近到館", "距今(天)", "分群", "備註（聯繫狀況）"]):
            col.markdown(f"**{t}**")
        for m in list1:
            c1, c2, c3, c4, c5 = st.columns([2, 2, 1.3, 1.5, 3])
            c1.write(m["name"])
            c2.write(m["last_checkin"])
            c3.write(str(m["recency_days"]))
            c4.write(m["segment"])
            c5.text_input(
                "備註", key=f"alert1_note_{m['member_id']}",
                label_visibility="collapsed",
                placeholder="例如：已電話聯繫、約下週回來",
            )

    st.divider()

    # ========== 清單二 ==========
    st.markdown("#### 2. 進步停滯超過三週")
    st.caption("某動作最近一週的最大重量，未高於前三週的最大重量")
    list2 = get_stalled()
    if not list2:
        st.success("目前沒有進步停滯的會員。")
    else:
        h = st.columns([2, 2, 2, 3])
        for col, t in zip(h, ["會員", "停滯動作", "最後訓練日", "備註（聯繫狀況）"]):
            col.markdown(f"**{t}**")
        for s in list2:
            c1, c2, c3, c4 = st.columns([2, 2, 2, 3])
            c1.write(s["member_name"])
            c2.write(s["exercise_name"])
            c3.write(s["last_training_date"])
            c4.text_input(
                "備註", key=f"alert2_note_{s['member_id']}_{s['exercise_id']}",
                label_visibility="collapsed",
                placeholder="例如：已通知教練調整課表",
            )

    st.caption("備註目前僅暫存於本次操作（重新整理會清空）。需要永久保存可再加一張聯繫紀錄表。")