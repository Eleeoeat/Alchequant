# -*- coding: utf-8 -*-
"""HTML 投资者报告生成模块。"""

from __future__ import annotations

from datetime import datetime
from html import escape
import os
import platform
from pathlib import Path
import subprocess
import webbrowser

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from src.analysis import analyze_stock
from src.charts import render_equity_curve, render_kline_chart
from src.llm_report import build_llm_payload, generate_llm_sections
from src.report_agents import build_agent_report
from src.utils import find_max_drawdown_period


def _fmt_pct(value, digits: int = 2) -> str:
    if value is None or pd.isna(value):
        return "--"
    return f"{value * 100:+.{digits}f}%"


def _fmt_num(value, digits: int = 2) -> str:
    if value is None or pd.isna(value):
        return "--"
    return f"{float(value):,.{digits}f}"


def _downside_volatility(returns: pd.Series) -> float:
    downside = returns[returns < 0]
    if downside.empty:
        return 0.0
    return float(downside.std() * np.sqrt(252))


def _max_drawdown_duration(equity: pd.DataFrame) -> int:
    values = equity["value"].astype(float)
    peaks = values.cummax()
    underwater = values < peaks
    max_len = cur = 0
    for flag in underwater:
        cur = cur + 1 if flag else 0
        max_len = max(max_len, cur)
    return max_len


def _annual_returns(equity: pd.DataFrame) -> pd.DataFrame:
    eq = equity.copy()
    eq["date"] = pd.to_datetime(eq["date"])
    eq["year"] = eq["date"].dt.year
    rows = []
    for year, group in eq.groupby("year"):
        start = float(group["value"].iloc[0])
        end = float(group["value"].iloc[-1])
        rows.append({"年份": year, "年度收益": _fmt_pct(end / start - 1)})
    return pd.DataFrame(rows)


def _benchmark_curve(ohlcv: pd.DataFrame, initial_cash: float) -> pd.DataFrame:
    bm = ohlcv.copy().sort_values("date")
    bm["date"] = pd.to_datetime(bm["date"])
    first_close = float(bm["close"].iloc[0])
    bm["benchmark_value"] = initial_cash * bm["close"] / first_close
    return bm[["date", "benchmark_value"]]


def calculate_report_metrics(result: dict) -> dict:
    """补齐 RQAlpha 风格的扩展指标。"""
    summary = result["summary"].copy()
    equity = result["equity_curve"].copy()
    ohlcv = result["ohlcv"].copy()
    trades = result.get("trades", [])

    equity["date"] = pd.to_datetime(equity["date"])
    ohlcv["date"] = pd.to_datetime(ohlcv["date"])
    eq_ret = equity["value"].pct_change().dropna()
    bm_ret = ohlcv["close"].pct_change().dropna()
    aligned = pd.concat([eq_ret.rename("strategy"), bm_ret.rename("benchmark")], axis=1).dropna()

    beta = 0.0
    alpha = 0.0
    info_ratio = 0.0
    tracking_error = 0.0
    if not aligned.empty and aligned["benchmark"].var() != 0:
        beta = float(aligned["strategy"].cov(aligned["benchmark"]) / aligned["benchmark"].var())
        strategy_annual = float(aligned["strategy"].mean() * 252)
        benchmark_annual = float(aligned["benchmark"].mean() * 252)
        risk_free = 0.02
        alpha = strategy_annual - (risk_free + beta * (benchmark_annual - risk_free))
        active = aligned["strategy"] - aligned["benchmark"]
        tracking_error = float(active.std() * np.sqrt(252))
        if tracking_error:
            info_ratio = float((active.mean() * 252) / tracking_error)

    benchmark_return = float(ohlcv["close"].iloc[-1] / ohlcv["close"].iloc[0] - 1)
    volatility = float(eq_ret.std() * np.sqrt(252)) if not eq_ret.empty else 0.0
    downside_vol = _downside_volatility(eq_ret)
    sortino = ((summary["annual_return"] - 0.02) / downside_vol) if downside_vol else 0.0
    calmar = summary["annual_return"] / summary["max_drawdown"] if summary["max_drawdown"] else 0.0
    max_dd_period = find_max_drawdown_period(equity)

    trade_df = pd.DataFrame(trades)
    avg_hold_days = 0.0
    best_trade = 0.0
    worst_trade = 0.0
    if not trade_df.empty:
        trade_df["date_in"] = pd.to_datetime(trade_df["date_in"])
        trade_df["date_out"] = pd.to_datetime(trade_df["date_out"])
        trade_df["hold_days"] = (trade_df["date_out"] - trade_df["date_in"]).dt.days
        trade_df["return"] = trade_df["price_out"] / trade_df["price_in"] - 1
        avg_hold_days = float(trade_df["hold_days"].mean())
        best_trade = float(trade_df["return"].max())
        worst_trade = float(trade_df["return"].min())

    summary.update({
        "benchmark_return": benchmark_return,
        "excess_return": summary["total_return"] - benchmark_return,
        "alpha": alpha,
        "beta": beta,
        "volatility": volatility,
        "downside_volatility": downside_vol,
        "sortino_ratio": sortino,
        "calmar_ratio": calmar,
        "information_ratio": info_ratio,
        "tracking_error": tracking_error,
        "max_drawdown_period": max_dd_period,
        "max_drawdown_duration": _max_drawdown_duration(equity),
        "avg_hold_days": avg_hold_days,
        "best_trade": best_trade,
        "worst_trade": worst_trade,
    })
    return summary


