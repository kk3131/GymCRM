"""
pixel_home.py — 🎮 ADVENTURE MAP 冒險主頁
像素遊戲風格個人儀表板：HUD / 關卡地圖 / 進度條 / 本週金幣 / 訊息框
資料在 Python 查好後用 f-string 注入 HTML；CSS 為獨立常數，不在 f-string 內。
"""
from datetime import date, timedelta

import streamlit as st
import streamlit.components.v1 as components

from db import get_connection

# ── CSS 定義為純字串常數（無 f-string），避免大括號衝突 ──
_CSS = """<style>
@import url('https://fonts.googleapis.com/css2?family=Press+Start+2P&display=swap');
* { box-sizing: border-box; margin: 0; padding: 0; }
body { background: #1a1a2e; color: #fff; font-family: 'Press Start 2P', cursive;
       font-size: 10px; padding: 10px; }
.hud { background: #000; border: 3px solid #FFD700; padding: 10px 16px;
       display: flex; justify-content: space-between; align-items: center;
       margin-bottom: 14px; flex-wrap: wrap; gap: 8px; }
.hud-p { color: #5C94FC; font-size: 9px; }
.hud-s { color: #FFD700; font-size: 9px; }
.hud-l { color: #ff4444; font-size: 9px; }
.sec { background: #000; border: 2px solid #FFD700; padding: 12px; margin-bottom: 12px; }
.sec-t { color: #FFD700; font-size: 8px; margin-bottom: 10px; padding-bottom: 6px;
          border-bottom: 1px solid #333; letter-spacing: 1px; }
.level-map { display: flex; align-items: center; flex-wrap: wrap; gap: 6px; padding: 4px 0; }
.node { display: flex; flex-direction: column; align-items: center; gap: 4px; }
.node-box { width: 44px; height: 44px; display: flex; align-items: center;
             justify-content: center; font-size: 20px; border: 3px solid; }
.node-lbl { font-size: 6px; text-align: center; color: #999; line-height: 1.6; max-width: 54px; }
.nd .node-box { border-color: #5DB25C; background: #0a1f0a; }
.na .node-box { border-color: #FFD700; background: #1f1800; }
.nl .node-box { border-color: #444;    background: #111;    }
.nc .node-box { border-color: #5C94FC; background: #0a0f1f; }
@keyframes blink { 0%,100% { opacity: 1; } 50% { opacity: 0.2; } }
.na .node-box { animation: blink 1s infinite; }
.conn { color: #555; font-size: 18px; align-self: center; margin-bottom: 18px; }
.pb-row { margin-bottom: 12px; }
.pb-lbl { font-size: 8px; color: #ccc; margin-bottom: 5px; }
.pb-track { background: #222; border: 1px solid #444; height: 16px;
             position: relative; overflow: hidden; }
.pb-fill  { height: 100%; position: absolute; left: 0; top: 0; }
.pb-stat  { font-size: 7px; color: #888; margin-top: 3px; }
.coins { display: flex; gap: 14px; justify-content: center; padding: 8px 0; flex-wrap: wrap; }
.coin  { display: flex; flex-direction: column; align-items: center; gap: 5px; }
.ci { font-size: 22px; }
.cd { font-size: 6px; }
.msg-row { display: flex; gap: 10px; margin-bottom: 10px; font-size: 8px;
            align-items: flex-start; line-height: 1.8; }
.msg-ic { color: #FFD700; min-width: 80px; white-space: nowrap; }
.msg-tx { color: #ccc; }
</style>"""


# ── 資料查詢 ──

