import time
import akshare as ak
import pandas as pd


def get_hs300_stocks() -> pd.DataFrame:
    """获取沪深300成分股列表"""
    df = ak.index_stock_cons(symbol="000300")
    if df is None or df.empty:
        raise ValueError("沪深300成分股数据为空")
    df = df.rename(columns={"品种代码": "code", "品种名称": "name"})
    df = df[["code", "name"]]
    df["code"] = df["code"].astype(str).str.zfill(6)
    return df.reset_index(drop=True)


def get_stock_daily(code: str, start_date: str = "20150101", end_date: str = "20251231") -> pd.DataFrame:
    """下载单只股票日线历史数据

    Args:
        code: 股票代码，6位字符串
        start_date: 起始日期 YYYYMMDD
        end_date: 截止日期 YYYYMMDD
    """
    code = str(code).zfill(6)
    df = ak.stock_zh_a_hist(
        symbol=code,
        period="daily",
        start_date=start_date,
        end_date=end_date,
        adjust="qfq",
    )
    if df is None or df.empty:
        return pd.DataFrame()

    df = df.rename(columns={
        "日期": "date",
        "开盘": "open",
        "最高": "high",
        "最低": "low",
        "收盘": "close",
        "成交量": "volume",
    })
    df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
    df = df[["date", "open", "high", "low", "close", "volume"]]
    df["code"] = code
    return df


def download_all_stocks(stocks: pd.DataFrame, start_date: str = "20150101",
                        end_date: str = "20251231", delay: float = 0.5):
    """批量下载股票数据（带延迟防封）
    
    Yields: (idx, code, name, df)
    """
    total = len(stocks)
    for idx, row in stocks.iterrows():
        code = row["code"]
        name = row["name"]
        try:
            df = get_stock_daily(code, start_date, end_date)
            time.sleep(delay)
            yield idx, code, name, df
        except Exception as e:
            print(f"[{idx+1}/{total}] {code} {name} 下载失败: {e}")
            time.sleep(delay)
            yield idx, code, name, pd.DataFrame()
