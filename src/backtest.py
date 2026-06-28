"""回测引擎封装 — 简化 Backtrader Cerebro 的调用流程"""
import io
import sys
import pandas as pd
import numpy as np
import backtrader as bt
from src.database import get_connection, get_stock_data


class TradeRecorder(bt.Analyzer):
    """自定义分析器：通过 notify_order 记录每笔交易的真实成交价"""

    def __init__(self):
        self._trades = []
        self._pending_buy = {}

    def notify_order(self, order):
        if order.status != order.Completed:
            return
        data = order.data
        if order.isbuy():
            self._pending_buy[data] = {
                'price': order.executed.price,
                'size': order.executed.size,
                'date': bt.num2date(order.executed.dt).date(),
            }
        else:
            buy_info = self._pending_buy.pop(data, None)
            if buy_info:
                sell_price = order.executed.price
                sell_size = abs(order.executed.size)
                pnl = (sell_price - buy_info['price']) * sell_size
                self._trades.append({
                    'date_in': buy_info['date'],
                    'date_out': bt.num2date(order.executed.dt).date(),
                    'price_in': buy_info['price'],
                    'price_out': sell_price,
                    'size': sell_size,
                    'pnl': pnl,
                    'pnlcomm': None,
                })

    def notify_trade(self, trade):
        if trade.isclosed and self._trades:
            self._trades[-1]['pnlcomm'] = trade.pnlcomm

    def get_analysis(self):
        return self._trades


class EquityCurve(bt.Analyzer):
    """自定义分析器：记录每日净值曲线"""

    def __init__(self):
        self._curve = []

    def next(self):
        dt = self.datas[0].datetime.date(0)
        value = self.strategy.broker.getvalue()
        self._curve.append({'date': dt, 'value': value})

    def get_analysis(self):
        df = pd.DataFrame(self._curve)
        if not df.empty:
            df['date'] = pd.to_datetime(df['date'])
        return df


def load_data_to_backtrader(df: pd.DataFrame) -> bt.feeds.PandasData:
    df = df.copy()
    df['date'] = pd.to_datetime(df['date'])
    df = df.set_index('date').sort_index()
    return bt.feeds.PandasData(dataname=df)


def _build_summary(strat, df_len: int, init_value: float, final_value: float,
                   strategy_name: str, code: str, commission: float,
                   position_pct: float) -> dict:
    trades = strat.analyzers.trades.get_analysis()
    sharpe = strat.analyzers.sharpe.get_analysis()
    drawdown = strat.analyzers.drawdown.get_analysis()
    sqn = strat.analyzers.sqn.get_analysis()

    total_closed = trades.get('total', {}).get('closed', 0) or 0
    won = trades.get('won', {}).get('total', 0) or 0
    lost = trades.get('lost', {}).get('total', 0) or 0

    win_rate = won / total_closed if total_closed > 0 else 0

    gross_won = trades.get('won', {}).get('pnl', {}).get('total', 0) or 0
    gross_lost = trades.get('lost', {}).get('pnl', {}).get('total', 0) or 0
    if gross_lost != 0:
        profit_factor = gross_won / abs(gross_lost)
    elif gross_won > 0:
        profit_factor = float('inf')
    else:
        profit_factor = 0.0

    total_return = (final_value - init_value) / init_value
    years = df_len / 252
    annual_return = (1 + total_return) ** (1 / years) - 1 if years > 0 else 0

    sharpe_val = sharpe.get('sharperatio')
    if sharpe_val is None or not np.isfinite(sharpe_val):
        sharpe_val = 0.0

    return {
        'code': code,
        'strategy': strategy_name,
        'initial_cash': init_value,
        'final_value': final_value,
        'commission': commission,
        'position_pct': position_pct,
        'total_return': total_return,
        'annual_return': annual_return,
        'total_trades': total_closed,
        'win_trades': won,
        'loss_trades': lost,
        'win_rate': win_rate,
        'profit_factor': profit_factor,
        'max_drawdown': (drawdown.get('max', {}).get('drawdown', 0) or 0) / 100,
        'max_drawdown_len': drawdown.get('max', {}).get('len', 0) or 0,
        'sharpe_ratio': sharpe_val,
        'sqn': sqn.get('sqn', 0) or 0,
        'data_days': df_len,
    }


