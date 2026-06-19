"""
labels.py — 資料庫代碼 -> 中文顯示的對照表（各頁共用）
資料庫存英文代碼，畫面顯示中文，改用詞不必動資料。
"""

GOAL_LABELS = {"lose_weight": "減重", "gain_muscle": "增肌", "maintain": "維持"}

GENDER_LABELS = {"male": "男", "female": "女", "other": "其他"}

STATUS_LABELS = {"active": "使用中", "frozen": "凍結", "expired": "到期"}
# 會籍狀態顏色：使用中=綠、凍結=黃、到期=紅
STATUS_COLORS = {"active": "#16a34a", "frozen": "#ca8a04", "expired": "#dc2626"}

PLAN_TYPE_LABELS = {
    "monthly": "月費",
    "class_pack": "堂數包",
    "personal_training": "私教",
}

PAYMENT_TYPE_LABELS = {
    "membership_fee": "會籍費",
    "add_on_class": "加購課程",
    "personal_training": "私教課",
}

METHOD_LABELS = {"cash": "現金", "card": "刷卡", "transfer": "轉帳"}