def _table_html(df: pd.DataFrame, empty_text: str = "暂无数据") -> str:
    if df is None or df.empty:
        return f"<p class='muted'>{empty_text}</p>"
    return df.to_html(index=False, border=0, classes="data-table", escape=False)


def _levels_table_html(levels: list[dict], empty_text: str) -> str:
    if not levels:
        return f"<p class='muted'>{empty_text}</p>"
    rows = []
    for item in levels:
        rows.append({
            "位置": item["name"],
            "价格": f"{item['price']:.2f}",
            "距离现价": item["distance_text"],
            "依据": escape(item["basis"]),
        })
    return _table_html(pd.DataFrame(rows))


def _figure_html(fig: go.Figure) -> str:
    return fig.to_html(full_html=False, include_plotlyjs="cdn", config={"displaylogo": False})


def _list_html(items: list[str]) -> str:
    return "<ul>" + "".join(f"<li>{escape(item)}</li>" for item in items) + "</ul>"


def _text_or_fallback(sections: dict | None, key: str, fallback: str) -> str:
    if not sections:
        return fallback
    value = sections.get(key)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return fallback


def _list_or_fallback(sections: dict | None, key: str, fallback: list[str]) -> list[str]:
    if not sections:
        return fallback
    value = sections.get(key)
    if isinstance(value, list) and value:
        return [str(v) for v in value if str(v).strip()]
    return fallback


def _role_cards_html(roles: list[dict]) -> str:
    cards = []
    for role in roles:
        evidence = role.get("evidence") or []
        evidence_html = _list_html(evidence) if evidence else ""
        cards.append(
            "<div class='role-card'>"
            f"<span>{escape(role['focus'])}</span>"
            f"<strong>{escape(role['name'])}</strong>"
            f"<p><b>判断：</b>{escape(role.get('judgement', role.get('view', '')))}</p>"
            f"{'<b>依据：</b>' + evidence_html if evidence_html else ''}"
            f"<p><b>含义：</b>{escape(role.get('implication', ''))}</p>"
            f"<p><b>观察：</b>{escape(role.get('watch', ''))}</p>"
            "</div>"
        )
    return "\n".join(cards)


def open_report(path: Path) -> bool:
    """用当前操作系统的默认方式打开 HTML 报告。

    Windows: 使用 os.startfile，尊重 .html 文件关联。
    macOS: 使用 open，避免浏览器只打开主页。
    Linux: 优先使用 xdg-open。
    兜底: 使用 webbrowser 打开 file URI。
    """
    resolved = path.resolve()
    if not resolved.exists():
        return False

    try:
        if os.name == "nt":
            os.startfile(str(resolved))  # type: ignore[attr-defined]
            return True

        system = platform.system()
        if system == "Darwin":
            subprocess.Popen(["open", str(resolved)])
            return True
        if system == "Linux":
            subprocess.Popen(["xdg-open", str(resolved)])
            return True

        return bool(webbrowser.open(resolved.as_uri(), new=2))
    except Exception:
        try:
            return bool(webbrowser.open(resolved.as_uri(), new=2))
        except Exception:
            return False


