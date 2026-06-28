"""Alchequant 发布版自检脚本。

用于验证一台新电脑克隆项目并安装依赖后，核心链路是否可复现：
依赖导入 -> 数据库读取 -> 回测 -> 因子计算 -> HTML 报告生成。
"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def ok(message: str) -> None:
    print(f"[OK] {message}")


def check_imports() -> None:
    packages = [
        "akshare",
        "backtrader",
        "numpy",
        "pandas",
        "plotly",
        "streamlit",
    ]
    for package in packages:
        importlib.import_module(package)
    ok("核心依赖导入成功")


def check_database() -> None:
    from src.database import get_connection, get_stock_count, get_stock_data, get_stock_list

    db_path = ROOT / "data" / "stocks.db"
    if not db_path.exists():
        raise FileNotFoundError(f"缺少示例数据库: {db_path}")

    conn = get_connection(str(db_path))
    try:
        stocks = get_stock_list(conn)
        data_count = get_stock_count(conn)
        sample = get_stock_data(conn, "000001")
    finally:
        conn.close()

    if len(stocks) == 0:
        raise RuntimeError("stocks 表为空")
    if data_count == 0:
        raise RuntimeError("daily 表没有任何股票日线数据")
    if sample.empty:
        raise RuntimeError("示例股票 000001 无日线数据")

    ok(f"示例数据库可用：股票清单 {len(stocks)} 只，有日线数据 {data_count} 只")


def check_backtest() -> dict:
    from src.backtest import run_backtest_detailed
    from src.strategy import SmaCross

    result = run_backtest_detailed(
        "000001",
        SmaCross,
        db_path=str(ROOT / "data" / "stocks.db"),
        strategy_params={"fast": 5, "slow": 20},
    )
    summary = result["summary"]
    if result["equity_curve"].empty:
        raise RuntimeError("回测净值曲线为空")
    ok(
        "回测通过："
        f"总收益率 {summary['total_return'] * 100:.2f}%，"
        f"交易 {summary['total_trades']} 笔"
    )
    return result


def check_factors() -> None:
    from src.factors import calculate_factor_scores

    factors = calculate_factor_scores(db_path=str(ROOT / "data" / "stocks.db"))
    if factors.empty:
        raise RuntimeError("因子计算结果为空")
    ok(f"因子计算通过：纳入 {len(factors)} 只股票")


def check_report(result: dict) -> None:
    from src.report import generate_html_report

    out_dir = ROOT / "results" / "smoke_test"
    path = generate_html_report(
        result,
        stock_code="000001",
        stock_name="深发展A",
        strategy_name="双均线交叉",
        strategy_params={"fast": 5, "slow": 20},
        output_dir=str(out_dir),
    )
    if not path.exists() or path.stat().st_size == 0:
        raise RuntimeError("HTML 报告未成功生成")
    ok(f"HTML 报告生成通过：{path.relative_to(ROOT)}")


def main() -> None:
    print("Alchequant smoke test")
    print(f"Project: {ROOT}")
    check_imports()
    check_database()
    result = check_backtest()
    check_factors()
    check_report(result)
    print("\n全部自检通过。")


if __name__ == "__main__":
    main()
