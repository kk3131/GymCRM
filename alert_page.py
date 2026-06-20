"""
alert_page.py — 流失預警（管理者限定）
  清單一：高貢獻會員超過兩週未到館
          （F 分數>=3 或 M 分數>=3）且 最近一次到館 > 14 天   ← 與最近性脫鉤
  清單二：進步停滯超過三週
          某動作「最近一週最大重量」未高於「前三週最大重量」
每列：備註輸入框 + 「記錄聯繫」按鈕（寫入 contact_logs），並顯示最近一次聯繫紀錄。
分群/評分重用 rfm_page；停滯重用 training_page。資料一律 dict(r)；時區用 Asia/Taipei。
"""
from datetime import datetime

import streamlit as st

from db import get_connection
from rfm_page import compute_rfm_rows
from training_page import fetch_progress, detect_stall

# 時區：台北
try:
    from zoneinfo import ZoneInfo
    _TZ = ZoneInfo("Asia/Taipei")
except Exception:
    _TZ = None


def _today_str():
    now = datetime.now(_TZ) if _TZ else datetime.now()
    return now.strftime("%Y-%m-%d")


RECENCY_THRESHOLD = 14


# ==================== 資料 ====================
def get_lapsing_high_value(threshold: int = RECENCY_THRESHOLD):
    """高貢獻(F 或 M 分數>=3) 且 最近到館 > threshold 天。與分群脫鉤。"""
    result = []
    for r in compute_rfm_rows():
        is_high_value = r["f_score"] >= 3 or r["m_score"] >= 3
        if (is_high_value
                and r["recency_days"] is not None
                and r["recency_days"] > threshold):
            result.append({
                "member_id": r["member_id"],
                "name": r["name"],
                "last_checkin": r["last_checkin"][:10] if r["last_checkin"] else "—",
                "recency_days": r["recency_days"],
                "segment": r["segment"],
            })
    result.sort(key=lambda x: x["recency_days"], reverse=True)
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
        is_stall, _r, _b = detect_stall(progress)
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


def create_contact_log(member_id, staff_id, alert_type, note):
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO contact_logs(member_id, staff_id, contact_date, alert_type, note) "
            "VALUES (?, ?, ?, ?, ?)",
            (member_id, staff_id, _today_str(), alert_type, note),
        )
        conn.commit()
    finally:
        conn.close()


def fetch_latest_contact(member_id, alert_type):
    conn = get_connection()
    row = conn.execute(
        "SELECT contact_date, note FROM contact_logs "
        "WHERE member_id = ? AND alert_type = ? "
        "ORDER BY contact_date DESC, log_id DESC LIMIT 1",
        (member_id, alert_type),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


# ==================== 畫面 ====================
def _last_contact_caption(member_id, alert_type):
    last = fetch_latest_contact(member_id, alert_type)
    if last:
        note = last["note"] or "（無備註）"
        return f"上次聯繫 {last['contact_date']}：{note}"
    return "尚無聯繫紀錄"


def render(user: dict):
    st.subheader("流失預警")

    flash = st.session_state.pop("alert_flash", None)
    if flash:
        st.success(flash)

    # ========== 清單一 ==========
    st.markdown("#### 1. 高貢獻會員超過兩週未到館")
    st.caption("近一年到館≥12 次 或 消費≥5000 元（高貢獻），且最近一次到館已超過 14 天")
    list1 = get_lapsing_high_value()
    if not list1:
        st.success("目前沒有符合條件的高貢獻會員。")
    else:
        h = st.columns([1.6, 1.4, 1, 1.4, 2.2, 1.1])
        for col, t in zip(h, ["會員", "最近到館", "距今(天)", "分群", "備註", ""]):
            col.markdown(f"**{t}**")
        for m in list1:
            c1, c2, c3, c4, c5, c6 = st.columns([1.6, 1.4, 1, 1.4, 2.2, 1.1])
            c1.write(m["name"])
            c1.caption(_last_contact_caption(m["member_id"], "no_checkin"))
            c2.write(m["last_checkin"])
            c3.write(str(m["recency_days"]))
            c4.write(m["segment"])
            note_key = f"n1_{m['member_id']}"
            note = c5.text_input("備註", key=note_key, label_visibility="collapsed",
                                 placeholder="例如：已電話聯繫")
            if c6.button("記錄聯繫", key=f"b1_{m['member_id']}"):
                create_contact_log(m["member_id"], user["staff_id"], "no_checkin",
                                   (note or "").strip() or None)
                st.session_state.pop(note_key, None)
                st.session_state["alert_flash"] = f"{m['name']} 聯繫紀錄已儲存"
                st.rerun()

    st.divider()

    # ========== 清單二 ==========
    st.markdown("#### 2. 進步停滯超過三週")
    st.caption("某動作最近一週的最大重量，未高於前三週的最大重量")
    list2 = get_stalled()
    if not list2:
        st.success("目前沒有進步停滯的會員。")
    else:
        h = st.columns([1.6, 1.6, 1.6, 2.2, 1.1])
        for col, t in zip(h, ["會員", "停滯動作", "最後訓練日", "備註", ""]):
            col.markdown(f"**{t}**")
        for s in list2:
            c1, c2, c3, c4, c5 = st.columns([1.6, 1.6, 1.6, 2.2, 1.1])
            c1.write(s["member_name"])
            c1.caption(_last_contact_caption(s["member_id"], "plateau"))
            c2.write(s["exercise_name"])
            c3.write(s["last_training_date"])
            note_key = f"n2_{s['member_id']}_{s['exercise_id']}"
            note = c4.text_input("備註", key=note_key, label_visibility="collapsed",
                                 placeholder="例如：已通知教練調整課表")
            if c5.button("記錄聯繫", key=f"b2_{s['member_id']}_{s['exercise_id']}"):
                create_contact_log(s["member_id"], user["staff_id"], "plateau",
                                   (note or "").strip() or None)
                st.session_state.pop(note_key, None)
                st.session_state["alert_flash"] = f"{s['member_name']} 聯繫紀錄已儲存"
                st.rerun()
