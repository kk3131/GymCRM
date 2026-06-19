"""
training_page.py — 訓練紀錄
  Part 1: 新增訓練紀錄(選會員/日期 + 動態動作清單 + 備註 -> 表頭+明細整批寫入)
  Part 2: 進步曲線(待開發)
撈出資料一律 dict(r)；時區用 Asia/Taipei；表頭與明細包成一筆交易。
"""
from datetime import datetime

import streamlit as st

from db import get_connection

# 時區：台北
try:
    from zoneinfo import ZoneInfo
    _TZ = ZoneInfo("Asia/Taipei")
except Exception:
    _TZ = None


def _now():
    return datetime.now(_TZ) if _TZ else datetime.now()


def today_date():
    return _now().date()


# ==================== 資料 ====================
def fetch_all_members():
    conn = get_connection()
    rows = conn.execute(
        "SELECT member_id, name, phone FROM members ORDER BY name"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def fetch_exercises():
    conn = get_connection()
    rows = conn.execute(
        "SELECT exercise_id, name, exercise_type, category "
        "FROM exercises WHERE is_active = 1 ORDER BY exercise_id"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def create_training(member_id, trainer_id, training_date, notes, items):
    """表頭(training_sessions) + 每個動作明細(training_logs) 包成一筆交易。"""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO training_sessions(member_id, trainer_id, training_date, notes) "
            "VALUES (?, ?, ?, ?)",
            (member_id, trainer_id, training_date, notes),
        )
        session_id = cur.lastrowid
        for it in items:
            cur.execute(
                "INSERT INTO training_logs(training_session_id, exercise_id, weight, sets, reps) "
                "VALUES (?, ?, ?, ?, ?)",
                (session_id, it["exercise_id"], it["weight"], it["sets"], it["reps"]),
            )
        conn.commit()
        return session_id
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ==================== 畫面 ====================
def render(user: dict):
    st.subheader("新增訓練紀錄")

    if "training_cart" not in st.session_state:
        st.session_state["training_cart"] = []

    flash = st.session_state.pop("training_flash", None)
    if flash:
        st.success(flash)

    members = fetch_all_members()
    if not members:
        st.warning("尚無會員，無法新增訓練紀錄。")
        return
    member_by_id = {m["member_id"]: m for m in members}

    exercises = fetch_exercises()
    if not exercises:
        st.warning("尚無動作資料，請先在 exercises 建立動作。")
        return
    ex_by_id = {e["exercise_id"]: e for e in exercises}

    # 1. 選會員
    member_id = st.selectbox(
        "選擇會員",
        list(member_by_id.keys()),
        format_func=lambda mid: f"{member_by_id[mid]['name']}（{member_by_id[mid]['phone'] or '—'}）",
        key="training_member",
    )

    # 2. 訓練日期
    training_date = st.date_input("訓練日期", value=today_date(), key="training_date")

    # 3. 動作清單
    st.markdown("**動作清單**")
    cart = st.session_state["training_cart"]
    if cart:
        h = st.columns([3, 2, 1.5, 1.5, 1.2])
        for col, t in zip(h, ["動作", "重量", "組數", "次數", ""]):
            col.markdown(f"**{t}**")
        for i, it in enumerate(cart):
            c1, c2, c3, c4, c5 = st.columns([3, 2, 1.5, 1.5, 1.2])
            c1.write(ex_by_id.get(it["exercise_id"], {}).get("name", "?"))
            c2.write(f"{it['weight']:g} kg")
            c3.write(f"{it['sets']} 組")
            c4.write(f"{it['reps']} 次")
            if c5.button("移除", key=f"rm_{i}"):
                cart.pop(i)
                st.rerun()
    else:
        st.caption("尚未加入動作，用下方欄位加入。")

    # 加動作的小表單（送出後自動清空，方便連續輸入）
    with st.form("add_exercise_form", clear_on_submit=True):
        f1, f2, f3, f4 = st.columns([3, 2, 1.5, 1.5])
        ex_id = f1.selectbox("動作", list(ex_by_id.keys()),
                             format_func=lambda eid: ex_by_id[eid]["name"])
        weight = f2.number_input("重量(kg)", min_value=0.0, value=20.0, step=2.5)
        sets = f3.number_input("組數", min_value=1, value=3, step=1)
        reps = f4.number_input("次數", min_value=1, value=8, step=1)
        add = st.form_submit_button("＋ 加入動作")
    if add:
        st.session_state["training_cart"].append({
            "exercise_id": ex_id,
            "weight": float(weight),
            "sets": int(sets),
            "reps": int(reps),
        })
        st.rerun()

    # 4. 備註
    notes = st.text_area("備註（選填）", key="training_notes")

    # 5. 送出
    st.divider()
    if st.button("送出訓練紀錄", type="primary"):
        if not cart:
            st.error("請至少加入一個動作。")
            return
        n = len(cart)
        member_name = member_by_id[member_id]["name"]
        try:
            create_training(
                member_id, user["staff_id"],
                training_date.isoformat(), notes.strip() or None,
                list(cart),
            )
        except Exception as e:
            st.error(f"新增失敗，已全部撤銷：{e}")
            return
        st.session_state["training_cart"] = []
        st.session_state["training_flash"] = f"訓練紀錄新增完成：{member_name}（{n} 個動作）"
        st.rerun()