def _build_technical_interpretation(analysis: dict) -> str:
    trend = analysis["trend_status"]
    risk = analysis["risk_status"]
    r20 = analysis["return_20d"]
    r60 = analysis["return_60d"]
    vol = analysis["volatility20"]

    if trend == "偏强":
        trend_text = "价格与均线结构对多头更友好，说明近期资金仍愿意在较高位置承接。"
    elif trend == "偏弱":
        trend_text = "价格相对主要均线偏弱，短中期趋势修复还需要更多上涨确认。"
    else:
        trend_text = "均线结构暂未给出清晰方向，当前更像震荡整理状态。"

    momentum_text = (
        f"近 20 日涨跌幅为 {_fmt_pct(r20)}，近 60 日涨跌幅为 {_fmt_pct(r60)}。"
        "若短期表现明显强于中期，通常意味着近期动量正在改善；"
        "若短期和中期同时偏弱，则说明价格仍处在趋势修复或弱势延续的验证阶段。"
    )
    risk_text = (
        f"20 日年化波动率约为 {_fmt_pct(vol)}，报告将当前风险标记为“{risk}”。"
        "该风险标记用于衡量价格波动和回撤压力，不等同于交易建议。"
    )
    return f"{trend_text}{momentum_text}{risk_text}"


def build_strategy_profile(strategy_name: str | None, strategy_params: dict | None) -> dict:
    """返回策略专属研究画像，用于本地报告和 AI payload。"""
    name = strategy_name or ""
    params = strategy_params or {}
    if name == "RSI超买超卖":
        period = params.get("period", 14)
        oversold = params.get("oversold", 30)
        overbought = params.get("overbought", 70)
        return {
            "style": "震荡反转",
            "signal_logic": f"使用 {period} 日 RSI 判断短线强弱，RSI 低于 {oversold} 视为超卖修复候选，高于 {overbought} 视为短线过热离场信号。",
            "return_source": "收益主要来自价格在箱体或中枢内的过度下跌修复，而不是长期单边趋势延续。",
            "best_market": "更适合宽幅震荡、急跌后修复和均值回归特征明显的阶段。",
            "failure_mode": "在持续单边下跌中可能过早接入，在强趋势上涨中也可能因过早识别超买而提前离场。",
            "quality_focus": "评估重点不是单纯胜率，而是超卖信号后的反弹幅度是否足以覆盖错误接入和提前离场成本。",
            "watch": f"重点观察 RSI 低于 {oversold} 后价格是否止跌回升，以及 RSI 接近 {overbought} 后是否出现动能衰减。",
        }
    if name == "唐奇安通道突破":
        entry = params.get("entry_period", 20)
        exit_p = params.get("exit_period", 10)
        return {
            "style": "价格突破",
            "signal_logic": f"收盘价突破过去 {entry} 日高点时参与向上突破，跌破过去 {exit_p} 日低点时退出以控制突破失败风险。",
            "return_source": "收益主要来自少数趋势段的延伸，策略允许多次小幅试错来换取捕捉大级别行情的机会。",
            "best_market": "更适合方向明确、波动扩张、价格持续创新高的趋势行情。",
            "failure_mode": "在横盘震荡或假突破频繁阶段容易反复进出，交易次数和回撤压力可能同步上升。",
            "quality_focus": "评估重点在于单笔大盈利能否覆盖连续假突破损耗，以及净值创新高能力是否稳定。",
            "watch": f"重点观察突破 {entry} 日高点后能否继续抬高低点，跌破 {exit_p} 日低点时是否触发有效风险收缩。",
        }
    fast = params.get("fast", 5)
    slow = params.get("slow", 20)
    return {
        "style": "趋势跟随",
        "signal_logic": f"MA{fast} 上穿 MA{slow} 时确认短期趋势强于中期趋势，下穿时退出以规避趋势转弱。",
        "return_source": "收益主要来自中短期趋势延续，策略通过过滤噪声来减少主观判断。",
        "best_market": "更适合趋势方向清晰、均线斜率持续改善、回调后仍能重新上行的阶段。",
        "failure_mode": "在横盘震荡中容易出现反复金叉死叉，信号滞后会放大追涨杀跌和交易成本影响。",
        "quality_focus": "评估重点在于趋势段收益能否覆盖震荡期的来回止损，以及超额收益是否稳定跑赢买入持有。",
        "watch": f"重点观察 MA{fast} 与 MA{slow} 的距离、斜率和交叉频率，交叉过密通常意味着趋势质量下降。",
    }


def profile_clause(profile: dict) -> str:
    return (
        f"{profile['return_source'].rstrip('。')}；"
        f"{profile['failure_mode'].rstrip('。')}"
    )


def clean_watch_text(profile: dict) -> str:
    watch = profile["watch"].strip()
    if watch.startswith("重点观察"):
        watch = watch[len("重点观察"):].lstrip("：:，, ")
    return watch


