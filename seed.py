"""
seed.py — 種子資料
用法: python seed.py
特性:
  * 日期相對「今天」動態產生，RFM 的 R(最近一次)才有意義
  * 密碼用 bcrypt 雜湊
  * 可重複執行：每次先清空再重建（注意：會清掉現有資料）
三個測試會員刻意拉開 RFM 差距：
  高貢獻度(常來、消費多) / 中貢獻度(偶爾來) / 可能流失(很久沒來)
"""
from datetime import date, datetime, timedelta

try:
    import bcrypt
except ImportError:
    raise SystemExit("請先安裝 bcrypt：pip install bcrypt")

from db import get_connection

TODAY = date.today()


def d(days_ago: int) -> str:
    """days_ago 天前的日期字串 'YYYY-MM-DD'（可為負數表示未來）"""
    return (TODAY - timedelta(days=days_ago)).isoformat()


def dt(days_ago: int, hour: int = 18, minute: int = 0) -> str:
    """days_ago 天前的時間字串 'YYYY-MM-DD HH:MM:SS'"""
    base = datetime.combine(TODAY - timedelta(days=days_ago), datetime.min.time())
    return base.replace(hour=hour, minute=minute).strftime("%Y-%m-%d %H:%M:%S")


def hash_pw(pw: str) -> str:
    return bcrypt.hashpw(pw.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def insert(cur, sql, params):
    cur.execute(sql, params)
    return cur.lastrowid


def clear_all(cur):
    """依外鍵相依順序，子表先刪、父表後刪。"""
    for t in [
        "training_logs", "training_sessions", "member_goals",
        "body_measurements", "check_ins", "payments", "memberships",
        "members", "exercises", "membership_plans", "staff",
    ]:
        cur.execute(f"DELETE FROM {t}")


def seed():
    conn = get_connection()
    cur = conn.cursor()
    clear_all(cur)

    # ---------- 會籍方案 ----------
    plan_monthly = insert(cur,
        "INSERT INTO membership_plans(name,type,price,duration_days,session_count) VALUES (?,?,?,?,?)",
        ("月費方案", "monthly", 2000, 30, None))
    plan_pack = insert(cur,
        "INSERT INTO membership_plans(name,type,price,duration_days,session_count) VALUES (?,?,?,?,?)",
        ("十堂課程包", "class_pack", 3000, None, 10))
    plan_pt = insert(cur,
        "INSERT INTO membership_plans(name,type,price,duration_days,session_count) VALUES (?,?,?,?,?)",
        ("私教五堂", "personal_training", 5000, None, 5))

    # ---------- 動作字典（皆為重訓）----------
    ex_squat  = insert(cur, "INSERT INTO exercises(name,exercise_type,category) VALUES (?,?,?)", ("深蹲",   "strength", "腿"))
    ex_bench  = insert(cur, "INSERT INTO exercises(name,exercise_type,category) VALUES (?,?,?)", ("臥推",   "strength", "胸"))
    ex_dead   = insert(cur, "INSERT INTO exercises(name,exercise_type,category) VALUES (?,?,?)", ("硬舉",   "strength", "背"))
    ex_pullup = insert(cur, "INSERT INTO exercises(name,exercise_type,category) VALUES (?,?,?)", ("引體向上", "strength", "背"))
    ex_ohp    = insert(cur, "INSERT INTO exercises(name,exercise_type,category) VALUES (?,?,?)", ("肩推",   "strength", "肩"))

    # ---------- 員工 ----------
    mgr     = insert(cur, "INSERT INTO staff(name,role,username,password_hash) VALUES (?,?,?,?)", ("陳經理", "manager",    "manager",   hash_pw("manager123")))
    front   = insert(cur, "INSERT INTO staff(name,role,username,password_hash) VALUES (?,?,?,?)", ("林前台", "front_desk", "frontdesk", hash_pw("front123")))
    trainer = insert(cur, "INSERT INTO staff(name,role,username,password_hash) VALUES (?,?,?,?)", ("黃教練", "trainer",    "trainer",   hash_pw("trainer123")))

    # ---------- 會員 ----------
    m_high = insert(cur,
        "INSERT INTO members(name,gender,birth_date,phone,email,goal_type,join_date,consent_data_collection,consent_date) VALUES (?,?,?,?,?,?,?,?,?)",
        ("王大明", "male", "1990-05-12", "0912345678", "wang@example.com", "gain_muscle", d(300), 1, d(300)))
    m_mid = insert(cur,
        "INSERT INTO members(name,gender,birth_date,phone,email,goal_type,join_date,consent_data_collection,consent_date) VALUES (?,?,?,?,?,?,?,?,?)",
        ("李小華", "female", "1995-08-20", "0922333444", "lee@example.com", "lose_weight", d(240), 1, d(240)))
    m_churn = insert(cur,
        "INSERT INTO members(name,gender,birth_date,phone,email,goal_type,join_date,consent_data_collection,consent_date) VALUES (?,?,?,?,?,?,?,?,?)",
        ("陳志強", "male", "1988-03-03", "0933222111", "chen@example.com", "maintain", d(330), 1, d(330)))

    # ---------- 會籍 ----------
    # 高：月費(使用中) + 私教包(使用中，剩2堂)
    ms_high_monthly = insert(cur,
        "INSERT INTO memberships(member_id,plan_id,status,start_date,end_date,sessions_remaining) VALUES (?,?,?,?,?,?)",
        (m_high, plan_monthly, "active", d(20), d(-10), None))           # 月費，效期到 10 天後
    ms_high_pt = insert(cur,
        "INSERT INTO memberships(member_id,plan_id,status,start_date,end_date,sessions_remaining) VALUES (?,?,?,?,?,?)",
        (m_high, plan_pt, "active", d(40), None, 2))                     # 私教 5 堂用剩 2 堂
    # 中：課程包(使用中，剩4堂)
    ms_mid_pack = insert(cur,
        "INSERT INTO memberships(member_id,plan_id,status,start_date,end_date,sessions_remaining) VALUES (?,?,?,?,?,?)",
        (m_mid, plan_pack, "active", d(50), None, 4))
    # 流失：月費(已到期)
    ms_churn = insert(cur,
        "INSERT INTO memberships(member_id,plan_id,status,start_date,end_date,sessions_remaining) VALUES (?,?,?,?,?,?)",
        (m_churn, plan_monthly, "expired", d(180), d(120), None))

    # ---------- 金流（M 來源：近一年）----------
    # 高：近一年 10 筆月費 + 1 筆私教 = 25000（最高）
    for days in [300, 270, 240, 210, 180, 150, 120, 90, 60, 20]:
        link = ms_high_monthly if days == 20 else None
        insert(cur, "INSERT INTO payments(member_id,membership_id,staff_id,amount,payment_type,payment_date,method) VALUES (?,?,?,?,?,?,?)",
               (m_high, link, front, 2000, "membership_fee", d(days), "card"))
    insert(cur, "INSERT INTO payments(member_id,membership_id,staff_id,amount,payment_type,payment_date,method) VALUES (?,?,?,?,?,?,?)",
           (m_high, ms_high_pt, trainer, 5000, "personal_training", d(40), "card"))

    # 中：課程包 3000 + 一筆月費 2000 = 5000
    insert(cur, "INSERT INTO payments(member_id,membership_id,staff_id,amount,payment_type,payment_date,method) VALUES (?,?,?,?,?,?,?)",
           (m_mid, ms_mid_pack, front, 3000, "add_on_class", d(50), "cash"))
    insert(cur, "INSERT INTO payments(member_id,membership_id,staff_id,amount,payment_type,payment_date,method) VALUES (?,?,?,?,?,?,?)",
           (m_mid, None, front, 2000, "membership_fee", d(120), "cash"))

    # 流失：兩筆舊月費 4000（且都在 5 個月前）
    for days in [180, 150]:
        insert(cur, "INSERT INTO payments(member_id,membership_id,staff_id,amount,payment_type,payment_date,method) VALUES (?,?,?,?,?,?,?)",
               (m_churn, ms_churn, front, 2000, "membership_fee", d(days), "transfer"))

    # ---------- 到館簽到（R / F 來源）----------
    # 高：最近一次=1天前，近三個月每兩天一次 + 更早每週一次 → R 最近、F 最高
    high_offsets = list(range(1, 95, 2)) + list(range(100, 280, 7))
    # 中：最近一次=18天前，零星 → R 中等、F 中等
    mid_offsets = [18, 25, 33, 46, 60, 80, 110, 140, 170, 200]
    # 流失：最近一次=110天前，且只有早期幾次 → R 很久、F 很低
    churn_offsets = [110, 118, 125, 140, 155, 170]
    for mid_, offsets in [(m_high, high_offsets), (m_mid, mid_offsets), (m_churn, churn_offsets)]:
        for off in offsets:
            insert(cur, "INSERT INTO check_ins(member_id,check_in_at,checked_in_by) VALUES (?,?,?)",
                   (mid_, dt(off, hour=(8 + off % 12)), front))

    # ---------- 訓練紀錄 ----------
    def add_session(member_id, days_ago, logs):
        sid = insert(cur, "INSERT INTO training_sessions(member_id,trainer_id,training_date,notes) VALUES (?,?,?,?)",
                     (member_id, trainer, d(days_ago), None))
        for ex_id, weight, sets, reps in logs:
            insert(cur, "INSERT INTO training_logs(training_session_id,exercise_id,weight,sets,reps) VALUES (?,?,?,?,?)",
                   (sid, ex_id, weight, sets, reps))

    # 高：深蹲 60→80 穩定進步（對應你的範例），臥推 40→55
    add_session(m_high, 200, [(ex_squat, 60, 5, 5), (ex_bench, 40, 5, 8)])
    add_session(m_high, 150, [(ex_squat, 65, 5, 5), (ex_bench, 45, 5, 8)])
    add_session(m_high, 100, [(ex_squat, 70, 5, 5), (ex_bench, 50, 5, 6)])
    add_session(m_high,  50, [(ex_squat, 75, 5, 5), (ex_bench, 52, 5, 6), (ex_dead, 90, 3, 5)])
    add_session(m_high,  10, [(ex_squat, 80, 5, 5), (ex_bench, 55, 5, 5), (ex_dead, 100, 3, 5)])

    # 中：兩次，小幅
    add_session(m_mid, 60, [(ex_squat, 40, 4, 10), (ex_pullup, 0, 3, 5)])
    add_session(m_mid, 25, [(ex_squat, 42, 4, 10), (ex_ohp, 20, 4, 8)])

    # 流失：早期一次後就沒再來
    add_session(m_churn, 170, [(ex_squat, 50, 4, 8), (ex_bench, 35, 4, 8)])

    # ---------- 身體測量 ----------
    for member_id, rows in [
        (m_high,  [(200, 78, 18, 32), (100, 80, 17, 34), (10, 82, 16, 36)]),  # 增肌：體重↑體脂↓
        (m_mid,   [(60, 65, 28, 24), (25, 63, 27, 24)]),                       # 減重：體重↓
        (m_churn, [(170, 75, 22, 28)]),
    ]:
        for days, w, bf, mm in rows:
            insert(cur, "INSERT INTO body_measurements(member_id,measured_date,weight,body_fat_pct,muscle_mass,recorded_by) VALUES (?,?,?,?,?,?)",
                   (member_id, d(days), w, bf, mm, trainer))

    # ---------- 目標里程碑 ----------
    # 高：深蹲目標 100kg(未達)、體重目標 85kg(未達)
    insert(cur, "INSERT INTO member_goals(member_id,goal_category,exercise_id,target_value,achieved,achieved_date) VALUES (?,?,?,?,?,?)",
           (m_high, "lift", ex_squat, 100, 0, None))
    insert(cur, "INSERT INTO member_goals(member_id,goal_category,exercise_id,target_value,achieved,achieved_date) VALUES (?,?,?,?,?,?)",
           (m_high, "weight", None, 85, 0, None))
    # 中：體重目標 65kg(已達成，觸發過恭喜) + 60kg(進行中)
    insert(cur, "INSERT INTO member_goals(member_id,goal_category,exercise_id,target_value,achieved,achieved_date) VALUES (?,?,?,?,?,?)",
           (m_mid, "weight", None, 65, 1, d(25)))
    insert(cur, "INSERT INTO member_goals(member_id,goal_category,exercise_id,target_value,achieved,achieved_date) VALUES (?,?,?,?,?,?)",
           (m_mid, "weight", None, 60, 0, None))

    conn.commit()
    conn.close()
    print("種子資料建立完成。")
    print(f"  方案 id: 月費={plan_monthly} 課程包={plan_pack} 私教={plan_pt}")
    print(f"  會員 id: 高={m_high} 中={m_mid} 流失={m_churn}")
    print("  登入帳密(測試用): manager/manager123, frontdesk/front123, trainer/trainer123")


if __name__ == "__main__":
    seed()
