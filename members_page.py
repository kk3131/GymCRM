"""
members_page.py — 會員管理
  Part 1: 列表(搜尋 + 彩色狀態 + 查看詳細) + 會員詳細
  Part 2: 新增會員(基本資料 + 選方案 + 付款方式 + 個資同意)
資料查詢與畫面渲染分開：fetch_*/create_* 為純邏輯，render_* 負責畫面。
"""
from datetime import date, timedelta

import streamlit as st

from db import get_connection
from auth import can_see_financials
from labels import (
    GOAL_LABELS, GENDER_LABELS, STATUS_LABELS, STATUS_COLORS,
    PLAN_TYPE_LABELS, PAYMENT_TYPE_LABELS, METHOD_LABELS,
)

# 方案類型 -> 對應的付款項目代碼
PLAN_TYPE_TO_PAYMENT = {
    "monthly": "membership_fee",
    "class_pack": "add_on_class",
    "personal_training": "personal_training",
}


# ==================== 資料查詢 ====================
def fetch_members(search: str = ""):
    """所有會員 + 代表性會籍狀態（優先序 active > frozen > expired）。"""
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT m.member_id, m.name, m.phone, m.join_date,
               (SELECT ms.status FROM memberships ms
                 WHERE ms.member_id = m.member_id
                 ORDER BY CASE ms.status
                            WHEN 'active'  THEN 1
                            WHEN 'frozen'  THEN 2
                            WHEN 'expired' THEN 3
                            ELSE 4 END
                 LIMIT 1) AS status
        FROM members m
        WHERE m.name LIKE '%' || ? || '%'
        ORDER BY m.name
        """,
        (search,),
    ).fetchall()
    conn.close()
    return rows


def fetch_member(member_id: int):
    conn = get_connection()
    row = conn.execute("SELECT * FROM members WHERE member_id = ?", (member_id,)).fetchone()
    conn.close()
    return row


def fetch_memberships(member_id: int):
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT ms.status, ms.start_date, ms.end_date, ms.sessions_remaining,
               p.name AS plan_name, p.type AS plan_type
        FROM memberships ms
        JOIN membership_plans p ON p.plan_id = ms.plan_id
        WHERE ms.member_id = ?
        ORDER BY CASE ms.status WHEN 'active' THEN 1 WHEN 'frozen' THEN 2 ELSE 3 END,
                 ms.start_date DESC
        """,
        (member_id,),
    ).fetchall()
    conn.close()
    return rows


def fetch_payments(member_id: int):
    conn = get_connection()
    rows = conn.execute(
        "SELECT payment_date, payment_type, amount, method "
        "FROM payments WHERE member_id = ? ORDER BY payment_date DESC",
        (member_id,),
    ).fetchall()
    conn.close()
    return rows


def fetch_checkins(member_id: int, limit: int = 10):
    conn = get_connection()
    rows = conn.execute(
        "SELECT check_in_at FROM check_ins WHERE member_id = ? "
        "ORDER BY check_in_at DESC LIMIT ?",
        (member_id, limit),
    ).fetchall()
    conn.close()
    return rows


