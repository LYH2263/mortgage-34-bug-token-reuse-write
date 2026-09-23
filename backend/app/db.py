import sqlite3
from app.config import DATA_DIR, DB_FILENAME
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / DB_FILENAME
def connect() -> sqlite3.Connection:
    # isolation_level=None：关闭 Python 驱动的隐式事务，改为显式
    # BEGIN/COMMIT 控制；否则手写的 BEGIN IMMEDIATE 会与隐式事务冲突，
    # 并发下无法靠行级认领保证“一枚回执只能落库一次”。
    c = sqlite3.connect(DB_PATH, isolation_level=None)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA busy_timeout=5000")
    return c
