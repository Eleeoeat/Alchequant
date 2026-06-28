# -*- coding: utf-8 -*-
"""股票技术面分析模块。

输入单只股票 OHLCV 数据，输出适合报告展示的结构化结论。
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def _safe_pct(current: float, previous: float) -> float:
    if previous == 0 or pd.isna(previous):
        return 0.0
    return current / previous - 1


def _calc_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - 100 / (1 + rs)


def _add_level(levels: list[dict], price: float, basis: str, current: float, kind: str) -> None:
    if pd.isna(price) or price <= 0:
        return
    distance = price / current - 1
    levels.append({
        "name": "",
        "price": float(price),
        "basis": basis,
        "distance": distance,
        "kind": kind,
    })


def _dedupe_levels(levels: list[dict], current: float, limit: int = 5) -> list[dict]:
    filtered = []
    for item in sorted(levels, key=lambda x: abs(x["distance"])):
        if any(abs(item["price"] / old["price"] - 1) < 0.006 for old in filtered):
            continue
        filtered.append(item)
        if len(filtered) >= limit:
            break

    prefix = "压力" if filtered and filtered[0]["kind"] == "resistance" else "支撑"
    for idx, item in enumerate(filtered, start=1):
        item["name"] = f"第{idx}{prefix}"
        item["distance_text"] = f"{item['distance'] * 100:+.2f}%"
    return filtered


def _calc_key_levels(df: pd.DataFrame, close: float, ma5: float, ma20: float, ma60: float) -> tuple[list[dict], list[dict]]:
    support_candidates = []
    resistance_candidates = []

    for price, basis in [
        (ma5, "MA5 均线"),
        (ma20, "MA20 均线"),
        (ma60, "MA60 均线"),
    ]:
        if pd.isna(price):
            continue
        target = resistance_candidates if price > close else support_candidates
        _add_level(target, price, basis, close, "resistance" if price > close else "support")

    windows = [(20, "近20日"), (60, "近60日"), (120, "近120日")]
    for window, label in windows:
        if len(df) < max(5, window // 2):
            continue
        sample = df.tail(min(window, len(df)))
        low = float(sample["low"].min())
        high = float(sample["high"].max())
        if low < close:
            _add_level(support_candidates, low, f"{label}低点", close, "support")
        if high > close:
            _add_level(resistance_candidates, high, f"{label}高点", close, "resistance")

    supports = _dedupe_levels(support_candidates, close, limit=5)
    resistances = _dedupe_levels(resistance_candidates, close, limit=5)
    return supports, resistances


def enrich_indicators(ohlcv: pd.DataFrame) -> pd.DataFrame:
    """补齐阶段 5 报告所需技术指标。"""
    df = ohlcv.copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)

    for window in (5, 20, 60):
        df[f"ma{window}"] = df["close"].rolling(window).mean()

    ema12 = df["close"].ewm(span=12, adjust=False).mean()
    ema26 = df["close"].ewm(span=26, adjust=False).mean()
    df["dif"] = ema12 - ema26
    df["dea"] = df["dif"].ewm(span=9, adjust=False).mean()
    df["macd"] = (df["dif"] - df["dea"]) * 2
    df["rsi14"] = _calc_rsi(df["close"], 14)
    df["return"] = df["close"].pct_change()
    df["volatility20"] = df["return"].rolling(20).std() * np.sqrt(252)
    df["volume_ma20"] = df["volume"].rolling(20).mean()
    return df


def analyze_stock(ohlcv: pd.DataFrame, stock_name: str | None = None) -> dict:
    """生成结构化技术面分析结论。"""
    if ohlcv is None or ohlcv.empty:
        raise ValueError("OHLCV 数据为空，无法生成技术面分析")

    df = enrich_indicators(ohlcv)
    latest = df.iloc[-1]
    close = float(latest["close"])

    def period_return(days: int) -> float:
        if len(df) <= days:
            return 0.0
        return _safe_pct(close, float(df["close"].iloc[-days - 1]))

    ma5 = float(latest.get("ma5", np.nan))
    ma20 = float(latest.get("ma20", np.nan))
    ma60 = float(latest.get("ma60", np.nan))
    r20 = period_return(20)
    r60 = period_return(60)
    r120 = period_return(120)

    if close > ma5 > ma20 > ma60:
        ma_structure = "多头排列"
        trend_status = "偏强"
    elif close < ma5 < ma20 < ma60:
        ma_structure = "空头排列"
        trend_status = "偏弱"
    elif close >= ma20 and ma20 >= ma60:
        ma_structure = "短中期偏多"
        trend_status = "偏强"
    elif close < ma20 and ma20 < ma60:
        ma_structure = "短中期偏空"
        trend_status = "偏弱"
    else:
        ma_structure = "均线纠缠"
        trend_status = "中性"

    dif = float(latest.get("dif", 0) or 0)
    dea = float(latest.get("dea", 0) or 0)
    prev_dif = float(df["dif"].iloc[-2]) if len(df) > 1 and pd.notna(df["dif"].iloc[-2]) else dif
    prev_dea = float(df["dea"].iloc[-2]) if len(df) > 1 and pd.notna(df["dea"].iloc[-2]) else dea
    if prev_dif <= prev_dea and dif > dea:
        macd_status = "金叉"
    elif prev_dif >= prev_dea and dif < dea:
        macd_status = "死叉"
    elif dif >= dea and dif >= 0:
        macd_status = "多头"
    elif dif < dea and dif < 0:
        macd_status = "空头"
    else:
        macd_status = "震荡"

    rsi = float(latest.get("rsi14", 50) or 50)
    if rsi >= 70:
        rsi_status = "超买"
    elif rsi <= 30:
        rsi_status = "超卖"
    else:
        rsi_status = "中性"

    vol20 = float(latest.get("volatility20", 0) or 0)
    volume_ma20 = float(latest.get("volume_ma20", 0) or 0)
    volume_change = _safe_pct(float(latest["volume"]), volume_ma20) if volume_ma20 else 0.0
    volume_status = "放量" if volume_change > 0.25 else "缩量" if volume_change < -0.25 else "量能平稳"

    recent_120 = df.tail(min(120, len(df)))
    recent_high = float(recent_120["high"].max())
    recent_low = float(recent_120["low"].min())
    high_date = recent_120.loc[recent_120["high"].idxmax(), "date"].strftime("%Y-%m-%d")
    drawdown_from_high = _safe_pct(close, recent_high)
    rebound_from_low = _safe_pct(close, recent_low)
    support_levels, resistance_levels = _calc_key_levels(df, close, ma5, ma20, ma60)

    risk_score = 0
    if vol20 > 0.45:
        risk_score += 2
    elif vol20 > 0.28:
        risk_score += 1
    if rsi >= 75 or rsi <= 25:
        risk_score += 1
    if r20 < -0.12:
        risk_score += 1
    risk_status = "高" if risk_score >= 3 else "中" if risk_score >= 1 else "低"

    trend_score = 50
    if trend_status == "偏强":
        trend_score += 20
    elif trend_status == "偏弱":
        trend_score -= 20
    if macd_status in ("金叉", "多头"):
        trend_score += 10
    elif macd_status in ("死叉", "空头"):
        trend_score -= 10
    if r20 > 0.08:
        trend_score += 10
    elif r20 < -0.08:
        trend_score -= 10
    if close > ma20:
        trend_score += 5
    else:
        trend_score -= 5
    trend_score = int(max(0, min(100, trend_score)))

    if trend_score >= 70:
        trend_conclusion = "多头趋势占优"
        research_action = "谨慎跟踪"
    elif trend_score <= 35:
        trend_conclusion = "空头趋势占优"
        research_action = "观望等待"
    else:
        trend_conclusion = "震荡观察"
        research_action = "等待确认"

    summary_parts = [
        f"最新收盘价为 {close:.2f} 元",
        f"价格位于 MA20 {'上方' if close >= ma20 else '下方'}",
        f"均线结构呈现{ma_structure}",
        f"MACD 为{macd_status}状态",
        f"RSI 处于{rsi_status}区间",
        f"综合判断短期趋势{trend_status}，风险水平为{risk_status}，研究动作倾向为{research_action}",
    ]

    return {
        "stock_name": stock_name or "",
        "latest_close": close,
        "start_date": df["date"].iloc[0].strftime("%Y-%m-%d"),
        "end_date": df["date"].iloc[-1].strftime("%Y-%m-%d"),
        "latest_trade_date": df["date"].iloc[-1].strftime("%Y-%m-%d"),
        "return_20d": r20,
        "return_60d": r60,
        "return_120d": r120,
        "ma5": ma5,
        "ma20": ma20,
        "ma60": ma60,
        "ma_structure": ma_structure,
        "macd_status": macd_status,
        "rsi14": rsi,
        "rsi_status": rsi_status,
        "volatility20": vol20,
        "volume_change": volume_change,
        "volume_status": volume_status,
        "recent_high": recent_high,
        "recent_high_date": high_date,
        "recent_low": recent_low,
        "drawdown_from_high": drawdown_from_high,
        "rebound_from_low": rebound_from_low,
        "support_levels": support_levels,
        "resistance_levels": resistance_levels,
        "trend_score": trend_score,
        "trend_conclusion": trend_conclusion,
        "research_action": research_action,
        "trend_status": trend_status,
        "risk_status": risk_status,
        "summary": "，".join(summary_parts) + "。",
        "indicator_df": df,
    }
