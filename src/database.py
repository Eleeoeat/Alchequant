import sqlite3
import pandas as pd
from pathlib import Path


def get_connection(db_path: str = "data/stocks.db") -> sqlite3.Connection:
    """获取数据库连接"""
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(db_path: str = "data/stocks.db"):
    """初始化数据库表结构"""
    conn = get_connection(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS stocks (
            code TEXT PRIMARY KEY,
            name TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS daily (
            code TEXT NOT NULL,
            date TEXT NOT NULL,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            volume REAL,
            PRIMARY KEY (code, date),
            FOREIGN KEY (code) REFERENCES stocks(code)
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_daily_code_date ON daily(code, date)
    """)
    conn.commit()
    return conn


def save_stocks(conn: sqlite3.Connection, stocks_df: pd.DataFrame):
    """保存或更新成分股列表"""
    records = stocks_df[["code", "name"]].to_dict("records")
    conn.executemany(
        "INSERT OR REPLACE INTO stocks (code, name) VALUES (:code, :name)",
        records,
    )
    conn.commit()


def save_daily_data(conn: sqlite3.Connection, code: str, df: pd.DataFrame):
    """保存日线数据（跳过重复主键）"""
    if df.empty:
        return
    records = df[["code", "date", "open", "high", "low", "close", "volume"]].to_dict("records")
    conn.executemany(
        """INSERT OR IGNORE INTO daily (code, date, open, high, low, close, volume)
           VALUES (:code, :date, :open, :high, :low, :close, :volume)""",
        records,
    )
    conn.commit()


def get_latest_date(conn: sqlite3.Connection, code: str) -> str | None:
    """获取某只股票在数据库中的最新日期"""
    cursor = conn.execute(
        "SELECT MAX(date) FROM daily WHERE code = ?", (code,)
    )
    row = cursor.fetchone()
    return row[0] if row else None


def get_stock_data(conn: sqlite3.Connection, code: str,
                   start: str | None = None, end: str | None = None) -> pd.DataFrame:
    """查询指定股票日线数据"""
    query = "SELECT date, open, high, low, close, volume FROM daily WHERE code = ?"
    params = [code]
    if start:
        query += " AND date >= ?"
        params.append(start)
    if end:
        query += " AND date <= ?"
        params.append(end)
    query += " ORDER BY date ASC"
    df = pd.read_sql_query(query, conn, params=params)
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"])
    return df


def get_stock_list(conn: sqlite3.Connection) -> pd.DataFrame:
    """获取数据库中所有成分股"""
    return pd.read_sql_query("SELECT code, name FROM stocks ORDER BY code", conn)


def get_stock_count(conn: sqlite3.Connection) -> int:
    """获取数据库中已有数据的股票数量"""
    cursor = conn.execute(
        "SELECT COUNT(DISTINCT code) FROM daily"
    )
    return cursor.fetchone()[0]


def get_date_range(conn: sqlite3.Connection, code: str) -> tuple[str | None, str | None]:
    """获取某只股票的数据日期范围"""
    cursor = conn.execute(
        "SELECT MIN(date), MAX(date) FROM daily WHERE code = ?", (code,)
    )
    row = cursor.fetchone()
    if row:
        return row[0], row[1]
    return None, None
