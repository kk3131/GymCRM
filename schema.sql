-- ============================================================
-- 健身房 CRM 系統 v1 Schema (SQLite)
-- 11 張表：members, staff, membership_plans, exercises,
--          memberships, payments, check_ins, body_measurements,
--          member_goals, training_sessions, training_logs
-- 說明：
--   * 日期一律用 TEXT 存 ISO 格式：日期 'YYYY-MM-DD'、時間 'YYYY-MM-DD HH:MM:SS'
--   * 布林值用 INTEGER 存 0/1（SQLite 沒有真正的 BOOLEAN 型別）
--   * 列舉值用英文代碼 + CHECK 約束，畫面再對應中文標籤
-- ============================================================

-- ---------- 1. 會員 ----------
CREATE TABLE IF NOT EXISTS members (
    member_id               INTEGER PRIMARY KEY,
    name                    TEXT    NOT NULL,
    gender                  TEXT    CHECK (gender IN ('male', 'female', 'other')),
    birth_date              TEXT,                                   -- 'YYYY-MM-DD'
    phone                   TEXT,
    email                   TEXT,
    goal_type               TEXT    CHECK (goal_type IN ('lose_weight', 'gain_muscle', 'maintain')),
    join_date               TEXT    NOT NULL DEFAULT CURRENT_DATE,
    consent_data_collection INTEGER NOT NULL DEFAULT 0,             -- 0=未同意 1=已同意
    consent_date            TEXT,
    created_at              TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ---------- 2. 員工（前台/管理者/教練）----------
CREATE TABLE IF NOT EXISTS staff (
    staff_id      INTEGER PRIMARY KEY,
    name          TEXT    NOT NULL,
    role          TEXT    NOT NULL CHECK (role IN ('front_desk', 'manager', 'trainer')),
    username      TEXT    NOT NULL UNIQUE,
    password_hash TEXT    NOT NULL,                                 -- 存雜湊，絕不存明碼
    is_active     INTEGER NOT NULL DEFAULT 1,
    created_at    TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ---------- 3. 會籍方案（賣的商品）----------
CREATE TABLE IF NOT EXISTS membership_plans (
    plan_id       INTEGER PRIMARY KEY,
    name          TEXT    NOT NULL,
    type          TEXT    NOT NULL CHECK (type IN ('monthly', 'class_pack', 'personal_training')),
    price         REAL    NOT NULL,
    duration_days INTEGER,                                          -- 月費制效期天數；非月費可 NULL
    session_count INTEGER,                                          -- 堂數包/私教總堂數；月費可 NULL
    is_active     INTEGER NOT NULL DEFAULT 1
);

-- ---------- 4. 動作字典 ----------
CREATE TABLE IF NOT EXISTS exercises (
    exercise_id   INTEGER PRIMARY KEY,
    name          TEXT    NOT NULL UNIQUE,                          -- 深蹲/臥推/硬舉/跑步機
    exercise_type TEXT    NOT NULL DEFAULT 'strength'
                          CHECK (exercise_type IN ('strength', 'cardio')),  -- 決定記重量/組/次 還是 時間
    category      TEXT,                                            -- 腿/胸/背/有氧...
    is_active     INTEGER NOT NULL DEFAULT 1
);

-- ---------- 5. 會籍（會員實際持有的合約）----------
-- 不放 type 欄位：可從 plan_id -> membership_plans.type 查到，存在這裡才是冗餘。
CREATE TABLE IF NOT EXISTS memberships (
    membership_id      INTEGER PRIMARY KEY,
    member_id          INTEGER NOT NULL REFERENCES members(member_id),
    plan_id            INTEGER NOT NULL REFERENCES membership_plans(plan_id),
    status             TEXT    NOT NULL DEFAULT 'active'
                               CHECK (status IN ('active', 'frozen', 'expired')),
    start_date         TEXT    NOT NULL,
    end_date           TEXT,
    sessions_remaining INTEGER,                                     -- 堂數包/私教剩餘堂數
    created_at         TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ---------- 6. 金流（RFM 的 M 來源）----------
CREATE TABLE IF NOT EXISTS payments (
    payment_id    INTEGER PRIMARY KEY,
    member_id     INTEGER NOT NULL REFERENCES members(member_id),
    membership_id INTEGER REFERENCES memberships(membership_id),    -- 可 NULL：加購、雜項
    staff_id      INTEGER REFERENCES staff(staff_id),               -- 經手人
    amount        REAL    NOT NULL,
    payment_type  TEXT    NOT NULL CHECK (payment_type IN ('membership_fee', 'add_on_class', 'personal_training')),
    payment_date  TEXT    NOT NULL,
    method        TEXT    CHECK (method IN ('cash', 'card', 'transfer')),
    created_at    TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ---------- 7. 到館簽到（RFM 的 R / F 來源；前台手動打卡）----------
CREATE TABLE IF NOT EXISTS check_ins (
    check_in_id   INTEGER PRIMARY KEY,
    member_id     INTEGER NOT NULL REFERENCES members(member_id),
    check_in_at   TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,       -- 到館時間
    checked_in_by INTEGER REFERENCES staff(staff_id)
);

-- ---------- 8. 身體測量 ----------
CREATE TABLE IF NOT EXISTS body_measurements (
    measurement_id INTEGER PRIMARY KEY,
    member_id      INTEGER NOT NULL REFERENCES members(member_id),
    measured_date  TEXT    NOT NULL,
    weight         REAL,                                            -- 公斤
    body_fat_pct   REAL,                                            -- 體脂率 %
    muscle_mass    REAL,                                            -- 肌肉量 kg
    recorded_by    INTEGER REFERENCES staff(staff_id)
);

-- ---------- 9. 會員目標里程碑（達標時觸發恭喜訊息）----------
CREATE TABLE IF NOT EXISTS member_goals (
    goal_id       INTEGER PRIMARY KEY,
    member_id     INTEGER NOT NULL REFERENCES members(member_id),
    goal_category TEXT    NOT NULL CHECK (goal_category IN ('weight', 'lift')),
    exercise_id   INTEGER REFERENCES exercises(exercise_id),        -- 只有 lift 目標才填
    target_value  REAL    NOT NULL,                                 -- 目標體重 或 目標重量（kg）
    achieved      INTEGER NOT NULL DEFAULT 0,
    achieved_date TEXT,
    created_at    TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    -- lift 目標必須指定動作；weight 目標不可指定動作
    CHECK (
        (goal_category = 'lift'   AND exercise_id IS NOT NULL) OR
        (goal_category = 'weight' AND exercise_id IS NULL)
    )
);

-- ---------- 10. 訓練（一次訓練的表頭）----------
CREATE TABLE IF NOT EXISTS training_sessions (
    training_session_id INTEGER PRIMARY KEY,
    member_id           INTEGER NOT NULL REFERENCES members(member_id),
    trainer_id          INTEGER REFERENCES staff(staff_id),
    training_date       TEXT    NOT NULL,
    notes               TEXT,
    created_at          TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ---------- 11. 訓練明細（每個動作的重量/組/次 或 時間；進步停滯來源）----------
CREATE TABLE IF NOT EXISTS training_logs (
    log_id              INTEGER PRIMARY KEY,
    training_session_id INTEGER NOT NULL REFERENCES training_sessions(training_session_id),
    exercise_id         INTEGER NOT NULL REFERENCES exercises(exercise_id),
    weight              REAL,                                       -- 公斤（重訓用；有氧可 NULL）
    sets                INTEGER,                                    -- 組數（重訓用）
    reps                INTEGER,                                    -- 次數（重訓用）
    duration_seconds    INTEGER,                                    -- 秒（有氧用：跑步、划船機）
    created_at          TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- 索引：加速 RFM / 流失預警 / 進步停滯 的查詢
-- （SQLite 會自動為 PRIMARY KEY 建索引，但不會自動為外鍵建）
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_checkins_member_date  ON check_ins(member_id, check_in_at);
CREATE INDEX IF NOT EXISTS idx_payments_member_date  ON payments(member_id, payment_date);
CREATE INDEX IF NOT EXISTS idx_memberships_member    ON memberships(member_id);
CREATE INDEX IF NOT EXISTS idx_measurements_member   ON body_measurements(member_id, measured_date);
CREATE INDEX IF NOT EXISTS idx_goals_member          ON member_goals(member_id);
CREATE INDEX IF NOT EXISTS idx_tsessions_member_date ON training_sessions(member_id, training_date);
CREATE INDEX IF NOT EXISTS idx_tlogs_session         ON training_logs(training_session_id);
CREATE INDEX IF NOT EXISTS idx_tlogs_exercise        ON training_logs(exercise_id);