def _build_strategy_interpretation(metrics: dict, strategy_name: str | None = None,
                                   strategy_params: dict | None = None) -> str:
    total = metrics["total_return"]
    benchmark = metrics["benchmark_return"]
    excess = metrics["excess_return"]
    win_rate = metrics["win_rate"]
    trades = metrics["total_trades"]
    avg_hold = metrics.get("avg_hold_days", 0)
    best = metrics.get("best_trade", 0)
    worst = metrics.get("worst_trade", 0)
    profile = build_strategy_profile(strategy_name, strategy_params)

    if excess > 0:
        compare_text = "样本内跑赢买入持有基准，说明该策略规则在这段行情中产生了有效择时贡献。"
    elif excess < 0:
        compare_text = "样本内弱于买入持有基准，说明当前信号没有充分抵消错过上涨区间、错误触发或交易成本带来的影响。"
    else:
        compare_text = "样本内表现与买入持有基准接近，择时规则暂未形成清晰优势。"

    base_text = (
        f"该策略属于“{profile['style']}”框架，核心信号是：{profile['signal_logic']}"
        f"{profile['return_source']}{profile['best_market']}{profile['failure_mode']}"
        f"回测总收益率为 {_fmt_pct(total)}，基准收益率为 {_fmt_pct(benchmark)}，"
        f"超额收益率为 {_fmt_pct(excess)}；共完成 {trades} 笔闭合交易，"
        f"胜率为 {_fmt_pct(win_rate)}，平均持仓 {avg_hold:.1f} 天，"
        f"最好单笔 {_fmt_pct(best)}，最差单笔 {_fmt_pct(worst)}。{compare_text}"
    )

    if trades == 0:
        diagnostic = "当前没有完整闭合交易，说明参数条件可能过严或样本内行情没有触发完整买卖闭环。"
    elif win_rate < 0.4 and total > 0:
        diagnostic = "胜率不高但仍能取得正收益，说明收益更可能集中在少数关键交易上，需要重点检查盈利交易是否具有可重复的信号特征。"
    elif win_rate > 0.55 and total <= 0:
        diagnostic = "胜率较高但收益不理想，说明盈亏比或单笔亏损控制可能是主要短板。"
    else:
        diagnostic = profile["quality_focus"]

    return f"{base_text}{diagnostic}{profile['watch']}"


def _build_risk_interpretation(metrics: dict) -> str:
    max_dd = metrics["max_drawdown"]
    sharpe = metrics["sharpe_ratio"]
    sortino = metrics["sortino_ratio"]
    info = metrics["information_ratio"]

    if max_dd >= 0.5:
        dd_text = "最大回撤较深，说明即使策略最终有收益，持有过程中的资金波动也会比较考验心理承受能力。"
    elif max_dd >= 0.25:
        dd_text = "最大回撤处于中等偏高水平，策略需要结合仓位控制和风险预算一起看。"
    else:
        dd_text = "最大回撤相对可控，但仍需注意历史样本不能覆盖所有未来市场环境。"

    ratio_text = (
        f"夏普比率为 {_fmt_num(sharpe, 3)}，索提诺比率为 {_fmt_num(sortino, 3)}，"
        f"信息比率为 {_fmt_num(info, 3)}。这些指标主要用于观察收益质量和稳定性，"
        "不应单独作为策略有效性的唯一判断依据。"
    )
    return f"{dd_text}{ratio_text}"


def _build_backtest_setting_interpretation(metrics: dict, strategy_profile: dict) -> str:
    cash = metrics.get("initial_cash", 0)
    commission = metrics.get("commission", 0.001)
    position_pct = metrics.get("position_pct", 95)
    trades = metrics.get("total_trades", 0)
    exposure = position_pct / 100

    if commission >= 0.002:
        cost_text = "手续费率设置偏高，频繁触发信号的策略会更明显受到交易成本侵蚀。"
    elif commission <= 0.0003:
        cost_text = "手续费率设置较低，回测结果对交易摩擦的惩罚较轻，解读时需要注意真实成交环境差异。"
    else:
        cost_text = "手续费率处于常见回测假设区间，仍会随交易次数增加而累积影响净收益。"

    if position_pct >= 95:
        position_text = "单次建仓比例接近满仓，收益和回撤都会被充分放大，资金曲线对入场时点更敏感。"
    elif position_pct <= 50:
        position_text = "单次建仓比例偏保守，有助于降低净值波动，但也会压低趋势或反弹行情中的收益弹性。"
    else:
        position_text = "单次建仓比例处于中等水平，收益弹性和回撤控制之间相对均衡。"

    style_text = (
        f"结合“{strategy_profile['style']}”策略特征，"
        f"{strategy_profile['quality_focus']}"
    )
    trade_text = (
        f"本次回测初始资金为 {_fmt_num(cash)} 元，手续费率为 {_fmt_pct(commission)}，"
        f"单次建仓比例为 {position_pct:.0f}%，理论单次风险暴露约为可用资金的 {exposure:.0%}；"
        f"样本内闭合交易 {trades} 笔。"
    )
    return f"{trade_text}{cost_text}{position_text}{style_text}"


