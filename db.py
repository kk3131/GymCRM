"""
db.py — 資料庫連線與初始化
* get_connection() 回傳已開啟外鍵支援的 sqlite3.Connection
* 第一次呼叫時自動執行 schema.sql 建表（冪等：CREATE TABLE IF NOT EXISTS）
"""
import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).parent
DB_PATH  = BASE_DIR / "gym.db"
SQL_PATH = BASE_DIR / "schema.sql"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row          # 讓查詢結果可用欄位名稱取值
    conn.execute("PRAGMA foreign_keys = ON")
    _init_schema(conn)
    return conn


def _init_schema(conn: sqlite3.Connection) -> None:
    """讀 schema.sql 並執行；CREATE TABLE IF NOT EXISTS 保證安全重複執行。"""
    sql = SQL_PATH.read_text(encoding="utf-8")
    conn.executescript(sql)
    _auto_seed(conn)


_seeding = False  # 防止 seed.seed() 內的 get_connection() 再次觸發 _auto_seed

def _auto_seed(conn: sqlite3.Connection) -> None:
    """資料庫空白時自動植入種子資料（雲端部署用，避免每次重啟都要手動 seed）。"""
    global _seeding
    if _seeding:
        return
    count = conn.execute("SELECT COUNT(*) FROM members").fetchone()[0]
    if count == 0:
        _seeding = True
        try:
            import seed
            seed.seed()
        finally:
            _seeding = False
