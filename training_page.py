"""
training_page.py — 訓練紀錄
  Part 1: 新增訓練紀錄(選會員/日期 + 動態動作清單 + 備註 -> 表頭+明細整批寫入)
  Part 2: 進步曲線(待開發)
撈出資料一律 dict(r)；時區用 Asia/Taipei；表頭與明細包成一筆交易。
"""
from datetime import datetime, date

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


def has_checkin_on(member_id, date_str) -> bool:
    """該會員在指定日期(YYYY-MM-DD)當天有沒有到館紀錄。"""
    conn = get_connection()
    row = conn.execute(
        "SELECT 1 FROM check_ins WHERE member_id = ? AND date(check_in_at) = ? LIMIT 1",
        (member_id, date_str),
    ).fetchone()
    conn.close()
    return row is not None


def fetch_progress(member_id, exercise_id):
    """每次訓練該動作的最大重量，按日期排序（給折線圖）。"""
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT ts.training_date AS training_date, MAX(l.weight) AS max_weight
        FROM training_sessions ts
        JOIN training_logs l ON l.training_session_id = ts.training_session_id
        WHERE ts.member_id = ? AND l.exercise_id = ?
        GROUP BY ts.training_session_id
        HAVING max_weight IS NOT NULL
        ORDER BY ts.training_date
        """,
        (member_id, exercise_id),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def detect_stall(progress, recent_days: int = 7, prior_days: int = 28):
    """週間比較式停滯偵測。
    progress: [{training_date, max_weight}, ...]，已按日期由舊到新排序。
    比較「最近一週的最高重量」與「之前三週(7~28天)的最高重量」：
      最近 <= 之前 -> 停滯。
    用『每週取最大』而非單筆，避免被熱身/測試組(如 20kg)誤導同一週的判斷。
    回傳 (is_stall, recent_max, baseline_max)；資料不足回傳 (False, ...)。
    """
    if not progress:
        return (False, None, None)

    latest = date.fromisoformat(progress[-1]["training_date"])
    recent_vals, prior_vals = [], []
    for p in progress:
        days_before = (latest - date.fromisoformat(p["training_date"])).days
        if days_before <= recent_days - 1:        # 0~6 天 = 最近一週
            recent_vals.append(p["max_weight"])
        elif recent_days <= days_before <= prior_days:  # 7~28 天 = 之前三週
            prior_vals.append(p["max_weight"])

    if not recent_vals or not prior_vals:
        return (False, None, None)  # 缺一邊就無法判斷，不輕易示警

    recent_max = max(recent_vals)
    baseline_max = max(prior_vals)
    return (recent_max <= baseline_max, recent_max, baseline_max)


# ==================== 畫面 ====================
def render(user: dict):
    tab_new, tab_progress = st.tabs(["新增訓練紀錄", "進步曲線"])
    with tab_new:
        render_new(user)
    with tab_progress:
        render_progress(user)


def render_new(user: dict):
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

    # 軟性警告：該會員在訓練日期當天沒有到館紀錄（仍允許送出）
    if not has_checkin_on(member_id, training_date.isoformat()):
        st.warning("該會員當日無到館紀錄，請確認是否選錯會員。（仍可送出）")

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


def render_progress(user: dict):
    members = fetch_all_members()
    if not members:
        st.warning("尚無會員。")
        return
    member_by_id = {m["member_id"]: m for m in members}

    exercises = fetch_exercises()
    if not exercises:
        st.warning("尚無動作資料。")
        return
    ex_by_id = {e["exercise_id"]: e for e in exercises}

    c1, c2 = st.columns(2)
    member_id = c1.selectbox(
        "選擇會員", list(member_by_id.keys()),
        format_func=lambda mid: member_by_id[mid]["name"],
        key="progress_member",
    )
    exercise_id = c2.selectbox(
        "選擇動作", list(ex_by_id.keys()),
        format_func=lambda eid: ex_by_id[eid]["name"],
        key="progress_exercise",
    )

    progress = fetch_progress(member_id, exercise_id)
    if not progress:
        st.info("這個會員在這個動作還沒有訓練紀錄。")
        return

    # 停滯偵測（週間比較）
    is_stall, recent_max, baseline_max = detect_stall(progress)
    if is_stall:
        st.warning(
            f"進步停滯，建議調整課表。"
            f"（最近一週最高 {recent_max:g} kg ≤ 前三週最高 {baseline_max:g} kg）"
        )

    # 折線圖（plotly）
    import plotly.graph_objects as go
    dates = [p["training_date"] for p in progress]
    weights = [p["max_weight"] for p in progress]
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=dates, y=weights, mode="lines+markers",
        line=dict(width=3, color="#2563eb"),
        marker=dict(size=9),
        hovertemplate="%{x}<br>%{y:g} kg<extra></extra>",
    ))
    fig.update_layout(
        xaxis_title="訓練日期",
        yaxis_title="最大重量 (公斤)",
        height=420,
        margin=dict(l=10, r=10, t=30, b=10),
    )
    st.plotly_chart(fig, use_container_width=True)

    st.caption(f"共 {len(progress)} 次紀錄，歷史最高 {max(weights):g} kg。")
