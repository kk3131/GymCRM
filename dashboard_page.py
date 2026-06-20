"""
dashboard_page.py — 管理者儀表板（管理者限定）
  KPI 卡：今日到館人數 / 本月新增會員 / 本月總收入
  圖表：RFM 分群分布（環狀圖），分群定義與 rfm_page 完全共用
"""
from datetime import datetime

import streamlit as st

from db import get_connection
from rfm_page import compute_rfm_rows, SEGMENT_ORDER

try:
    from zoneinfo import ZoneInfo
    _TZ = ZoneInfo("Asia/Taipei")
except Exception:
    _TZ = None


def _now():
    return datetime.now(_TZ) if _TZ else datetime.now()


# ==================== 資料 ====================
def fetch_kpis():
    today = _now().strftime("%Y-%m-%d")
    month = _now().strftime("%Y-%m")
    conn = get_connection()
    checkins_today = conn.execute(
        "SELECT COUNT(*) FROM check_ins WHERE date(check_in_at) = ?",
        (today,),
    ).fetchone()[0]
    new_members = conn.execute(
        "SELECT COUNT(*) FROM members WHERE strftime('%Y-%m', join_date) = ?",
        (month,),
    ).fetchone()[0]
    revenue = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) FROM payments WHERE strftime('%Y-%m', payment_date) = ?",
        (month,),
    ).fetchone()[0]
    conn.close()
    return checkins_today, new_members, int(revenue)


def fetch_segment_counts():
    counts = {seg: 0 for seg in SEGMENT_ORDER}
    for r in compute_rfm_rows():
        counts[r["segment"]] = counts.get(r["segment"], 0) + 1
    return counts


# ==================== 畫面 ====================
_COLORS = {
    "核心會員": "#2196F3",
    "穩定會員": "#4CAF50",
    "一般會員": "#9E9E9E",
    "流失風險": "#F44336",
}


def render(user: dict):
    st.subheader("管理者儀表板")

    # ---------- KPI 卡 ----------
    checkins_today, new_members, revenue = fetch_kpis()
    k1, k2, k3 = st.columns(3)
    k1.metric("今日到館人數", checkins_today)
    k2.metric("本月新增會員", new_members)
    k3.metric("本月總收入", f"NT$ {revenue:,}")

    st.divider()

    # ---------- 分群分布 ----------
    st.markdown("#### RFM 分群分布")
    st.caption(
        "分群定義與 RFM 分析頁一致：R≤2 → 流失風險｜R≥4 且 F≥4 → 核心會員｜F≥3 → 穩定會員｜其餘 → 一般會員"
    )

    counts = fetch_segment_counts()
    total = sum(counts.values())

    if total == 0:
        st.info("尚無會員資料。")
        return

    import plotly.graph_objects as go

    labels = SEGMENT_ORDER
    values = [counts[s] for s in SEGMENT_ORDER]

    fig = go.Figure(go.Pie(
        labels=labels,
        values=values,
        hole=0.45,
        marker_colors=[_COLORS[s] for s in SEGMENT_ORDER],
        textinfo="label+value",
        textfont_size=14,
        hovertemplate="%{label}: %{value} 人（%{percent}）<extra></extra>",
    ))
    fig.update_layout(
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=-0.15, xanchor="center", x=0.5),
        height=380,
        margin=dict(t=20, b=40, l=20, r=20),
    )
    st.plotly_chart(fig, use_container_width=True)

    # 數字小卡（與圓餅圖對應，方便對照）
    cols = st.columns(len(SEGMENT_ORDER))
    for col, seg in zip(cols, SEGMENT_ORDER):
        cnt = counts[seg]
        col.metric(seg, f"{cnt} 人", f"{cnt/total*100:.0f}%")
