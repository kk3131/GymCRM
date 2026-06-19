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

st.set_page_config(page_title="健身房 CRM", page_icon="💪", layout="wide")


# ---------------- 登入頁 ----------------
def login_view():
    st.title("健身房 CRM 系統")
    st.subheader("請登入")

    # 用 st.form 把輸入打包，按 Enter 或按鈕才送出（避免每打一個字就重跑）
    with st.form("login_form"):
        username = st.text_input("帳號")
        password = st.text_input("密碼", type="password")
        submitted = st.form_submit_button("登入", type="primary")

    if submitted:
        user = verify_login(username, password)
        if user:
            st.session_state.user = user   # 把登入資訊存進 session，之後每次重跑都還在
            st.rerun()                     # 立刻重跑，切到已登入畫面
        else:
            st.error("帳號或密碼錯誤，或帳號已停用。")


# ---------------- 側邊欄 + 分派 ----------------
def main_view():
    user = st.session_state.user

    with st.sidebar:
        st.markdown(f"### {user['name']}")
        st.caption(f"角色：{ROLE_LABELS.get(user['role'], user['role'])}")
        st.divider()

        pages = pages_for_role(user["role"])     # 只列出這個角色能看的頁
        choice = st.radio("功能選單", pages, label_visibility="collapsed")

        st.divider()
        if st.button("登出", use_container_width=True):
            del st.session_state.user
            st.rerun()

    # 二次把關：即使有人想辦法跳到沒權限的頁，也擋下來
    if not can_access(user["role"], choice):
        st.error("您沒有權限檢視此頁面。")
        return

    render_page(choice, user)


# ---------------- 各頁面（內容之後逐項補上）----------------
def render_page(page: str, user: dict):
    st.title(page)

    if page == "會員管理":
        members_page.render(user)
    elif page == "訓練紀錄":
        training_page.render(user)
    elif page == "到館簽到":
        checkin_page.render(user)
    elif page == "RFM 分析":
        st.info("RFM 分析（僅管理者）—— 開發中。")
    elif page == "流失預警":
        st.info("流失預警（僅管理者）—— 開發中。")


# ---------------- 進入點 ----------------
def main():
    if "user" not in st.session_state:
        login_view()
    else:
        main_view()


main()
