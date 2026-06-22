"""
pixel_home.py — 🎮 ADVENTURE MAP 冒險主頁
Mario 天空藍風格個人儀表板：HUD / ? 磚塊 / 任務進度 / 關卡地圖 / 本週出勤 / 訊息框
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
body { background: #5C94FC; color: #fff; font-family: 'Press Start 2P', cursive;
       font-size: 12px; padding: 10px; }

.hud { background: #000; padding: 10px 16px;
       display: flex; justify-content: space-between; align-items: center;
       margin-bottom: 10px; flex-wrap: wrap; gap: 10px; }
.hud-cell { display: flex; flex-direction: column; gap: 5px; text-align: center; min-width: 76px; }
.hud-label { font-size: 9px; color: #aaa; letter-spacing: 1px; }
.hud-value { font-size: 12px; }
.hud-p .hud-value { color: #5C94FC; }
.hud-s .hud-value { color: #FFD700; }
.hud-c .hud-value { color: #FFD700; }
.hud-l .hud-value { color: #ff5555; }

.qblocks { display: flex; gap: 5px; margin-bottom: 10px; }
.qblock { width: 44px; height: 44px; display: flex; align-items: center;
          justify-content: center; font-size: 16px; font-weight: bold;
          background: #C84B00; color: #FFD700;
          border: 2px solid #7A2E00;
          box-shadow: inset 1px 1px 0 #e06000, 2px 2px 0 #000; }
.qblock.empty { color: #9a3500; }

.mission { background: #2A5A9A; border: 3px solid #000; padding: 12px; margin-bottom: 10px; }
.map-sec  { background: #2A5A9A; border: 3px solid #000; padding: 12px 12px 0 12px;
            margin-bottom: 0; }
.sec-t { color: #FFD700; font-size: 10px; margin-bottom: 10px; letter-spacing: 1px; }

.pb-row { margin-bottom: 12px; }
.pb-lbl { font-size: 9px; color: #fff; margin-bottom: 5px; }
.pb-track { background: #1a3a5c; border: 1px solid #000; height: 16px; position: relative; overflow: hidden; }
.pb-fill  { height: 100%; position: absolute; left: 0; top: 0; }
.pb-right { display: flex; justify-content: space-between; margin-top: 3px; }
.pb-val   { font-size: 8px; color: #ccc; }
.pb-pct   { font-size: 8px; color: #aaa; }

.map-row { display: flex; align-items: flex-end; gap: 0; padding-bottom: 8px; }
.level-map { display: flex; align-items: center; flex-wrap: nowrap; gap: 4px;
              flex: 1; overflow-x: auto; padding-bottom: 2px; }
.node { display: flex; flex-direction: column; align-items: center; gap: 4px; }
.node-box { width: 52px; height: 52px; display: flex; align-items: center;
             justify-content: center; font-size: 24px; border: 3px solid; }
.node-lbl { font-size: 8px; text-align: center; line-height: 1.6; max-width: 62px; }
.nd .node-box { border-color: #5DB25C; background: #1a4a1a; }
.nd .node-lbl { color: #5DB25C; }
.na .node-box { border-color: #FFD700; background: #3a2800; }
.na .node-lbl { color: #FFD700; }
.nl .node-box { border-color: #444; background: #111; }
.nl .node-lbl { color: #666; }
.nc .node-box { border-color: #888; background: #2a2a2a; }
.nc .node-lbl { color: #aaa; }
@keyframes blink { 0%,100% { opacity:1; } 50% { opacity:0.3; } }
.na .node-box { animation: blink 1s infinite; }
.conn { color: #fff; font-size: 22px; margin-bottom: 28px; flex-shrink: 0; }

.pipe-wrap { display: flex; flex-direction: column; align-items: center;
             margin-left: 14px; flex-shrink: 0; align-self: flex-end; }
.pipe-cap  { background: #5DB25C; border: 2px solid #2a6a2a; width: 34px; height: 12px; }
.pipe-body { background: #3a8a3a; border: 2px solid #2a6a2a; border-top: none; width: 24px; height: 38px; }

.floor { background: #5DB25C; height: 20px; border-top: 4px solid #2a6a2a;
         margin-bottom: 10px; }

.week-sec { background: #000; padding: 12px 16px; margin-bottom: 10px;
            display: flex; justify-content: space-between; align-items: center; }
.week-left { display: flex; align-items: center; gap: 14px; }
.week-circles { display: flex; gap: 8px; align-items: flex-end; }
.witem { display: flex; flex-direction: column; align-items: center; gap: 4px; }
.wc { font-size: 20px; }
.wd { font-size: 7px; }
.week-count { font-size: 9px; color: #aaa; }
.view-btn { background: #FFD700; color: #000; font-family: 'Press Start 2P', cursive;
            font-size: 9px; padding: 10px 12px; border: none;
            box-shadow: 2px 2px 0 #000; }

.msg-sec  { background: #000; border: 2px solid #333; padding: 14px; }
.msg-text { color: #fff; font-size: 10px; line-height: 2.6; }
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

    # 本週出勤（週一~週日）
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

    # 訊息資料
    msgs = []
    last_ci = conn.execute(
        "SELECT date(check_in_at) AS d FROM check_ins WHERE member_id=? "
        "ORDER BY check_in_at DESC LIMIT 1", (member_id,)
    ).fetchone()
    if last_ci:
        ago = (today - date.fromisoformat(last_ci["d"])).days
        msgs.append(("CHECK-IN", "TODAY" if ago == 0 else str(ago)))
    else:
        msgs.append(("CHECK-IN", "NONE"))

    if isinstance(lives, int):
        if lives < 14:
            msgs.append(("ALERT", str(lives)))
        else:
            msgs.append(("LIVES", str(lives)))

    lt = conn.execute(
        "SELECT MAX(training_date) AS d FROM training_sessions WHERE member_id=?", (member_id,)
    ).fetchone()
    if lt and lt["d"]:
        days_nt = (today - date.fromisoformat(lt["d"])).days
        if days_nt > 21:
            msgs.append(("WARN_TRAIN", str(days_nt)))

    conn.close()
    return m, score, lives, goals, coins, msgs


# ── 訊息合併為中文句子 ──

def _combined_msg(msgs):
    parts = []
    for ic, tx in msgs:
        if ic == "CHECK-IN":
            if tx == "TODAY":
                parts.append("今日已報到！繼續保持！")
            elif tx == "NONE":
                parts.append("尚無到館紀錄，快來開始冒險！")
            else:
                n = int(tx)
                if n > 30:
                    parts.append(f"距上次到館已 {n} 天！勇士，回來吧！")
                elif n > 7:
                    parts.append(f"距上次到館 {n} 天，加油！")
                else:
                    parts.append(f"距上次到館 {n} 天。")
        elif ic == "ALERT":
            parts.append(f"⚠ 會籍剩 {tx} 天，快來繼續你的冒險！")
        elif ic == "WARN_TRAIN":
            parts.append(f"⚠ 停訓 {tx} 天了，是時候練起來！")
    return "　".join(parts) if parts else "PRESS START ▶ 繼續你的冒險！"


# ── HTML 組裝（CSS 以變數嵌入，避免大括號轉義問題）──

def _build_html(m, score, lives, goals, coins, msgs):
    total_checkins = score // 100
    score_str = str(score).zfill(6)
    lives_str = f"&#9660;&#215;{lives}d" if isinstance(lives, int) else "&#9660;&#215;&#8734;"
    name = m["name"]

    # ? 磚塊（未達成目標數，最多 8 個）
    pending = sum(1 for g in goals if not g["achieved"])
    qblocks_html = ""
    for i in range(max(pending, 4)):
        css_cls = "qblock" if i < pending else "qblock empty"
        sym = "?" if i < pending else "&#9632;"
        qblocks_html += f'<div class="{css_cls}">{sym}</div>'

    # 任務進度條
    prog_html = ""
    for g in goals:
        ex = g.get("exercise_name") or "體重"
        pct = g["pct"]
        clr = "#FFD700" if pct >= 80 else "#5DB25C"
        done_mark = " &#10003;" if g["achieved"] else ""
        cur_str = f"{g['current']:g}kg" if g["current"] is not None else "N/A"
        tgt_str = f"{g['target_value']:g}kg"
        lbl = f"{ex} ({cur_str} &#8594; {tgt_str}){done_mark}"
        prog_html += (
            f'<div class="pb-row">'
            f'<div class="pb-lbl">{lbl}</div>'
            f'<div class="pb-track">'
            f'<div class="pb-fill" style="width:{pct}%;background:{clr}"></div>'
            f'</div>'
            f'<div class="pb-right">'
            f'<div class="pb-val">{cur_str} / {tgt_str}</div>'
            f'<div class="pb-pct">{pct}%</div>'
            f'</div>'
            f'</div>'
        )
    if not prog_html:
        prog_html = '<div style="color:#aaa;font-size:8px;text-align:center;padding:8px 0">NO GOALS SET</div>'

    # 關卡地圖節點
    done_g = [g for g in goals if g["achieved"]]
    pend_g = [g for g in goals if not g["achieved"]]
    nodes = []
    for g in done_g:
        ex = g.get("exercise_name") or "WEIGHT"
        nodes.append(("nd", "&#127942;", f"{ex}<br>{g['target_value']:g}kg"))
    if pend_g:
        g0 = pend_g[0]
        ex = g0.get("exercise_name") or "WEIGHT"
        nodes.append(("na", "&#127919;", f"{ex}<br>{g0['target_value']:g}kg"))
        for g in pend_g[1:]:
            ex = g.get("exercise_name") or "WEIGHT"
            nodes.append(("nl", "&#128274;", f"{ex}<br>{g['target_value']:g}kg"))
    nodes.append(("nc", "&#127984;", "CASTLE<br>BOSS"))

    map_html = ""
    if not goals:
        map_html = '<span style="color:#aaa;font-size:8px">NO GOALS SET</span>'
    else:
        for i, (cls, icon, lbl) in enumerate(nodes):
            sep = '<span class="conn">&#8212;</span>' if i < len(nodes) - 1 else ""
            map_html += (
                f'<div class="node {cls}">'
                f'<div class="node-box">{icon}</div>'
                f'<div class="node-lbl">{lbl}</div>'
                f'</div>{sep}'
            )

    # 本週出勤圓圈
    week_count = sum(1 for c in coins if c["filled"])
    coins_html = ""
    for c in coins:
        sym = "&#9679;" if c["filled"] else "&#9675;"
        wc_color = "#FFD700" if c["filled"] else "#444"
        wd_color = "#5C94FC" if c["today"] else "#666"
        coins_html += (
            f'<div class="witem">'
            f'<div class="wc" style="color:{wc_color}">{sym}</div>'
            f'<div class="wd" style="color:{wd_color}">{c["day"]}</div>'
            f'</div>'
        )

    combined = _combined_msg(msgs)
    css = _CSS

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8">{css}</head>
<body>

<div class="hud">
  <div class="hud-cell hud-p">
    <div class="hud-label">PLAYER</div>
    <div class="hud-value">{name}</div>
  </div>
  <div class="hud-cell hud-s">
    <div class="hud-label">SCORE</div>
    <div class="hud-value">{score_str}</div>
  </div>
  <div class="hud-cell hud-c">
    <div class="hud-label">COINS</div>
    <div class="hud-value">&#215;{total_checkins}</div>
  </div>
  <div class="hud-cell hud-l">
    <div class="hud-label">LIVES</div>
    <div class="hud-value">{lives_str}</div>
  </div>
</div>

<div class="qblocks">{qblocks_html}</div>

<div class="mission">
  <div class="sec-t">&#9646; MISSION PROGRESS</div>
  {prog_html}
</div>

<div class="map-sec">
  <div class="sec-t">&#9733; LEVEL MAP</div>
  <div class="map-row">
    <div class="level-map">{map_html}</div>
    <div class="pipe-wrap">
      <div class="pipe-cap"></div>
      <div class="pipe-body"></div>
    </div>
  </div>
</div>
<div class="floor"></div>

<div class="week-sec">
  <div class="week-left">
    <div class="week-circles">{coins_html}</div>
    <div class="week-count">{week_count} / 7</div>
  </div>
  <button class="view-btn">VIEW STATS &#9658;</button>
</div>

<div class="msg-sec">
  <div class="msg-text">{combined}</div>
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
        "SELECT PLAYER ▶",
        list(by_id.keys()),
        format_func=lambda x: by_id[x]["name"],
        key="pixel_home_member",
    )

    m, score, lives, goals, coins, msgs = _fetch(mid)
    html = _build_html(m, score, lives, goals, coins, msgs)
    components.html(html, height=850, scrolling=True)
