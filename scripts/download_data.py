"""一键下载沪深300全部股票数据到 SQLite。"""
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data_fetcher import get_hs300_stocks, get_stock_daily
from src.database import init_db, save_stocks, save_daily_data, get_latest_date, get_stock_count


def main():
    db_path = ROOT / "data" / "stocks.db"
    conn = init_db(db_path)

    print("正在获取沪深300成分股列表...")
    stocks = get_hs300_stocks()
    save_stocks(conn, stocks)
    print(f"已保存 {len(stocks)} 只成分股到 stocks 表")

    existing = get_stock_count(conn)
    print(f"数据库中已有 {existing} 只股票的数据")

    total = len(stocks)
    start_date = "20150101"
    end_date = "20251231"

    for idx, row in stocks.iterrows():
        code = row["code"]
        name = row["name"]

        latest = get_latest_date(conn, code)
        if latest and latest >= "2025-01-01":
            print(f"[{idx+1}/{total}] {code} {name} 数据已是最新，跳过")
            continue

        fetch_start = latest[:4] + "0101" if latest else start_date
        if latest:
            print(f"[{idx+1}/{total}] {code} {name} 增量更新 ({latest} → {end_date})")
        else:
            print(f"[{idx+1}/{total}] {code} {name} 首次下载...")

        try:
            df = get_stock_daily(code, fetch_start, end_date)
            if df.empty:
                print(f"    无数据")
            else:
                save_daily_data(conn, code, df)
                print(f"    保存 {len(df)} 条记录")
        except Exception as e:
            print(f"    下载失败: {e}")

        time.sleep(0.5)

    final_count = get_stock_count(conn)
    conn.close()
    print(f"\n完成！共 {final_count} 只股票有数据")


if __name__ == "__main__":
    main()
