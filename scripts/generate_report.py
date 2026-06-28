# -*- coding: utf-8 -*-
"""命令行生成阶段 5 综合报告。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.backtest import run_backtest_detailed
from src.database import get_connection, get_stock_list
from src.report import generate_html_report, open_report
from src.strategy import DonchianBreakout, RsiStrategy, SmaCross


STRATEGY_REGISTRY = {
    "sma": {
        "label": "双均线交叉",
        "class": SmaCross,
        "params": ("fast", "slow"),
    },
    "rsi": {
        "label": "RSI超买超卖",
        "class": RsiStrategy,
        "params": ("period", "oversold", "overbought"),
    },
    "donchian": {
        "label": "唐奇安通道突破",
        "class": DonchianBreakout,
        "params": ("entry_period", "exit_period"),
    },
}


def get_stock_name(code: str) -> str:
    conn = get_connection("data/stocks.db")
    try:
        stocks = get_stock_list(conn)
    finally:
        conn.close()
    row = stocks[stocks["code"] == code]
    if row.empty:
        return ""
    return str(row.iloc[0]["name"])


def main() -> None:
    parser = argparse.ArgumentParser(description="生成 Alchequant HTML 综合报告")
    parser.add_argument("--code", default="000001", help="股票代码")
    parser.add_argument("--strategy", choices=STRATEGY_REGISTRY.keys(), default="sma",
                        help="报告策略：sma=双均线，rsi=RSI，donchian=唐奇安")
    parser.add_argument("--fast", type=int, default=5, help="短期均线周期")
    parser.add_argument("--slow", type=int, default=20, help="长期均线周期")
    parser.add_argument("--period", type=int, default=14, help="RSI 周期")
    parser.add_argument("--oversold", type=int, default=30, help="RSI 超卖阈值")
    parser.add_argument("--overbought", type=int, default=70, help="RSI 超买阈值")
    parser.add_argument("--entry-period", type=int, default=20, help="唐奇安突破周期")
    parser.add_argument("--exit-period", type=int, default=10, help="唐奇安离场周期")
    parser.add_argument("--cash", type=float, default=100000, help="初始资金")
    parser.add_argument("--commission", type=float, default=0.001, help="手续费率，例如 0.001 表示单边 0.1%")
    parser.add_argument("--position-pct", type=float, default=95, help="单次建仓比例，例如 95 表示使用 95% 可用资金")
    parser.add_argument("--no-open", action="store_true", help="只生成报告，不自动打开 HTML 文件")
    parser.add_argument("--llm", action="store_true", help="启用 AI 增强报告文字")
    parser.add_argument("--llm-api-key", default="", help="AI API Key；留空读取 LLM_API_KEY 或 OPENAI_API_KEY")
    parser.add_argument("--llm-base-url", default="", help="OpenAI-compatible Base URL")
    parser.add_argument("--llm-model", default="", help="模型名称")
    args = parser.parse_args()

    strategy_cfg = STRATEGY_REGISTRY[args.strategy]
    all_params = {
        "fast": args.fast,
        "slow": args.slow,
        "period": args.period,
        "oversold": args.oversold,
        "overbought": args.overbought,
        "entry_period": args.entry_period,
        "exit_period": args.exit_period,
    }
    params = {key: all_params[key] for key in strategy_cfg["params"]}
    result = run_backtest_detailed(
        args.code,
        strategy_cfg["class"],
        cash=args.cash,
        commission=args.commission,
        position_pct=args.position_pct,
        strategy_params=params,
    )
    report_path = generate_html_report(
        result,
        stock_code=args.code,
        stock_name=get_stock_name(args.code),
        strategy_name=strategy_cfg["label"],
        strategy_params=params,
        ai_config={
            "enabled": args.llm,
            "api_key": args.llm_api_key,
            "base_url": args.llm_base_url,
            "model": args.llm_model,
        },
    )
    print(report_path)
    if not args.no_open:
        open_report(report_path)


if __name__ == "__main__":
    main()