def _make_cerebro(data, strategy_class, strategy_params, cash, commission,
                  position_pct):
    cerebro = bt.Cerebro()
    cerebro.adddata(data)
    cerebro.addstrategy(strategy_class, **(strategy_params or {}))
    cerebro.broker.setcash(cash)
    cerebro.broker.setcommission(commission=commission)
    cerebro.addsizer(bt.sizers.PercentSizer, percents=position_pct)

    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trades')
    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe', riskfreerate=0.02,
                        annualize=True, timeframe=bt.TimeFrame.Days)
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
    cerebro.addanalyzer(bt.analyzers.SQN, _name='sqn')
    cerebro.addanalyzer(TradeRecorder, _name='trade_recorder')
    cerebro.addanalyzer(EquityCurve, _name='equity')

    return cerebro


def run_backtest_detailed(code: str, strategy_class,
                          db_path: str = 'data/stocks.db',
                          cash: float = 100000, commission: float = 0.001,
                          strategy_params: dict | None = None,
                          position_pct: float = 95) -> dict:
    """运行详细回测，返回摘要 + 交易明细 + 净值曲线 + 原始数据

    Returns:
        dict: {'summary', 'trades', 'equity_curve', 'ohlcv'}
    """
    conn = get_connection(db_path)
    df_raw = get_stock_data(conn, code)
    conn.close()

    if df_raw.empty:
        raise ValueError(f'股票 {code} 无数据')

    data = load_data_to_backtrader(df_raw)
    cerebro = _make_cerebro(data, strategy_class, strategy_params, cash,
                            commission, position_pct)

    init_value = cerebro.broker.getvalue()

    old_stdout = sys.stdout
    sys.stdout = io.StringIO()
    try:
        results = cerebro.run()
    finally:
        sys.stdout = old_stdout

    strat = results[0]
    final_value = cerebro.broker.getvalue()

    summary = _build_summary(strat, len(df_raw), init_value, final_value,
                             strategy_class.__name__, code, commission,
                             position_pct)
    trade_list = strat.analyzers.trade_recorder.get_analysis()
    equity_df = strat.analyzers.equity.get_analysis()

    if equity_df is not None and not equity_df.empty:
        equity_df['value'] = equity_df['value'].astype(float)
        equity_df['return_pct'] = (equity_df['value'] - init_value) / init_value * 100

    return {
        'summary': summary,
        'trades': trade_list,
        'equity_curve': equity_df,
        'ohlcv': df_raw,
    }


def run_backtest(code: str, strategy_class, db_path: str = 'data/stocks.db',
                 cash: float = 100000, commission: float = 0.001,
                 strategy_params: dict | None = None,
                 position_pct: float = 95) -> dict:
    """运行单策略回测（简化版，仅返回摘要）"""
    result = run_backtest_detailed(code, strategy_class, db_path=db_path,
                                   cash=cash, commission=commission,
                                   strategy_params=strategy_params,
                                   position_pct=position_pct)
    return result['summary']


def compare_strategies(code: str, strategies: list, db_path: str = 'data/stocks.db',
                       cash: float = 100000, commission: float = 0.001,
                       position_pct: float = 95) -> pd.DataFrame:
    """对同一只股票跑多个策略，返回对比表"""
    results = []
    for s_cls, s_params in strategies:
        summary = run_backtest(code, s_cls, db_path=db_path, cash=cash,
                               commission=commission, strategy_params=(s_params or {}),
                               position_pct=position_pct)
        results.append(summary)
    return pd.DataFrame(results)


def compare_strategies_detailed(code: str, strategies: list,
                                db_path: str = 'data/stocks.db',
                                cash: float = 100000,
                                commission: float = 0.001,
                                position_pct: float = 95) -> list:
    """对同一只股票跑多个策略，返回详细结果列表"""
    results = []
    for s_cls, s_params in strategies:
        result = run_backtest_detailed(code, s_cls, db_path=db_path, cash=cash,
                                       commission=commission,
                                       strategy_params=(s_params or {}),
                                       position_pct=position_pct)
        results.append(result)
    return results
