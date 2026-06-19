"""
rfm_page.py — RFM 分析（管理者限定）
  R = 最近一次到館距今天數（越小越好）
  F = 近一年到館次數（越大越好）
  M = 近一年消費金額（越大越好）
各給 1~5 分，再依分數分群。撈出資料一律 dict(r)；時區用 Asia/Taipei。
"""
from datetime import datetime, date, timedelta

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


# ============ 評分門檻（集中管理，方便調整）============
def score_r(days):
    if days is None:
        return 1
    if days <= 7:
        return 5
    if days <= 14:
        return 4
    if days <= 30:
        return 3
    if days <= 60:
        return 2
    return 1


def score_f(n):
    if n >= 52:
        return 5
    if n >= 26:
        return 4
    if n >= 12:
        return 3
    if n >= 4:
        return 2
    return 1


def score_m(amount):
    if amount >= 20000:
        return 5
    if amount >= 10000:
        return 4
    if amount >= 5000:
        return 3
    if amount >= 2000:
        return 2
    return 1


def segment(r, f, m):
    """R 最近性是健身房流失的關鍵訊號，優先判斷。"""
    if r <= 2:
        return "流失風險"
    if r >= 4 and f >= 4:
        return "核心會員"
    if f >= 3:
        return "穩定會員"
    return "一般會員"


SEGMENT_ORDER = ["核心會員", "穩定會員", "一般會員", "流失風險"]


# ============ 資料 ============
def fetch_rfm():
    cutoff_dt = (_now() - timedelta(days=365)).strftime("%Y-%m-%d %H:%M:%S")
    cutoff_date = (_now() - timedelta(days=365)).strftime("%Y-%m-%d")

    conn = get_connection()
    rows = conn.execute(
        """
        SELECT m.member_id, m.name,
          (SELECT MAX(c.check_in_at) FROM check_ins c
             WHERE c.member_id = m.member_id) AS last_checkin,
          (SELECT COUNT(*) FROM check_ins c
             WHERE c.member_id = m.member_id AND c.check_in_at >= ?) AS freq,
          (SELECT COALESCE(SUM(p.amount), 0) FROM payments p
             WHERE p.member_id = m.member_id AND p.payment_date >= ?) AS monetary
        FROM members m
        """,
        (cutoff_dt, cutoff_date),
    ).fetchall()
    conn.close()

    today = _now().date()
    result = []
    for r in rows:
        d = dict(r)
        if d["last_checkin"]:
            d["recency_days"] = (today - date.fromisoformat(d["last_checkin"][:10])).days
        else:
            d["recency_days"] = None
        result.append(d)
    return result


def compute_rfm_rows():
    rows = []
    for d in fetch_rfm():
        rs, fs, ms = score_r(d["recency_days"]), score_f(d["freq"]), score_m(d["monetary"])
        rows.append({
            **d,
            "r_score": rs, "f_score": fs, "m_score": ms,
            "total": rs + fs + ms,
            "segment": segment(rs, fs, ms),
        })
    return rows


# ============ 畫面 ============
def render(user: dict):
    st.subheader("RFM 分析")
    st.caption("R＝最近一次到館距今天數（越小越好）｜F＝近一年到館次數｜M＝近一年消費金額")

    rows = compute_rfm_rows()
    if not rows:
        st.info("尚無會員資料。")
        return

    # 分群分布
    counts = {seg: 0 for seg in SEGMENT_ORDER}
    for r in rows:
        counts[r["segment"]] = counts.get(r["segment"], 0) + 1
    cols = st.columns(len(SEGMENT_ORDER))
    for col, seg in zip(cols, SEGMENT_ORDER):
        col.metric(seg, counts[seg])

    st.divider()

    # 明細表（依總分高到低；表頭可點擊重新排序）
    rows_sorted = sorted(rows, key=lambda x: x["total"], reverse=True)
    st.dataframe(
        [{
            "會員": r["name"],
            "最近到館(天)": r["recency_days"] if r["recency_days"] is not None else "—",
            "近一年次數": r["freq"],
            "近一年消費": int(r["monetary"]),
            "R": r["r_score"],
            "F": r["f_score"],
            "M": r["m_score"],
            "總分": r["total"],
            "分群": r["segment"],
        } for r in rows_sorted],
        hide_index=True, use_container_width=True,
    )

    st.caption("「流失風險」會員(R 太久沒來)會是下一步流失預警的重點對象。")
