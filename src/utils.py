# -*- coding: utf-8 -*-
"""Alchequant 工具函数 — 数据格式化、日期清洗、缓存键生成、参数校验"""

import pandas as pd


def clean_dates(df, date_col='date'):
    """清洗日期列，移除时间戳，统一为 YYYY-MM-DD 格式

    Args:
        df: 原始 DataFrame
        date_col: 日期列名

    Returns:
        DataFrame，日期列已格式化为纯日期字符串
    """
    df = df.copy()
    if date_col in df.columns:
        df[date_col] = pd.to_datetime(df[date_col]).dt.strftime('%Y-%m-%d')
    return df


def format_pct(val, decimal=2):
    """格式化百分比率值为显示字符串

    Args:
        val: 小数形式比率 (0.078 → '+7.80%')
        decimal: 小数位数

    Returns:
        str: 如 '+7.80%' 或 '-3.20%'
    """
    pct = val * 100
    sign = '+' if pct >= 0 else ''
    return f'{sign}{pct:.{decimal}f}%'


def format_currency(val, prefix='¥'):
    """格式化货币金额，千分位分隔

    Args:
        val: 数值
        prefix: 货币前缀

    Returns:
        str: 如 '¥107,805.12'
    """
    return f'{prefix}{val:,.2f}'


def validate_params(params, cash, commission=0.001, position_pct=95):
    """校验回测参数合法性。"""
    if cash <= 0:
        return False, '初始资金必须大于0'
    if commission < 0:
        return False, '手续费率不能为负'
    if position_pct <= 0 or position_pct > 100:
        return False, '单次建仓比例必须在 0~100% 之间'

    if 'fast' in params and 'slow' in params and params['fast'] >= params['slow']:
        return False, '短期周期必须小于长期周期'

    if (
        'oversold' in params and 'overbought' in params and
        params['oversold'] >= params['overbought']
    ):
        return False, 'RSI 超卖阈值必须小于超买阈值'

    if (
        'entry_period' in params and 'exit_period' in params and
        params['exit_period'] >= params['entry_period']
    ):
        return False, '离场周期必须小于突破周期'

    return True, ''


def calc_quick_start(quick_sel, full_end):
    """根据快捷时间选项计算起始日期

    Args:
        quick_sel: 选项 ('YTD'/'1Y'/'3Y'/'5Y'/'全部')
        full_end: 数据结束日期 (pd.Timestamp)

    Returns:
        pd.Timestamp 或 None (None 表示从最早数据开始)
    """
    if quick_sel == '全部' or not quick_sel:
        return None
    if quick_sel == '1Y':
        return full_end - pd.DateOffset(years=1)
    if quick_sel == '3Y':
        return full_end - pd.DateOffset(years=3)
    if quick_sel == '5Y':
        return full_end - pd.DateOffset(years=5)
    if quick_sel == 'YTD':
        return pd.Timestamp(year=full_end.year, month=1, day=1)
    return None


def find_max_drawdown_period(equity_df):
    """从净值曲线定位最大回撤区间

    Args:
        equity_df: 含 date/value 列的 DataFrame

    Returns:
        tuple: (peak_date, trough_date, dd_pct) 或 None
    """
    if equity_df is None or equity_df.empty or len(equity_df) < 2:
        return None
    values = equity_df['value'].astype(float).values
    dates = equity_df['date'].values

    running_peak = values[0]
    running_peak_idx = 0
    max_dd = 0
    peak_idx = 0
    trough_idx = 0

    for i in range(1, len(values)):
        if values[i] > running_peak:
            running_peak = values[i]
            running_peak_idx = i
        dd = (running_peak - values[i]) / running_peak
        if dd > max_dd:
            max_dd = dd
            peak_idx = running_peak_idx
            trough_idx = i

    if max_dd > 0:
        return dates[peak_idx], dates[trough_idx], max_dd
    return None


def build_trade_hover(trade, idx):
    """构建交易标记的 Plotly 悬停文本

    Args:
        trade: 交易字典 (date_in/date_out/price_in/price_out/pnl/pnlcomm/size)
        idx: 交易序号 (0-based)

    Returns:
        str: HTML 格式悬停文本
    """
    pnl = trade.get('pnl', 0)
    pnlcomm = trade.get('pnlcomm')
    ret = (trade['price_out'] / trade['price_in'] - 1) * 100 if trade['price_in'] else 0
    hold_days = (pd.Timestamp(trade['date_out']) - pd.Timestamp(trade['date_in'])).days

    lines = [f'<b>交易#{idx + 1}</b>']
    lines.append(f'买入价: {trade["price_in"]:.2f}')
    lines.append(f'卖出价: {trade["price_out"]:.2f}')
    lines.append(f'盈亏: {pnl:+,.2f}')
    if pnlcomm is not None:
        lines.append(f'净盈亏: {pnlcomm:+,.2f}')
    lines.append(f'收益率: {ret:+.2f}%')
    lines.append(f'持仓: {hold_days}天')
    return '<br>'.join(lines)


def get_selected_rows(selection):
    """从 st.dataframe 的 on_select 返回值中安全提取选中行索引

    Args:
        selection: st.dataframe(on_select="rerun") 的返回值

    Returns:
        list[int]: 选中的行索引列表
    """
    try:
        if hasattr(selection, 'selection'):
            sel = selection.selection
            if isinstance(sel, dict):
                return sel.get('rows', [])
            return getattr(sel, 'rows', [])
        if isinstance(selection, dict):
            return selection.get('selection', {}).get('rows', [])
    except Exception:
        pass
    return []