def fetch_recent_trainings(member_id: int, limit: int = 5):
    """最近 N 次訓練的所有動作明細（JOIN sessions + logs + exercises）。"""
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT ts.training_session_id, ts.training_date,
               e.name AS exercise_name, l.weight, l.sets, l.reps
        FROM training_sessions ts
        JOIN training_logs l ON l.training_session_id = ts.training_session_id
        JOIN exercises e      ON e.exercise_id = l.exercise_id
        WHERE ts.training_session_id IN (
            SELECT training_session_id FROM training_sessions
            WHERE member_id = ?
            ORDER BY training_date DESC, training_session_id DESC
            LIMIT ?
        )
        ORDER BY ts.training_date DESC, ts.training_session_id DESC, l.log_id
        """,
        (member_id, limit),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def fetch_active_plans():
    conn = get_connection()
    rows = conn.execute(
        "SELECT plan_id, name, type, price, duration_days, session_count "
        "FROM membership_plans WHERE is_active = 1 ORDER BY plan_id"
    ).fetchall()
    conn.close()
    return rows


def create_member(name, gender, birth_date, phone, email, goal_type, plan, method, staff_id):
    """一筆交易同時建立 members + memberships + payments；任一失敗全部回滾。"""
    today = date.today().isoformat()

    # 依方案類型決定會籍與付款內容
    if plan["type"] == "monthly":
        end_date = (date.today() + timedelta(days=plan["duration_days"])).isoformat() if plan["duration_days"] else None
        sessions = None
    else:  # class_pack / personal_training
        end_date = None
        sessions = plan["session_count"]
    payment_type = PLAN_TYPE_TO_PAYMENT[plan["type"]]

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO members(name,gender,birth_date,phone,email,goal_type,"
            "join_date,consent_data_collection,consent_date) VALUES (?,?,?,?,?,?,?,?,?)",
            (name, gender, birth_date, phone, email, goal_type, today, 1, today),
        )
        member_id = cur.lastrowid

        cur.execute(
            "INSERT INTO memberships(member_id,plan_id,status,start_date,end_date,sessions_remaining) "
            "VALUES (?,?,?,?,?,?)",
            (member_id, plan["plan_id"], "active", today, end_date, sessions),
        )
        membership_id = cur.lastrowid

        cur.execute(
            "INSERT INTO payments(member_id,membership_id,staff_id,amount,payment_type,payment_date,method) "
            "VALUES (?,?,?,?,?,?,?)",
            (member_id, membership_id, staff_id, plan["price"], payment_type, today, method),
        )
        conn.commit()           # 三筆一起提交
        return member_id
    except Exception:
        conn.rollback()         # 任一步出錯就整批撤銷，不會留半套資料
        raise
    finally:
        conn.close()


# ==================== 畫面 ====================
def status_badge(status) -> str:
    label = STATUS_LABELS.get(status, "無會籍")
    color = STATUS_COLORS.get(status, "#6b7280")
    return (
        f'<span style="background:{color};color:#fff;padding:2px 10px;'
        f'border-radius:12px;font-size:0.8rem;white-space:nowrap;">{label}</span>'
    )


def render(user: dict):
    """入口：新增模式 > 詳細模式 > 列表。"""
    if st.session_state.get("member_add_mode"):
        render_add(user)
    elif st.session_state.get("view_member_id"):
        render_detail(user, st.session_state["view_member_id"])
    else:
        render_list(user)


def render_list(user: dict):
    # 操作成功後的提示（從新增頁帶回來）
    flash = st.session_state.pop("flash", None)
    if flash:
        st.success(flash)

    col_search, col_add = st.columns([3, 1])
    search = col_search.text_input("搜尋會員姓名", placeholder="輸入姓名關鍵字…")
    col_add.write("")  # 對齊用
    if col_add.button("＋ 新增會員", use_container_width=True):
        st.session_state["member_add_mode"] = True
        st.rerun()

    members = fetch_members(search.strip())
    st.caption(f"共 {len(members)} 位會員")

    if not members:
        st.info("查無符合的會員。")
        return

    header = st.columns([2, 2, 2, 1.5, 1.3])
    for col, title in zip(header, ["姓名", "電話", "加入日期", "會籍狀態", ""]):
        col.markdown(f"**{title}**")
    st.divider()

    for m in members:
        c1, c2, c3, c4, c5 = st.columns([2, 2, 2, 1.5, 1.3])
        c1.write(m["name"])
        c2.write(m["phone"] or "—")
        c3.write(m["join_date"])
        c4.markdown(status_badge(m["status"]), unsafe_allow_html=True)
        if c5.button("查看詳細", key=f"view_{m['member_id']}"):
            st.session_state["view_member_id"] = m["member_id"]
            st.rerun()


def render_detail(user: dict, member_id: int):
    member = fetch_member(member_id)

    if st.button("← 返回列表"):
        del st.session_state["view_member_id"]
        st.rerun()

    if member is None:
        st.error("找不到此會員。")
        return

    st.header(member["name"])

    # --- 基本資料 ---
    st.subheader("基本資料")
    c1, c2 = st.columns(2)
    c1.write(f"**性別**：{GENDER_LABELS.get(member['gender'], '—')}")
    c1.write(f"**生日**：{member['birth_date'] or '—'}")
    c1.write(f"**目標**：{GOAL_LABELS.get(member['goal_type'], '—')}")
    c2.write(f"**電話**：{member['phone'] or '—'}")
    c2.write(f"**Email**：{member['email'] or '—'}")
    c2.write(f"**加入日期**：{member['join_date']}")
    c2.write(f"**個資同意**：{'已同意' if member['consent_data_collection'] else '未同意'}")

    # --- 目前會籍 ---
    st.subheader("目前會籍")
    ms = fetch_memberships(member_id)
    if ms:
        st.dataframe(
            [{
                "方案": r["plan_name"],
                "類型": PLAN_TYPE_LABELS.get(r["plan_type"], r["plan_type"]),
                "狀態": STATUS_LABELS.get(r["status"], r["status"]),
                "開始": r["start_date"],
                "結束": r["end_date"] or "—",
                "剩餘堂數": r["sessions_remaining"] if r["sessions_remaining"] is not None else "—",
            } for r in ms],
            hide_index=True, use_container_width=True,
        )
    else:
        st.caption("尚無會籍紀錄。")

    # --- 歷史消費紀錄（財務，僅管理者）---
    st.subheader("歷史消費紀錄")
    if can_see_financials(user["role"]):
        pays = fetch_payments(member_id)
        if pays:
            st.dataframe(
                [{
                    "日期": r["payment_date"],
                    "項目": PAYMENT_TYPE_LABELS.get(r["payment_type"], r["payment_type"]),
                    "金額": int(r["amount"]),
                    "方式": METHOD_LABELS.get(r["method"], r["method"] or "—"),
                } for r in pays],
                hide_index=True, use_container_width=True,
            )
            st.caption(f"消費總額：{int(sum(r['amount'] for r in pays))} 元")
        else:
            st.caption("尚無消費紀錄。")
    else:
        st.caption("（前台無檢視消費紀錄的權限）")

    # --- 最近簽到 ---
    st.subheader("最近簽到紀錄")
    cins = fetch_checkins(member_id, 10)
    if cins:
        st.dataframe(
            [{"到館時間": r["check_in_at"]} for r in cins],
            hide_index=True, use_container_width=True,
        )
    else:
        st.caption("尚無簽到紀錄。")

    # --- 最近訓練紀錄 ---
    st.subheader("最近訓練紀錄")
    trainings = fetch_recent_trainings(member_id, 5)
    if not trainings:
        st.caption("尚無訓練紀錄。")
        return

    # 依訓練場次分組（rows 已按場次排序）
    sessions, order = {}, []
    for r in trainings:
        sid = r["training_session_id"]
        if sid not in sessions:
            sessions[sid] = {"date": r["training_date"], "logs": []}
            order.append(sid)
        sessions[sid]["logs"].append(r)

    for sid in order:
        s = sessions[sid]
        st.markdown(f"**{s['date']}**")
        st.dataframe(
            [{
                "動作": l["exercise_name"],
                "重量": f"{l['weight']:g} kg" if l["weight"] is not None else "—",
                "組數": l["sets"] if l["sets"] is not None else "—",
                "次數": l["reps"] if l["reps"] is not None else "—",
            } for l in s["logs"]],
            hide_index=True, use_container_width=True,
        )


def render_add(user: dict):
    if st.button("← 返回列表"):
        st.session_state["member_add_mode"] = False
        st.rerun()

    st.header("新增會員")

    plans = [dict(p) for p in fetch_active_plans()]   # 轉 dict，避免 sqlite3.Row 無法序列化
    if not plans:
        st.warning("尚無可用的會籍方案，無法新增會員。")
        return
    plan_by_id = {p["plan_id"]: p for p in plans}

    GENDER_OPTS = {"不指定": None, "男": "male", "女": "female", "其他": "other"}
    GOAL_OPTS = {"不指定": None, "減重": "lose_weight", "增肌": "gain_muscle", "維持": "maintain"}
    METHOD_OPTS = {"現金": "cash", "刷卡": "card", "轉帳": "transfer"}

    with st.form("add_member_form"):
        st.subheader("基本資料")
        name = st.text_input("姓名 *", placeholder="必填")
        c1, c2 = st.columns(2)
        gender_label = c1.selectbox("性別", list(GENDER_OPTS.keys()))
        birth = c2.date_input("生日", value=date(1990, 1, 1),
                              min_value=date(1900, 1, 1), max_value=date.today())
        c3, c4 = st.columns(2)
        phone = c3.text_input("電話")
        email = c4.text_input("Email")
        goal_label = st.selectbox("健身目標", list(GOAL_OPTS.keys()))

        st.subheader("會籍方案與付款")
        # 選項用 plan_id(純數字、可序列化)；顯示文字交給 format_func 查表
        plan_id = st.selectbox(
            "選擇方案",
            list(plan_by_id.keys()),
            format_func=lambda pid: (
                f"{plan_by_id[pid]['name']}（"
                f"{PLAN_TYPE_LABELS.get(plan_by_id[pid]['type'], plan_by_id[pid]['type'])}・"
                f"{int(plan_by_id[pid]['price'])}元）"
            ),
        )
        method_label = st.selectbox("付款方式", list(METHOD_OPTS.keys()))

        consent = st.checkbox("我已取得會員同意收集個人資料（必勾才能送出）")

        submitted = st.form_submit_button("新增會員", type="primary")

    if not submitted:
        return

    # --- 驗證 ---
    if not name.strip():
        st.error("姓名為必填。")
        return
    if not consent:
        st.error("必須勾選個資同意才能送出。")
        return

    # --- 寫入（三表一致）---
    plan = plan_by_id[plan_id]   # 由選到的 plan_id 取回完整方案
    try:
        create_member(
            name=name.strip(),
            gender=GENDER_OPTS[gender_label],
            birth_date=birth.isoformat(),
            phone=phone.strip() or None,
            email=email.strip() or None,
            goal_type=GOAL_OPTS[goal_label],
            plan=plan,
            method=METHOD_OPTS[method_label],
            staff_id=user["staff_id"],
        )
    except Exception as e:
        st.error(f"新增失敗，資料已全部撤銷：{e}")
        return

    # --- 成功 -> 帶提示返回列表 ---
    st.session_state["flash"] = f"會員新增成功：{name.strip()}"
    st.session_state["member_add_mode"] = False
    st.rerun()
