"""
mailer.py — Gmail SMTP 發信工具
憑證從環境變數讀取：
  GMAIL_USER         寄件人 Gmail 帳號（如 liufu0831@gmail.com）
  GMAIL_APP_PASSWORD Google 應用程式密碼（16 碼，非登入密碼）
本機開發：在專案根目錄建立 .env 並填入上述兩個變數。
"""
import os
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

GMAIL_USER = os.environ.get("GMAIL_USER", "")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "")


def is_configured() -> bool:
    return bool(GMAIL_USER and GMAIL_APP_PASSWORD)


def send_alert_email(to_email: str, member_name: str, alert_type: str, note: str = "") -> None:
    """發送流失預警提醒郵件。alert_type: 'no_checkin' | 'plateau'"""
    if not is_configured():
        raise RuntimeError("未設定 GMAIL_USER / GMAIL_APP_PASSWORD 環境變數")

    subject, body = _build_content(member_name, alert_type, note)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = GMAIL_USER
    msg["To"] = to_email
    msg.attach(MIMEText(body, "plain", "utf-8"))

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
        server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        server.sendmail(GMAIL_USER, to_email, msg.as_string())


def _build_content(member_name: str, alert_type: str, note: str):
    note_line = f"\n備註：{note}" if note else ""

    if alert_type == "no_checkin":
        subject = f"【健身房關心您】{member_name}，好久不見！"
        body = (
            f"親愛的 {member_name}，\n\n"
            f"我們發現您已有一段時間未到館訓練，非常掛念您的健身狀況！\n\n"
            f"不論是想重拾健身習慣，還是有任何需要調整的地方，"
            f"歡迎隨時回來，我們都在這裡支持您。"
            f"{note_line}\n\n"
            f"期待再次見到您！\n健身房 CRM 團隊"
        )
    else:
        subject = f"【健身房關心您】{member_name}，教練為您準備了新計畫！"
        body = (
            f"親愛的 {member_name}，\n\n"
            f"根據您的訓練紀錄，我們注意到您最近的進步可能遇到了瓶頸。\n\n"
            f"這是每位健身者都會遇到的正常現象！"
            f"教練已為您準備了調整建議，歡迎預約下次訓練，一起突破瓶頸！"
            f"{note_line}\n\n"
            f"加油！\n健身房 CRM 團隊"
        )
    return subject, body
