"""
consultant_page.py — 🤖 AI 留客顧問
管理者選一位會員 → 自動組出去識別化資料摘要 → 用 Gemini 多輪對話分析留客策略
資料去識別化（不送姓名、電話）；對話歷史存 session_state，切換會員自動清空。
"""
import logging
import os
import time
from datetime import date, timedelta

import streamlit as st
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO)
_log = logging.getLogger("consultant_page")

load_dotenv()

from db import get_connection
from rfm_page import score_r, score_f, score_m, segment
from training_page import fetch_progress, detect_stall

_SYSTEM_INSTRUCTION = (
    "你是資深健身房留客顧問。只能根據我提供的"
    "會員資料回答，給出具體可執行的建議，"
    "不要編造資料裡沒有的數字。回答用繁體中文。"
)
_MODEL = "gemini-2.5-flash"
_RATE_LIMIT_WAIT = 62  # 免費方案 15 req/min，等 62 秒確保跨越邊界


# ── 資料查詢 ─────────────────────────────────────────────────

@st.cache_data(ttl=300)
def _all_members():
    conn = get_connection()
    rows = conn.execute("SELECT member_id, name FROM members ORDER BY name").fetchall()
    conn.close()
    return [dict(r) for r in rows]


@st.cache_data(ttl=300)
def _fetch_profile(member_id: int) -> dict:
    conn = get_connection()
    today = date.today()
    year_ago = (today - timedelta(days=365)).isoformat()

    # RFM 原始數據
    last_ci_row = conn.execute(
        "SELECT MAX(check_in_at) AS last FROM check_ins WHERE member_id=?", (member_id,)
    ).fetchone()
    last_ci = last_ci_row["last"]
    recency_days = (today - date.fromisoformat(last_ci[:10])).days if last_ci else None

    freq = conn.execute(
        "SELECT COUNT(*) FROM check_ins WHERE member_id=? AND date(check_in_at)>=?",
        (member_id, year_ago)
    ).fetchone()[0]
    monetary = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) FROM payments WHERE member_id=? AND payment_date>=?",
        (member_id, year_ago)
    ).fetchone()[0]

    r_score = score_r(recency_days)
    f_score = score_f(freq)
    m_score = score_m(monetary)
    seg = segment(r_score, f_score, m_score)

    # 近 8 週到館趨勢
    weeks_data = []
    for i in range(7, -1, -1):
        wk_start = today - timedelta(days=today.weekday() + 7 * i)
        wk_end = wk_start + timedelta(days=6)
        cnt = conn.execute(
            "SELECT COUNT(*) FROM check_ins WHERE member_id=? "
            "AND date(check_in_at) BETWEEN ? AND ?",
            (member_id, wk_start.isoformat(), wk_end.isoformat())
        ).fetchone()[0]
        weeks_data.append(("本週" if i == 0 else f"W-{i}", cnt))

    # 會籍狀態
    ms_row = conn.execute(
        "SELECT status, end_date FROM memberships WHERE member_id=? "
        "ORDER BY CASE status WHEN 'active' THEN 1 WHEN 'frozen' THEN 2 ELSE 3 END LIMIT 1",
        (member_id,)
    ).fetchone()
    ms_status = ms_row["status"] if ms_row else "none"
    ms_end = ms_row["end_date"] if ms_row else None
    lives = (date.fromisoformat(ms_end) - today).days if ms_end else None

    # 訓練停滯
    trained_exs = conn.execute(
        "SELECT DISTINCT l.exercise_id, e.name FROM training_logs l "
        "JOIN training_sessions ts ON ts.training_session_id=l.training_session_id "
        "JOIN exercises e ON e.exercise_id=l.exercise_id "
        "WHERE ts.member_id=? AND l.weight IS NOT NULL",
        (member_id,)
    ).fetchall()
    conn.close()

    stagnant = []
    for ex in trained_exs:
        progress = fetch_progress(member_id, ex["exercise_id"])
        is_stall, recent_max, baseline_max = detect_stall(progress)
        if is_stall:
            stagnant.append(
                f"{ex['name']}（近期最佳 {recent_max:g}kg，基準 {baseline_max:g}kg）"
            )

    # 目標進度
    conn = get_connection()
    goals = [dict(r) for r in conn.execute(
        "SELECT g.goal_id, g.goal_category, g.exercise_id, g.target_value, g.achieved, "
        "e.name AS exercise_name FROM member_goals g "
        "LEFT JOIN exercises e ON e.exercise_id=g.exercise_id "
        "WHERE g.member_id=? ORDER BY g.achieved DESC, g.goal_id",
        (member_id,)
    ).fetchall()]
    for g in goals:
        if g["goal_category"] == "weight":
            r = conn.execute(
                "SELECT weight FROM body_measurements WHERE member_id=? AND weight IS NOT NULL "
                "ORDER BY measured_date DESC LIMIT 1", (member_id,)
            ).fetchone()
            g["current"] = r["weight"] if r else None
        else:
            r = conn.execute(
                "SELECT MAX(l.weight) AS best FROM training_logs l "
                "JOIN training_sessions ts ON ts.training_session_id=l.training_session_id "
                "WHERE ts.member_id=? AND l.exercise_id=?",
                (member_id, g["exercise_id"])
            ).fetchone()
            g["current"] = r["best"] if r else None
        if g["current"] and g["target_value"]:
            g["pct"] = min(100, round(g["current"] / g["target_value"] * 100))
        else:
            g["pct"] = 0

    total_payment = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) FROM payments WHERE member_id=? AND payment_date>=?",
        (member_id, year_ago)
    ).fetchone()[0]
    conn.close()

    return {
        "recency_days": recency_days,
        "freq": freq,
        "monetary": monetary,
        "r_score": r_score,
        "f_score": f_score,
        "m_score": m_score,
        "segment": seg,
        "weeks_data": weeks_data,
        "ms_status": ms_status,
        "ms_end": ms_end,
        "lives": lives,
        "stagnant": stagnant,
        "goals": goals,
        "total_payment": total_payment,
    }


