# -*- coding: utf-8 -*-
"""Alchequant 因子研究模块。

基于本地 SQLite 中的 OHLCV 数据做横截面因子计算、标准化、综合评分和解释。
当前阶段只使用本地行情数据，不引入财务估值或外部主观打分。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from src.database import get_connection, get_stock_data, get_stock_list


FACTOR_COLUMNS = [
    '综合评分',
    '动量评分',
    '趋势评分',
    '风险评分',
    '活跃度评分',
    '价格分位评分',
]

SORT_FACTORS = {
    '综合评分': '综合评分',
    '60日动量': '动量60日',
    '120日动量': '动量120日',
    '趋势强度': '趋势强度',
    '风险评分': '风险评分',
    '20日波动率': '波动率20日',
    '20日量比': '成交量比20日',
    '120日价格分位': '价格分位120日',
}


@dataclass(frozen=True)
class FactorConfig:
    """因子计算窗口配置。"""

    lookback_days: int = 252
    min_obs: int = 120


def _safe_zscore(series: pd.Series) -> pd.Series:
    """稳健 z-score，自动处理常数列和缺失值。"""
    s = pd.to_numeric(series, errors='coerce')
    std = s.std(ddof=0)
    if pd.isna(std) or std == 0:
        return pd.Series(0.0, index=series.index)
    return (s - s.mean()) / std


def _score_high_is_good(series: pd.Series) -> pd.Series:
    """把数值转成 0-100 分，数值越大越好。"""
    z = _safe_zscore(series).clip(-3, 3)
    return ((z + 3) / 6 * 100).round(2)


def _score_low_is_good(series: pd.Series) -> pd.Series:
    """把数值转成 0-100 分，数值越小越好。"""
    return _score_high_is_good(-pd.to_numeric(series, errors='coerce'))


def _pct_return(close: pd.Series, periods: int) -> float:
    if len(close) <= periods:
        return np.nan
    base = close.iloc[-periods - 1]
    if pd.isna(base) or base == 0:
        return np.nan
    return float(close.iloc[-1] / base - 1)


def _max_drawdown(close: pd.Series) -> float:
    values = close.astype(float)
    peak = values.cummax()
    drawdown = values / peak - 1
    return float(drawdown.min()) if not drawdown.empty else np.nan


def _risk_level(volatility: float, max_drawdown: float) -> str:
    """给出便于看板筛选的风险等级。"""
    dd = abs(max_drawdown) if pd.notna(max_drawdown) else 0
    vol = volatility if pd.notna(volatility) else 0
    if vol >= 0.42 or dd >= 0.45:
        return '高'
    if vol >= 0.28 or dd >= 0.30:
        return '中'
    return '低'


def _calc_one_stock(code: str, name: str, df: pd.DataFrame, cfg: FactorConfig) -> dict | None:
    """计算单只股票的原始因子。"""
    if df.empty:
        return None

    # 多保留 1 个交易日，确保 N 日收益率能拿到窗口起点价格。
    data = df.copy().sort_values('date').tail(cfg.lookback_days + 1)
    if len(data) < cfg.min_obs:
        return None

    close = pd.to_numeric(data['close'], errors='coerce')
    high = pd.to_numeric(data['high'], errors='coerce')
    low = pd.to_numeric(data['low'], errors='coerce')
    volume = pd.to_numeric(data['volume'], errors='coerce')
    returns = close.pct_change()

    ma20 = close.rolling(20).mean().iloc[-1]
    ma60 = close.rolling(60).mean().iloc[-1]
    last_close = close.iloc[-1]

    high_120 = high.tail(120).max()
    low_120 = low.tail(120).min()
    price_position = (
        (last_close - low_120) / (high_120 - low_120)
        if pd.notna(high_120) and pd.notna(low_120) and high_120 != low_120
        else np.nan
    )

    vol_20 = returns.tail(20).std(ddof=0) * np.sqrt(252)
    vol_ratio = volume.tail(20).mean() / volume.tail(60).mean()
    trend_strength = (last_close / ma60 - 1) if pd.notna(ma60) and ma60 != 0 else np.nan

    return {
        '代码': code,
        '名称': name,
        '最新日期': pd.Timestamp(data['date'].iloc[-1]).strftime('%Y-%m-%d'),
        '最新收盘': round(float(last_close), 2),
        '动量20日': _pct_return(close, 20),
        '动量60日': _pct_return(close, 60),
        '动量120日': _pct_return(close, 120),
        '趋势强度': trend_strength,
        'MA20距离': (last_close / ma20 - 1) if pd.notna(ma20) and ma20 != 0 else np.nan,
        'MA60距离': trend_strength,
        '波动率20日': float(vol_20) if pd.notna(vol_20) else np.nan,
        '最大回撤': _max_drawdown(close.tail(120)),
        '成交量比20日': float(vol_ratio) if pd.notna(vol_ratio) else np.nan,
        '价格分位120日': float(price_position) if pd.notna(price_position) else np.nan,
        '样本天数': int(len(data)),
    }


def calculate_factor_scores(
    db_path: str = 'data/stocks.db',
    lookback_days: int = 252,
    min_obs: int = 120,
) -> pd.DataFrame:
    """计算股票池横截面因子评分。"""
    cfg = FactorConfig(lookback_days=lookback_days, min_obs=min_obs)
    conn = get_connection(db_path)
    try:
        stock_list = get_stock_list(conn)
        rows = []
        for _, stock in stock_list.iterrows():
            code = str(stock['code'])
            df = get_stock_data(conn, code)
            row = _calc_one_stock(code, stock['name'], df, cfg)
            if row:
                rows.append(row)
    finally:
        conn.close()

    if not rows:
        return pd.DataFrame()

    factors = pd.DataFrame(rows)

    factors['动量评分'] = _score_high_is_good(
        factors['动量20日'] * 0.2 + factors['动量60日'] * 0.5 + factors['动量120日'] * 0.3
    )
    factors['趋势评分'] = _score_high_is_good(
        factors['趋势强度'] * 0.7 + factors['MA20距离'] * 0.3
    )
    factors['风险评分'] = (
        _score_low_is_good(factors['波动率20日']) * 0.55 +
        _score_low_is_good(factors['最大回撤'].abs()) * 0.45
    ).round(2)
    factors['活跃度评分'] = _score_high_is_good(factors['成交量比20日'])
    factors['价格分位评分'] = _score_low_is_good(factors['价格分位120日'])

    factors['综合评分'] = (
        factors['动量评分'] * 0.35 +
        factors['趋势评分'] * 0.25 +
        factors['风险评分'] * 0.20 +
        factors['活跃度评分'] * 0.10 +
        factors['价格分位评分'] * 0.10
    ).round(2)

    factors['风险等级'] = factors.apply(
        lambda row: _risk_level(row['波动率20日'], row['最大回撤']),
        axis=1,
    )
    factors['候选标记'] = np.where(
        (factors['综合评分'] >= factors['综合评分'].quantile(0.65)) &
        (factors['风险等级'] != '高'),
        '候选',
        '观察',
    )

    return factors.sort_values('综合评分', ascending=False).reset_index(drop=True)


def filter_factor_scores(
    factors: pd.DataFrame,
    sort_factor: str = '综合评分',
    risk_filter: str = '全部',
    top_n: int = 10,
) -> pd.DataFrame:
    """按看板条件筛选排序。"""
    if factors.empty:
        return factors

    display = factors.copy()
    if risk_filter != '全部':
        display = display[display['风险等级'] == risk_filter]

    sort_col = SORT_FACTORS.get(sort_factor, sort_factor)
    ascending = sort_col in {'波动率20日', '价格分位120日', '最大回撤'}
    display = display.sort_values(sort_col, ascending=ascending)
    return display.head(top_n).reset_index(drop=True)


def build_factor_explanation(row: pd.Series) -> list[str]:
    """生成单只股票的因子解释。"""
    lines = [
        f"综合评分 {row['综合评分']:.1f}，当前在股票池中处于"
        f"{'候选' if row['候选标记'] == '候选' else '观察'}状态。"
    ]

    momentum_parts = []
    if pd.notna(row.get('动量60日')):
        momentum_parts.append(f"60日动量 {row['动量60日'] * 100:+.2f}%")
    if pd.notna(row.get('动量120日')):
        momentum_parts.append(f"120日动量 {row['动量120日'] * 100:+.2f}%")
    if momentum_parts:
        lines.append(f"{'，'.join(momentum_parts)}，趋势评分 {row['趋势评分']:.1f}。")
    elif pd.notna(row.get('趋势评分')):
        lines.append(f"当前窗口内可计算趋势评分 {row['趋势评分']:.1f}，动量窗口数据不足的项目已省略。")

    risk_parts = []
    if pd.notna(row.get('波动率20日')):
        risk_parts.append(f"20日年化波动率 {row['波动率20日'] * 100:.2f}%")
    if pd.notna(row.get('最大回撤')):
        risk_parts.append(f"近120日最大回撤 {row['最大回撤'] * 100:.2f}%")
    if risk_parts:
        lines.append(f"{'，'.join(risk_parts)}，风险等级为 {row['风险等级']}。")

    if pd.notna(row.get('价格分位120日')):
        lines.append(
            f"价格位于近120日区间的 {row['价格分位120日'] * 100:.1f}% 分位；"
            "该项为行情数据代理指标，不等同于财务估值。"
        )

    if pd.notna(row.get('成交量比20日')):
        lines.append(f"20日成交量比为 {row['成交量比20日']:.2f}，用于观察近期交易活跃度变化。")

    return lines


def get_candidate_list(factors: pd.DataFrame, top_n: int = 10) -> pd.DataFrame:
    """输出综合靠前且风险不过高的候选名单。"""
    if factors.empty:
        return factors
    candidates = factors[
        (factors['候选标记'] == '候选') &
        (factors['风险等级'] != '高')
    ].sort_values('综合评分', ascending=False)
    return candidates.head(top_n).reset_index(drop=True)


def export_factor_rank(factors: pd.DataFrame, output_dir: str = 'results/factors') -> Path:
    """导出因子排名 CSV。"""
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    trade_date = pd.Timestamp.now().strftime('%Y%m%d')
    path = out_dir / f'factor_rank_{trade_date}.csv'
    factors.to_csv(path, index=False, encoding='utf-8-sig')
    return path
