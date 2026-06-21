"""
app.py — 健身房 CRM 主程式
執行: streamlit run app.py
結構:
  未登入 -> 顯示登入頁
  已登入 -> 依角色顯示側邊欄 -> 分派到對應頁面
"""
import streamlit as st

from auth import verify_login, pages_for_role, can_access, ROLE_LABELS
import members_page
import checkin_page
import training_page
import goals_page
import rfm_page
import alert_page
import dashboard_page
import pixel_home

st.set_page_config(page_title="健身房 CRM", page_icon="💪", layout="wide")

# ── 全域像素風格 CSS ──
_PIXEL_CSS = """
<link href="https://fonts.googleapis.com/css2?family=Press+Start+2P&display=swap" rel="stylesheet">
<style>
/* 主背景 */
.stApp { background-color: #1a1a2e !important; }
.main .block-container { background-color: #1a1a2e !important; padding-top: 24px !important; }

/* 側邊欄 */
[data-testid="stSidebar"] { background-color: #16213e !important; }
[data-testid="stSidebar"] h3 { color: #FFD700 !important; font-family: 'Press Start 2P', cursive !important; font-size: 11px !important; }
[data-testid="stSidebar"] .stCaption p { color: #aaaaaa !important; font-size: 8px !important; }
[data-testid="stSidebar"] label { color: #FFD700 !important; font-family: 'Press Start 2P', cursive !important; font-size: 8px !important; line-height: 2; }

/* 標題 */
h1 { font-family: 'Press Start 2P', cursive !important; color: #FFD700 !important; font-size: 16px !important; letter-spacing: 1px !important; }
h2 { font-family: 'Press Start 2P', cursive !important; color: #FFD700 !important; font-size: 13px !important; }
h3 { font-family: 'Press Start 2P', cursive !important; color: #FFD700 !important; font-size: 11px !important; }

/* 文字 */
.stMarkdown p, p { color: #ffffff !important; }
.stCaption p { color: #888888 !important; font-size: 9px !important; }

/* 按鈕 */
.stButton > button {
    background-color: #FFD700 !important;
    color: #000000 !important;
    font-family: 'Press Start 2P', cursive !important;
    font-size: 9px !important;
    border: 3px solid #000000 !important;
    border-radius: 0px !important;
    box-shadow: 4px 4px 0px #000000 !important;
    padding: 8px 14px !important;
    transition: transform 0.08s, box-shadow 0.08s;
}
.stButton > button:hover {
    transform: translateY(-2px) !important;
    box-shadow: 6px 6px 0px #000000 !important;
}
.stButton > button:active {
    transform: translateY(1px) !important;
    box-shadow: 2px 2px 0px #000000 !important;
}

/* 輸入框 */
.stTextInput input, .stNumberInput input, .stTextArea textarea {
    background-color: #000000 !important;
    color: #ffffff !important;
    border: 2px solid #FFD700 !important;
    border-radius: 0px !important;
}
.stSelectbox div[data-baseweb="select"] > div:first-child {
    background-color: #000000 !important;
    border: 2px solid #FFD700 !important;
    border-radius: 0px !important;
}
.stSelectbox span { color: #ffffff !important; }

/* Metric 卡片 */
[data-testid="metric-container"] {
    background-color: #000000 !important;
    border: 2px solid #FFD700 !important;
    border-radius: 0px !important;
    padding: 12px !important;
}
[data-testid="stMetricValue"] { color: #FFD700 !important; }
[data-testid="stMetricLabel"] { color: #ffffff !important; }
[data-testid="stMetricDelta"] { font-size: 9px !important; }

/* Tabs */
[data-baseweb="tab-list"] { background-color: #16213e !important; gap: 4px !important; }
[data-baseweb="tab"] {
    font-family: 'Press Start 2P', cursive !important;
    font-size: 8px !important;
    background-color: #16213e !important;
    color: #FFD700 !important;
    border: 2px solid #FFD700 !important;
    border-radius: 0px !important;
    padding: 8px 12px !important;
}
[data-baseweb="tab"][aria-selected="true"] {
    background-color: #FFD700 !important;
    color: #000000 !important;
}

/* 分隔線 = 磚塊 */
hr {
    border: 0 !important;
    height: 6px !important;
    background: repeating-linear-gradient(
        to right, #FFD700 0px, #FFD700 14px, #000000 14px, #000000 18px
    ) !important;
    margin: 16px 0 !important;
    opacity: 0.65;
}

/* 提示框 */
[data-testid="stNotificationContent"] { border-radius: 0 !important; }
div[data-baseweb="notification"] { border-radius: 0 !important; }
.stSuccess > div { background-color: #0d2b0d !important; border: 2px solid #5DB25C !important; border-radius: 0 !important; }
.stWarning > div { background-color: #2b1200 !important; border: 2px solid #ff8800 !important; border-radius: 0 !important; }
.stError   > div { background-color: #2b0d0d !important; border: 2px solid #ff4444 !important; border-radius: 0 !important; }
.stInfo    > div { background-color: #0d1a2b !important; border: 2px solid #5C94FC !important; border-radius: 0 !important; }

/* Dataframe */
[data-testid="stDataFrame"] { border: 1px solid #FFD700 !important; }

/* Checkbox */
.stCheckbox label { color: #ffffff !important; }
</style>
"""


# ---------------- 登入頁 ----------------
def login_view():
    st.title("健身房 CRM")
    st.subheader("INSERT COIN TO PLAY")

    with st.form("login_form"):
        username = st.text_input("PLAYER ID")
        password = st.text_input("PASSWORD", type="password")
        submitted = st.form_submit_button("▶ START GAME", type="primary")

    if submitted:
        user = verify_login(username, password)
        if user:
            st.session_state.user = user
            st.rerun()
        else:
            st.error("GAME OVER — WRONG ID OR PASSWORD")


# ---------------- 側邊欄 + 分派 ----------------
def main_view():
    user = st.session_state.user

    with st.sidebar:
        st.markdown(f"### {user['name']}")
        st.caption(f"ROLE: {ROLE_LABELS.get(user['role'], user['role']).upper()}")
        st.divider()

        pages = pages_for_role(user["role"])
        choice = st.radio("MENU", pages, label_visibility="collapsed")

        st.divider()
        if st.button("⏏ LOGOUT", use_container_width=True):
            del st.session_state.user
            st.rerun()

    if not can_access(user["role"], choice):
        st.error("ACCESS DENIED")
        return

    render_page(choice, user)


# ---------------- 頁面分派 ----------------
def render_page(page: str, user: dict):
    st.title(page)

    if page == "🎮 ADVENTURE MAP":
        pixel_home.render(user)
    elif page == "🗺️ DASHBOARD":
        dashboard_page.render(user)
    elif page == "🏠 PLAYER SELECT":
        members_page.render(user)
    elif page == "💪 TRAINING LOG":
        training_page.render(user)
    elif page == "📋 CHECK IN":
        checkin_page.render(user)
    elif page == "🏆 GOALS":
        goals_page.render(user)
    elif page == "📊 STATS":
        rfm_page.render(user)
    elif page == "⚠️ DANGER ZONE":
        alert_page.render(user)


# ---------------- 進入點 ----------------
def main():
    st.markdown(_PIXEL_CSS, unsafe_allow_html=True)
    if "user" not in st.session_state:
        login_view()
    else:
        main_view()


main()