def _build_profile_text(p: dict) -> str:
    """組成去識別化的會員資料文字（不含姓名、電話）。"""
    lines = ["【會員資料摘要（去識別化）】"]

    recency_str = f"距上次到館 {p['recency_days']} 天" if p["recency_days"] is not None else "從未到館"
    lines.append(
        f"\n■ RFM 分析\n"
        f"  分群：{p['segment']}\n"
        f"  R（近訪問性）{p['r_score']}/5 — {recency_str}\n"
        f"  F（到館頻率）{p['f_score']}/5 — 近一年到館 {p['freq']} 次\n"
        f"  M（消費金額）{p['m_score']}/5 — 近一年消費 {int(p['monetary'])} 元"
    )

    status_map = {"active": "有效", "frozen": "凍結", "expired": "已過期", "none": "無會籍"}
    ms_label = status_map.get(p["ms_status"], p["ms_status"])
    end_str = (
        f"，到期日 {p['ms_end']}（剩 {p['lives']} 天）"
        if p["ms_end"] and p["lives"] is not None else ""
    )
    lines.append(f"\n■ 會籍狀態\n  {ms_label}{end_str}")

    trend_str = "  ".join(f"{lbl}:{cnt}次" for lbl, cnt in p["weeks_data"])
    lines.append(f"\n■ 近 8 週到館趨勢（最舊→最新）\n  {trend_str}")

    if p["stagnant"]:
        lines.append("\n■ 訓練停滯動作（近期無進步）\n  " + "\n  ".join(p["stagnant"]))
    else:
        lines.append("\n■ 訓練停滯動作\n  無停滯或無近期訓練紀錄")

    if p["goals"]:
        goal_lines = []
        for g in p["goals"]:
            ex = g.get("exercise_name") or "體重"
            status_str = "已達成" if g["achieved"] else f"進度 {g['pct']}%"
            cur_str = f"{g['current']:g}kg" if g["current"] is not None else "無紀錄"
            goal_lines.append(
                f"{ex} → 目標 {g['target_value']:g}kg（目前 {cur_str}，{status_str}）"
            )
        lines.append("\n■ 目標進度\n  " + "\n  ".join(goal_lines))
    else:
        lines.append("\n■ 目標進度\n  尚未設定目標")

    lines.append(f"\n■ 近一年總消費\n  {int(p['total_payment'])} 元")

    return "\n".join(lines)


# ── Gemini 呼叫 ──────────────────────────────────────────────

def _call_gemini(api_key: str, system_prompt: str, history: list, user_msg: str) -> str:
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        raise RuntimeError("請先安裝套件：pip install google-genai")

    client = genai.Client(api_key=api_key)

    contents = []
    for turn in history:
        contents.append(types.Content(
            role=turn["role"],
            parts=[types.Part(text=turn["content"])],
        ))
    contents.append(types.Content(
        role="user",
        parts=[types.Part(text=user_msg)],
    ))

    for attempt in range(5):
        try:
            response = client.models.generate_content(
                model=_MODEL,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    temperature=0.7,
                ),
            )
            return response.text
        except Exception as e:
            msg = str(e)
            _log.error("[Gemini attempt=%d] %s: %s", attempt, type(e).__name__, msg)
            if "429" in msg or "RESOURCE_EXHAUSTED" in msg:
                raise RuntimeError(f"__RATE_LIMIT__{msg}") from e
            if "503" in msg or "UNAVAILABLE" in msg or "overloaded" in msg:
                if attempt < 4:
                    wait = 5 * (2 ** attempt)   # 5s, 10s, 20s, 40s
                    _log.warning("[Gemini 503] attempt=%d, sleep %ds", attempt, wait)
                    time.sleep(wait)
                    continue
                raise RuntimeError("Gemini 暫時忙線（高流量），請稍後再試。") from e
            if any(k in msg for k in ("401", "403", "API_KEY", "invalid")):
                raise RuntimeError(f"金鑰或權限問題，請確認 GEMINI_API_KEY 正確。({msg})") from e
            raise