def _all_members():
    conn = get_connection()
    rows = conn.execute("SELECT member_id, name FROM members ORDER BY name").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def _fetch(member_id: int):
    conn = get_connection()
    today = date.today()

    # 會員基本資料
    m = dict(conn.execute("SELECT * FROM members WHERE member_id=?", (member_id,)).fetchone())

    # SCORE = 累計到館次數 × 100
    score = conn.execute(
        "SELECT COUNT(*) FROM check_ins WHERE member_id=?", (member_id,)
    ).fetchone()[0] * 100

    # LIVES = 有效會籍剩餘天數
    ms_row = conn.execute(
        "SELECT end_date FROM memberships WHERE member_id=? AND status='active' "
        "AND end_date IS NOT NULL ORDER BY end_date DESC LIMIT 1",
        (member_id,)
    ).fetchone()
    lives = max(0, (date.fromisoformat(ms_row["end_date"]) - today).days) if ms_row else "∞"

    # 目標列表 + 當前進度值
    goals = [dict(r) for r in conn.execute(
        "SELECT g.goal_id, g.goal_category, g.exercise_id, g.target_value, g.achieved, "
        "e.name AS exercise_name FROM member_goals g "
        "LEFT JOIN exercises e ON e.exercise_id = g.exercise_id "
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
        g["pct"] = (
            min(100, round(g["current"] / g["target_value"] * 100))
            if g["current"] and g["target_value"] else 0
        )

    # 本週金幣（週一~週日）
    monday = today - timedelta(days=today.weekday())
    week = [monday + timedelta(days=i) for i in range(7)]
    ci_set = {r["d"] for r in conn.execute(
        "SELECT date(check_in_at) AS d FROM check_ins "
        "WHERE member_id=? AND date(check_in_at) BETWEEN ? AND ?",
        (member_id, week[0].isoformat(), week[6].isoformat())
    ).fetchall()}
    DAY = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
    coins = [{"day": DAY[i], "filled": d.isoformat() in ci_set, "today": d == today}
             for i, d in enumerate(week)]

    # 訊息框
    msgs = []
    last_ci = conn.execute(
        "SELECT date(check_in_at) AS d FROM check_ins WHERE member_id=? "
        "ORDER BY check_in_at DESC LIMIT 1", (member_id,)
    ).fetchone()
    if last_ci:
        ago = (today - date.fromisoformat(last_ci["d"])).days
        msgs.append(("CHECK-IN", "TODAY ✓" if ago == 0 else f"{ago} DAYS AGO"))
    else:
        msgs.append(("CHECK-IN", "NO RECORD"))

    if isinstance(lives, int):
        if lives < 14:
            msgs.append(("!! ALERT", f"MEMBERSHIP EXPIRES IN {lives} DAYS!"))
        else:
            msgs.append(("MEMBER", f"{lives} DAYS LEFT"))

    # 本月 vs 上月到館
    this_mo = today.replace(day=1)
    last_mo_end = this_mo - timedelta(days=1)
    last_mo_start = last_mo_end.replace(day=1)
    this_n = conn.execute(
        "SELECT COUNT(*) FROM check_ins WHERE member_id=? AND date(check_in_at)>=?",
        (member_id, this_mo.isoformat())
    ).fetchone()[0]
    last_n = conn.execute(
        "SELECT COUNT(*) FROM check_ins WHERE member_id=? AND date(check_in_at) BETWEEN ? AND ?",
        (member_id, last_mo_start.isoformat(), last_mo_end.isoformat())
    ).fetchone()[0]
    diff = this_n - last_n
    trend = (f"+{diff}" if diff > 0 else str(diff))
    msgs.append(("MONTHLY", f"THIS:{this_n}x  LAST:{last_n}x  ({trend})"))

    # 訓練停滯警告（>21 天未訓練）
    lt = conn.execute(
        "SELECT MAX(training_date) AS d FROM training_sessions WHERE member_id=?", (member_id,)
    ).fetchone()
    if lt and lt["d"]:
        days_nt = (today - date.fromisoformat(lt["d"])).days
        if days_nt > 21:
            msgs.append(("!! WARN", f"NO TRAINING {days_nt} DAYS!"))

    conn.close()
    return m, score, lives, goals, coins, msgs


# ── HTML 組裝（CSS 以變數嵌入，避免大括號轉義問題）──

def _build_html(m, score, lives, goals, coins, msgs):
    score_str = str(score).zfill(6)
    lives_str = f"{lives}d" if isinstance(lives, int) else str(lives)
    name = m["name"]

    # 關卡地圖節點
    done_g = [g for g in goals if g["achieved"]]
    pend_g = [g for g in goals if not g["achieved"]]
    nodes = []
    for g in done_g:
        ex = g.get("exercise_name") or "WEIGHT"
        nodes.append(("nd", "🏁", f"{ex}<br>{g['target_value']:g}kg"))
    if pend_g:
        g = pend_g[0]
        ex = g.get("exercise_name") or "WEIGHT"
        nodes.append(("na", "⭐", f"{ex}<br>{g['target_value']:g}kg"))
        for g in pend_g[1:]:
            ex = g.get("exercise_name") or "WEIGHT"
            nodes.append(("nl", "🔒", f"{ex}<br>{g['target_value']:g}kg"))
    nodes.append(("nc", "🏰", "CASTLE<br>BOSS"))

    if not goals:
        map_html = '<span style="color:#555;font-size:8px">NO GOALS SET</span>'
    else:
        map_html = ""
        for i, (cls, icon, lbl) in enumerate(nodes):
            sep = '<span class="conn">—</span>' if i < len(nodes) - 1 else ""
            map_html += (
                f'<div class="node {cls}">'
                f'<div class="node-box">{icon}</div>'
                f'<div class="node-lbl">{lbl}</div>'
                f'</div>{sep}'
            )

    # 進度條
    prog_html = ""
    for g in goals:
        ex = g.get("exercise_name") or "體重"
        lbl = f"{ex} {g['target_value']:g}kg"
        cur = f"{g['current']:g}kg" if g["current"] is not None else "N/A"
        pct = g["pct"]
        clr = "#FFD700" if pct >= 80 else "#5DB25C"
        done_mark = " ✓" if g["achieved"] else ""
        prog_html += (
            f'<div class="pb-row">'
            f'<div class="pb-lbl">{lbl}{done_mark}</div>'
            f'<div class="pb-track">'
            f'<div class="pb-fill" style="width:{pct}%;background:{clr}"></div>'
            f'</div>'
            f'<div class="pb-stat">{cur} ({pct}%)</div>'
            f'</div>'
        )
    if not prog_html:
        prog_html = '<div style="color:#555;font-size:8px">NO GOALS</div>'

    # 金幣
    coins_html = ""
    for c in coins:
        sym = "●" if c["filled"] else "○"
        fc = "#FFD700" if c["filled"] else "#333"
        dc = "#5C94FC" if c["today"] else "#555"
        coins_html += (
            f'<div class="coin">'
            f'<div class="ci" style="color:{fc}">{sym}</div>'
            f'<div class="cd" style="color:{dc}">{c["day"]}</div>'
            f'</div>'
        )

    # 訊息
    msg_html = ""
    for ic, tx in msgs:
        msg_html += (
            f'<div class="msg-row">'
            f'<span class="msg-ic">[{ic}]</span>'
            f'<span class="msg-tx">{tx}</span>'
            f'</div>'
        )

    css = _CSS  # 純字串，含 CSS 大括號，作為變數嵌入不觸發 f-string 解析
    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8">{css}</head>
<body>
<div class="hud">
  <span class="hud-p">PLAYER: {name}</span>
  <span class="hud-s">SCORE: {score_str}</span>
  <span class="hud-l">&#9829; LIVES: {lives_str}</span>
</div>
<div class="sec">
  <div class="sec-t">&#9876; LEVEL MAP</div>
  <div class="level-map">{map_html}</div>
</div>
<div class="sec">
  <div class="sec-t">&#9646; PROGRESS GAUGE</div>
  {prog_html}
</div>
<div class="sec">
  <div class="sec-t">&#9679; THIS WEEK'S COINS</div>
  <div class="coins">{coins_html}</div>
</div>
<div class="sec">
  <div class="sec-t">&#9658; SYSTEM MESSAGE</div>
  {msg_html}
</div>
</body>
</html>"""


# ── 頁面入口 ──

def render(user: dict):
    members = _all_members()
    if not members:
        st.warning("NO MEMBERS FOUND")
        return

    by_id = {m["member_id"]: m for m in members}
    mid = st.selectbox(
        "SELECT PLAYER",
        list(by_id.keys()),
        format_func=lambda x: by_id[x]["name"],
        key="pixel_home_member",
    )

    m, score, lives, goals, coins, msgs = _fetch(mid)
    html = _build_html(m, score, lives, goals, coins, msgs)
    components.html(html, height=600, scrolling=True)