def generate_html_report(
    result: dict,
    stock_code: str,
    stock_name: str = "",
    strategy_name: str | None = None,
    strategy_params: dict | None = None,
    output_dir: str = "results/reports",
    ai_config: dict | None = None,
) -> Path:
    """生成阶段 5 综合 HTML 报告并返回文件路径。"""
    charts_dir = Path("results/charts")
    charts_dir.mkdir(parents=True, exist_ok=True)
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    analysis = analyze_stock(result["ohlcv"], stock_name=stock_name)
    metrics = calculate_report_metrics(result)
    benchmark = _benchmark_curve(result["ohlcv"], metrics["initial_cash"])

    equity_fig = render_equity_curve(result["equity_curve"], benchmark)
    kline_fig = render_kline_chart(
        result["ohlcv"],
        result.get("trades", []),
        strategy_name=strategy_name,
        strategy_params=strategy_params or {},
    )

    yearly = _annual_returns(result["equity_curve"])
    trades_df = pd.DataFrame(result.get("trades", []))
    if not trades_df.empty:
        trades_df = trades_df.assign(
            收益率=(trades_df["price_out"] / trades_df["price_in"] - 1).map(_fmt_pct),
            买入日期=pd.to_datetime(trades_df["date_in"]).dt.strftime("%Y-%m-%d"),
            卖出日期=pd.to_datetime(trades_df["date_out"]).dt.strftime("%Y-%m-%d"),
            买入价=trades_df["price_in"].map(lambda x: _fmt_num(x)),
            卖出价=trades_df["price_out"].map(lambda x: _fmt_num(x)),
            数量=trades_df["size"].map(lambda x: _fmt_num(x, 0)),
            净盈亏=trades_df["pnlcomm"].fillna(trades_df["pnl"]).map(lambda x: _fmt_num(x)),
        )[["买入日期", "卖出日期", "买入价", "卖出价", "数量", "净盈亏", "收益率"]]

    dd_period = metrics.get("max_drawdown_period")
    dd_text = "暂无明显回撤区间"
    if dd_period:
        dd_text = (
            f"{pd.Timestamp(dd_period[0]).strftime('%Y-%m-%d')} 至 "
            f"{pd.Timestamp(dd_period[1]).strftime('%Y-%m-%d')}，"
            f"区间回撤约 {_fmt_pct(-dd_period[2])}"
        )

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    strategy_label = strategy_name or metrics.get("strategy", "")
    params_label = ", ".join(f"{k}={v}" for k, v in (strategy_params or {}).items()) or "默认参数"
    technical_interpretation = _build_technical_interpretation(analysis)
    strategy_profile = build_strategy_profile(strategy_label, strategy_params or {})
    strategy_interpretation = _build_strategy_interpretation(metrics, strategy_label, strategy_params or {})
    setting_interpretation = _build_backtest_setting_interpretation(metrics, strategy_profile)
    risk_interpretation = _build_risk_interpretation(metrics)
    agent_report = build_agent_report(analysis, metrics, strategy_label, strategy_params or {}, strategy_profile)
    ai_sections = None
    ai_error = ""
    if ai_config and ai_config.get("enabled"):
        try:
            payload = build_llm_payload(
                stock_code=stock_code,
                stock_name=stock_name,
                strategy_name=strategy_label,
                strategy_params=strategy_params or {},
                analysis=analysis,
                metrics=metrics,
                agent_report=agent_report,
                strategy_profile=strategy_profile,
            )
            ai_sections = generate_llm_sections(
                payload,
                api_key=ai_config.get("api_key") or None,
                base_url=ai_config.get("base_url") or None,
                model=ai_config.get("model") or None,
                timeout=int(ai_config.get("timeout", 60)),
            )
        except Exception as exc:
            ai_error = str(exc)

    headline_summary = _text_or_fallback(ai_sections, "headline_summary", analysis["summary"])
    executive_summary = _list_or_fallback(ai_sections, "executive_summary", agent_report["executive_summary"])
    technical_interpretation = _text_or_fallback(ai_sections, "trend_analysis", technical_interpretation)
    key_levels_interpretation = _text_or_fallback(ai_sections, "key_levels_analysis", (
        "压力位用于观察反弹能否被市场承接，支撑位用于观察回撤是否仍处于可控范围。"
        "若价格接近压力位但量能未改善，突破有效性需要谨慎评估；"
        "若跌破最近支撑后无法快速收复，则趋势风险可能继续扩大。"
    ))
    strategy_interpretation = _text_or_fallback(ai_sections, "strategy_analysis", strategy_interpretation)
    risk_interpretation = _text_or_fallback(ai_sections, "drawdown_analysis", risk_interpretation)
    final_conclusion = _text_or_fallback(ai_sections, "final_conclusion", (
        f"综合技术面和回测结果看，当前股票处于“{analysis['trend_conclusion']}”状态，"
        f"研究动作倾向为“{analysis['research_action']}”。"
        f"{strategy_label}属于“{strategy_profile['style']}”策略，"
        f"在样本区间内取得 {_fmt_pct(metrics['total_return'])}，"
        f"相对买入持有基准的超额收益为 {_fmt_pct(metrics['excess_return'])}，"
        f"最大回撤为 {_fmt_pct(-metrics['max_drawdown'])}。"
        f"当前主要矛盾在于该策略的“{profile_clause(strategy_profile)}”与股票现有价格结构是否匹配；"
        f"后续应重点观察{clean_watch_text(strategy_profile)}，并结合主要均线、关键价位和策略净值修复情况交叉验证。"
    ))
    thesis = _list_or_fallback(ai_sections, "thesis", agent_report["thesis"])
    counterarguments = _list_or_fallback(ai_sections, "counterarguments", agent_report["counterarguments"])
    watch_points = _list_or_fallback(ai_sections, "watch_points", agent_report["watch_points"])
    action_plan = _list_or_fallback(ai_sections, "action_plan", agent_report["action_plan"])
    risk_categories = _list_or_fallback(ai_sections, "risk_categories", agent_report["risk_categories"])
    support_table_html = _levels_table_html(analysis["support_levels"], "当前下方缺少明确技术支撑锚点。")
    resistance_table_html = _levels_table_html(analysis["resistance_levels"], "当前上方缺少明确技术压力锚点。")

    equity_chart_path = charts_dir / f"equity_{stock_code}_{timestamp}.html"
    kline_chart_path = charts_dir / f"kline_{stock_code}_{timestamp}.html"
    equity_fig.write_html(equity_chart_path, include_plotlyjs="cdn", full_html=True)
    kline_fig.write_html(kline_chart_path, include_plotlyjs="cdn", full_html=True)

    cards = [
        ("总收益率", _fmt_pct(metrics["total_return"])),
        ("基准收益率", _fmt_pct(metrics["benchmark_return"])),
        ("超额收益率", _fmt_pct(metrics["excess_return"])),
        ("年化收益率", _fmt_pct(metrics["annual_return"])),
        ("Alpha", _fmt_pct(metrics["alpha"])),
        ("Beta", _fmt_num(metrics["beta"], 3)),
        ("夏普比率", _fmt_num(metrics["sharpe_ratio"], 3)),
        ("索提诺比率", _fmt_num(metrics["sortino_ratio"], 3)),
        ("Calmar 比率", _fmt_num(metrics["calmar_ratio"], 3)),
        ("最大回撤", _fmt_pct(-metrics["max_drawdown"])),
        ("波动率", _fmt_pct(metrics["volatility"])),
        ("信息比率", _fmt_num(metrics["information_ratio"], 3)),
    ]
    card_html = "\n".join(
        f"<div class='card'><span>{escape(k)}</span><strong>{escape(v)}</strong></div>"
        for k, v in cards
    )

    html = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>Alchequant 报告 - {escape(stock_code)}</title>
  <style>
    body {{ margin:0; background:#0f172b; color:#e2e8f0; font-family: Arial, "Microsoft YaHei", sans-serif; }}
    main {{ max-width:1180px; margin:0 auto; padding:32px 24px 56px; }}
    h1,h2 {{ margin:0 0 14px; }}
    h1 {{ font-size:30px; }}
    h2 {{ font-size:21px; margin-top:34px; border-bottom:1px solid #314158; padding-bottom:10px; }}
    p {{ line-height:1.8; }}
    .muted {{ color:#a0aec0; }}
    .hero {{ background:#1d293d; border:1px solid #314158; border-radius:8px; padding:24px; }}
    .grid {{ display:grid; grid-template-columns:repeat(4, minmax(0, 1fr)); gap:12px; }}
    .card {{ background:#162036; border:1px solid #314158; border-radius:8px; padding:14px; }}
    .card span {{ display:block; color:#a0aec0; font-size:13px; margin-bottom:8px; }}
    .card strong {{ font-size:22px; }}
    .pill {{ display:inline-block; padding:4px 10px; border-radius:999px; background:#26334d; color:#dbeafe; margin-right:8px; }}
    .data-table {{ width:100%; border-collapse:collapse; background:#111a2e; }}
    .data-table th,.data-table td {{ border-bottom:1px solid #314158; padding:10px 12px; text-align:right; }}
    .data-table th:first-child,.data-table td:first-child {{ text-align:left; }}
    .note {{ background:#271a1a; border:1px solid #7f1d1d; border-radius:8px; padding:14px; color:#fecaca; }}
    .analysis-box {{ background:#111a2e; border-left:4px solid #615fff; border-radius:8px; padding:14px 16px; margin:16px 0; }}
    .role-grid {{ display:grid; grid-template-columns:repeat(2, minmax(0, 1fr)); gap:12px; margin-top:12px; }}
    .role-card {{ background:#111a2e; border:1px solid #314158; border-radius:8px; padding:14px 16px; }}
    .role-card span {{ display:block; color:#a0aec0; font-size:12px; margin-bottom:6px; }}
    .role-card strong {{ display:block; font-size:17px; margin-bottom:8px; }}
    ul {{ line-height:1.8; padding-left:22px; }}
    .three-col {{ display:grid; grid-template-columns:repeat(3, minmax(0, 1fr)); gap:12px; }}
    @media (max-width:900px) {{ .grid {{ grid-template-columns:repeat(2, minmax(0, 1fr)); }} }}
    @media (max-width:900px) {{ .role-grid,.three-col {{ grid-template-columns:1fr; }} }}
  </style>
</head>
<body>
<main>
  <section class="hero">
    <h1>Alchequant 综合分析报告</h1>
    <p class="muted">{escape(stock_code)} {escape(stock_name)} · {escape(strategy_label)} · {escape(generated_at)}</p>
    <p>{escape(headline_summary)}</p>
    <span class="pill">趋势：{escape(analysis["trend_status"])}</span>
    <span class="pill">动作：{escape(analysis["research_action"])}</span>
    <span class="pill">风险：{escape(analysis["risk_status"])}</span>
    <span class="pill">研究倾向：{escape(agent_report["stance"])}</span>
    <span class="pill">参数：{escape(params_label)}</span>
  </section>

  <h2>多角色研究摘要</h2>
  <div class="analysis-box">
    <strong>执行摘要</strong>
    {_list_html(executive_summary)}
  </div>
  {f'<p class="muted">文字增强：已启用</p>' if ai_sections else ''}
  {f'<p class="muted">文字增强未启用：已使用本地分析底稿。</p>' if ai_error else ''}
  <div class="analysis-box">
    <strong>证据链</strong>
    {_list_html(agent_report["evidence_chain"])}
  </div>
  <div class="role-grid">
    {_role_cards_html(agent_report["roles"])}
  </div>

  <h2>股票基本信息与数据说明</h2>
  <p>数据区间：{analysis["start_date"]} 至 {analysis["end_date"]}；最近交易日：{analysis["latest_trade_date"]}；最新收盘价：{analysis["latest_close"]:.2f} 元。数据来源为本地 SQLite，原始行情由 AKShare 获取。</p>
  <p class="muted">独立图表文件：{escape(equity_chart_path.as_posix())}；{escape(kline_chart_path.as_posix())}</p>

  <h2>技术面分析</h2>
  <div class="analysis-box">
    <strong>技术面解读</strong>
    <p>{escape(technical_interpretation)}</p>
  </div>
  <div class="grid">
    <div class="card"><span>趋势评分</span><strong>{analysis["trend_score"]}/100</strong></div>
    <div class="card"><span>趋势结论</span><strong>{escape(analysis["trend_conclusion"])}</strong></div>
    <div class="card"><span>研究动作</span><strong>{escape(analysis["research_action"])}</strong></div>
    <div class="card"><span>近120日高点回撤</span><strong>{_fmt_pct(analysis["drawdown_from_high"])}</strong></div>
    <div class="card"><span>20日涨跌幅</span><strong>{_fmt_pct(analysis["return_20d"])}</strong></div>
    <div class="card"><span>60日涨跌幅</span><strong>{_fmt_pct(analysis["return_60d"])}</strong></div>
    <div class="card"><span>120日涨跌幅</span><strong>{_fmt_pct(analysis["return_120d"])}</strong></div>
    <div class="card"><span>20日年化波动率</span><strong>{_fmt_pct(analysis["volatility20"])}</strong></div>
    <div class="card"><span>MA5 / MA20 / MA60</span><strong>{analysis["ma5"]:.2f} / {analysis["ma20"]:.2f} / {analysis["ma60"]:.2f}</strong></div>
    <div class="card"><span>均线结构</span><strong>{escape(analysis["ma_structure"])}</strong></div>
    <div class="card"><span>MACD 状态</span><strong>{escape(analysis["macd_status"])}</strong></div>
    <div class="card"><span>RSI14</span><strong>{analysis["rsi14"]:.2f}（{escape(analysis["rsi_status"])}）</strong></div>
  </div>

  <h2>关键支撑与压力位</h2>
  <div class="three-col">
    <div class="analysis-box">
      <strong>压力位</strong>
      {resistance_table_html}
    </div>
    <div class="analysis-box">
      <strong>支撑位</strong>
      {support_table_html}
    </div>
    <div class="analysis-box">
      <strong>价位解读</strong>
      <p>{escape(key_levels_interpretation)}</p>
    </div>
  </div>

  <h2>策略回测概览</h2>
  <div class="analysis-box">
    <strong>策略表现解读</strong>
    <p>{escape(strategy_interpretation)}</p>
  </div>
  <div class="analysis-box">
    <strong>回测设置解读</strong>
    <p>{escape(setting_interpretation)}</p>
  </div>
  <p>初始资金 {_fmt_num(metrics["initial_cash"])} 元，最终资金 {_fmt_num(metrics["final_value"])} 元；手续费率 {_fmt_pct(metrics.get("commission", 0.001))}，单次建仓 {metrics.get("position_pct", 95):.0f}%；交易次数 {metrics["total_trades"]} 次，胜率 {_fmt_pct(metrics["win_rate"])}，平均持仓 {metrics["avg_hold_days"]:.1f} 天。</p>
  <div class="grid">{card_html}</div>

  <h2>策略 vs 基准净值曲线</h2>
  {_figure_html(equity_fig)}

  <h2>K 线买卖点图</h2>
  {_figure_html(kline_fig)}

  <h2>年度收益表</h2>
  {_table_html(yearly)}

  <h2>回撤分析</h2>
  <div class="analysis-box">
    <strong>风险解读</strong>
    <p>{escape(risk_interpretation)}</p>
  </div>
  <p>最大回撤区间：{escape(dd_text)}；最长回撤持续 {metrics["max_drawdown_duration"]} 个交易日。</p>

  <h2>交易统计</h2>
  <div class="grid">
    <div class="card"><span>最好单笔交易</span><strong>{_fmt_pct(metrics["best_trade"])}</strong></div>
    <div class="card"><span>最差单笔交易</span><strong>{_fmt_pct(metrics["worst_trade"])}</strong></div>
    <div class="card"><span>跟踪误差</span><strong>{_fmt_pct(metrics["tracking_error"])}</strong></div>
    <div class="card"><span>下行波动率</span><strong>{_fmt_pct(metrics["downside_volatility"])}</strong></div>
  </div>

  <h2>交易明细</h2>
  {_table_html(trades_df, "该参数组合下未产生完整闭合交易。")}

  <h2>投资论点、反方观点与观察点</h2>
  <div class="three-col">
    <div class="analysis-box">
      <strong>投资论点</strong>
      {_list_html(thesis)}
    </div>
    <div class="analysis-box">
      <strong>反方观点</strong>
      {_list_html(counterarguments)}
    </div>
    <div class="analysis-box">
      <strong>后续观察点</strong>
      {_list_html(watch_points)}
    </div>
  </div>

  <h2>操作观察与风险分类</h2>
  <div class="role-grid">
    <div class="analysis-box">
      <strong>操作观察</strong>
      {_list_html(action_plan)}
    </div>
    <div class="analysis-box">
      <strong>主要风险</strong>
      {_list_html(risk_categories)}
    </div>
  </div>

  <h2>综合结论与风险提示</h2>
  <p>{escape(final_conclusion)}</p>
  <p class="note">本报告基于历史行情和规则化回测生成，不构成任何投资建议。历史表现不代表未来收益，实际交易还会受到流动性、滑点、交易规则、数据质量和市场环境变化影响。</p>
</main>
</body>
</html>
"""

    file_name = f"report_{stock_code}_{timestamp}.html"
    path = out_dir / file_name
    path.write_text(html, encoding="utf-8")
    return path