def _is_rate_limit_error(e: Exception) -> bool:
    return str(e).startswith("__RATE_LIMIT__")


# ── 頁面入口 ─────────────────────────────────────────────────

def render(user: dict):
    members = _all_members()
    if not members:
        st.warning("尚無會員資料。")
        return

    by_id = {m["member_id"]: m["name"] for m in members}
    mid = st.selectbox(
        "選擇會員",
        list(by_id.keys()),
        format_func=lambda x: by_id[x],
        key="consultant_member",
    )

    # 切換會員 → 清空對話歷史與 pending 狀態
    if st.session_state.get("_consult_mid") != mid:
        st.session_state["_consult_history"] = []
        st.session_state["_consult_mid"] = mid
        st.session_state.pop("_pending_msg", None)
        st.session_state.pop("_rate_limit_until", None)

    profile = _fetch_profile(mid)
    profile_text = _build_profile_text(profile)
    system_prompt = f"{_SYSTEM_INSTRUCTION}\n\n{profile_text}"

    with st.expander("📋 會員資料摘要（AI 將依此分析）", expanded=True):
        st.code(profile_text, language=None)

    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        st.error("請在 Replit Secrets（或環境變數）中設定 GEMINI_API_KEY。")
        return

    st.divider()

    history: list = st.session_state["_consult_history"]

    # 顯示歷史對話
    for turn in history:
        role_ui = "assistant" if turn["role"] == "model" else "user"
        with st.chat_message(role_ui):
            st.markdown(turn["content"])

    # ── 429 自動重試倒數 ──────────────────────────────────────
    pending_msg = st.session_state.get("_pending_msg", "")
    rate_limit_until = st.session_state.get("_rate_limit_until", 0)
    now = time.time()

    if pending_msg:
        with st.chat_message("user"):
            st.markdown(pending_msg)

        if now < rate_limit_until:
            # 倒數中
            wait_secs = int(rate_limit_until - now)
            raw_err = st.session_state.get("_rate_limit_raw", "")
            with st.chat_message("assistant"):
                st.info(
                    f"⏳ 已達 Gemini 每分鐘額度上限（免費方案 15 次/分鐘）。\n\n"
                    f"**{wait_secs} 秒後自動重試**，請稍候..."
                )
                st.progress(max(0.0, 1.0 - wait_secs / _RATE_LIMIT_WAIT))
                if raw_err:
                    with st.expander("原始錯誤（除錯用）"):
                        st.code(raw_err)
            time.sleep(1)
            st.rerun()
        else:
            # 時間到，自動重試
            with st.chat_message("assistant"):
                with st.spinner("重試中..."):
                    try:
                        reply = _call_gemini(api_key, system_prompt, history, pending_msg)
                        st.markdown(reply)
                        history.append({"role": "user", "content": pending_msg})
                        history.append({"role": "model", "content": reply})
                        st.session_state["_consult_history"] = history
                        st.session_state.pop("_pending_msg", None)
                        st.session_state.pop("_rate_limit_until", None)
                    except Exception as e:
                        if _is_rate_limit_error(e):
                            # 重試仍失敗，再等一輪
                            st.session_state["_rate_limit_until"] = time.time() + _RATE_LIMIT_WAIT
                            st.info(f"⏳ 仍在額度限制中，再等 {_RATE_LIMIT_WAIT} 秒...")
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error(f"AI 回應失敗：{e}")
                            st.session_state.pop("_pending_msg", None)
                            st.session_state.pop("_rate_limit_until", None)
        return  # pending 狀態下不顯示 chat_input

    # ── 正常流程 ──────────────────────────────────────────────
    user_msg = st.chat_input(
        "詢問 AI 顧問，例如：這位會員有什麼流失風險？有哪些具體建議？"
    )
    if not user_msg:
        return

    with st.chat_message("user"):
        st.markdown(user_msg)

    with st.chat_message("assistant"):
        with st.spinner("AI 顧問思考中..."):
            try:
                reply = _call_gemini(api_key, system_prompt, history, user_msg)
                st.markdown(reply)
                history.append({"role": "user", "content": user_msg})
                history.append({"role": "model", "content": reply})
                st.session_state["_consult_history"] = history
            except Exception as e:
                if _is_rate_limit_error(e):
                    raw = str(e).removeprefix("__RATE_LIMIT__")
                    _log.error("[429 on user msg] raw=%s", raw)
                    st.session_state["_rate_limit_until"] = time.time() + _RATE_LIMIT_WAIT
                    st.session_state["_pending_msg"] = user_msg
                    st.session_state["_rate_limit_raw"] = raw
                    st.info(
                        f"⏳ 已達 Gemini 每分鐘額度上限（免費方案 15 次/分鐘）。\n\n"
                        f"**{_RATE_LIMIT_WAIT} 秒後自動重試**，請稍候..."
                    )
                    with st.expander("原始錯誤（除錯用）"):
                        st.code(raw)
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error(f"AI 回應失敗：{e}")
