# -*- coding: utf-8 -*-
"""本地多角色报告分析模块。

这里的“分析师”不是独立 LLM Agent，而是基于已计算指标的规则化角色观点。
目的：借鉴 FinRobot / TradingAgents-CN 的多角色研究结构，同时保持结果稳定、可复现。
"""

from __future__ import annotations


def _pct(value: float) -> str:
    return f"{value * 100:+.2f}%"


def _score_report(analysis: dict, metrics: dict) -> tuple[int, str]:
    score = 0
    if analysis["trend_status"] == "偏强":
        score += 1
    elif analysis["trend_status"] == "偏弱":
        score -= 1

    if metrics["excess_return"] > 0.05:
        score += 1
    elif metrics["excess_return"] < -0.05:
        score -= 1

    if metrics["max_drawdown"] > 0.5 or analysis["risk_status"] == "高":
        score -= 1
    elif metrics["max_drawdown"] < 0.25 and analysis["risk_status"] == "低":
        score += 1

    if score >= 2:
        stance = "偏积极"
    elif score <= -1:
        stance = "偏谨慎"
    else:
        stance = "中性观察"
    return score, stance


def _level_text(levels: list[dict], empty_text: str) -> str:
    if not levels:
        return empty_text
    parts = []
    for item in levels[:3]:
        parts.append(f"{item['price']:.2f}（{item['basis']}，距离现价 {item['distance_text']}）")
    return "；".join(parts)


def _make_role(name: str, focus: str, judgement: str, evidence: list[str],
               implication: str, watch: str) -> dict:
    view = (
        f"判断：{judgement}"
        f"依据：{'；'.join(evidence)}。"
        f"含义：{implication}"
        f"观察：{watch}"
    )
    return {
        "name": name,
        "focus": focus,
        "judgement": judgement,
        "evidence": evidence,
        "implication": implication,
        "watch": watch,
        "view": view,
    }


def _default_strategy_profile(strategy_name: str | None, strategy_params: dict | None) -> dict:
    params = strategy_params or {}
    if strategy_name == "RSI超买超卖":
        period = params.get("period", 14)
        oversold = params.get("oversold", 30)
        overbought = params.get("overbought", 70)
        return {
            "style": "震荡反转",
            "signal_logic": f"{period} 日 RSI 低于 {oversold} 买入，高于 {overbought} 卖出",
            "return_source": "收益来自超卖后的均值回归修复",
            "best_market": "适合震荡或急跌修复阶段",
            "failure_mode": "持续单边趋势中可能过早接入或过早离场",
            "quality_focus": "重点检查反弹幅度是否覆盖错误信号成本",
            "watch": "观察 RSI 极值后的价格确认和动能衰减",
        }
    if strategy_name == "唐奇安通道突破":
        entry = params.get("entry_period", 20)
        exit_p = params.get("exit_period", 10)
        return {
            "style": "价格突破",
            "signal_logic": f"突破 {entry} 日高点买入，跌破 {exit_p} 日低点卖出",
            "return_source": "收益来自趋势突破后的延伸行情",
            "best_market": "适合方向明确和波动扩张阶段",
            "failure_mode": "横盘和假突破环境中容易反复试错",
            "quality_focus": "重点检查大盈利交易能否覆盖假突破损耗",
            "watch": "观察突破后能否继续抬高低点并减少回撤",
        }
    fast = params.get("fast", 5)
    slow = params.get("slow", 20)
    return {
        "style": "趋势跟随",
        "signal_logic": f"MA{fast} 上穿 MA{slow} 买入，下穿卖出",
        "return_source": "收益来自中短期趋势延续",
        "best_market": "适合趋势清晰和均线斜率改善阶段",
        "failure_mode": "横盘震荡中容易反复交叉并产生滞后信号",
        "quality_focus": "重点检查趋势段收益能否覆盖震荡期损耗",
        "watch": "观察均线距离、斜率和交叉频率",
    }


def build_agent_report(analysis: dict, metrics: dict, strategy_name: str | None = None,
                       strategy_params: dict | None = None,
                       strategy_profile: dict | None = None) -> dict:
    """生成多角色研究观点、投资论点、反方观点和观察点。"""
    _, stance = _score_report(analysis, metrics)
    profile = strategy_profile or _default_strategy_profile(strategy_name, strategy_params)
    strategy_label = strategy_name or metrics.get("strategy", "当前策略")
    trend = analysis["trend_status"]
    risk = analysis["risk_status"]
    excess = metrics["excess_return"]
    max_dd = metrics["max_drawdown"]
    sharpe = metrics["sharpe_ratio"]
    action = analysis["research_action"]
    supports = analysis.get("support_levels", [])
    resistances = analysis.get("resistance_levels", [])
    support_text = _level_text(supports, "下方暂未形成明确支撑锚点")
    resistance_text = _level_text(resistances, "上方暂未形成明确压力锚点")

    roles = [
        _make_role(
            "技术面分析师",
            "趋势结构与动量",
            f"当前趋势为“{analysis['trend_conclusion']}”，短期状态为“{trend}”",
            [
                f"均线结构为“{analysis['ma_structure']}”",
                f"MACD 为“{analysis['macd_status']}”",
                f"RSI 为 {analysis['rsi14']:.2f}（{analysis['rsi_status']}）",
                f"近 20 日涨跌幅 {_pct(analysis['return_20d'])}",
                f"较近 120 日高点回撤 {_pct(analysis['drawdown_from_high'])}",
            ],
            "趋势修复不能只看单一指标，需要均线、动量和量能同步改善。",
            "重点观察价格能否重新站上中期均线，并伴随 MACD 和量能改善。",
        ),
        _make_role(
            "关键价位分析师",
            "支撑与压力",
            "当前价位需要重点观察上方压力突破与下方支撑失守两种情景",
            [
                f"上方压力参考：{resistance_text}",
                f"下方支撑参考：{support_text}",
            ],
            "压力位决定反弹能否延续，支撑位决定回撤是否仍处于可控区间。",
            "接近压力位时观察量能是否放大；跌破支撑后观察能否快速收复。",
        ),
        _make_role(
            "策略回测分析师",
            f"{profile['style']}策略表现",
            f"{strategy_label}的样本内表现需要按“{profile['style']}”逻辑评估",
            [
                f"策略规则：{profile['signal_logic']}",
                f"策略总收益率 {_pct(metrics['total_return'])}",
                f"买入持有基准收益率 {_pct(metrics['benchmark_return'])}",
                f"超额收益率 {_pct(excess)}",
                f"闭合交易 {metrics['total_trades']} 笔",
                f"胜率 {_pct(metrics['win_rate'])}",
                f"平均持仓 {metrics['avg_hold_days']:.1f} 天",
            ],
            profile["quality_focus"],
            profile["watch"],
        ),
        _make_role(
            "风险分析师",
            "回撤、波动与稳定性",
            "策略风险评估应优先关注最大回撤和恢复压力",
            [
                f"最大回撤 {_pct(-max_dd)}",
                f"下行波动率 {_pct(metrics['downside_volatility'])}",
                f"最长回撤持续 {metrics['max_drawdown_duration']} 个交易日",
                f"夏普比率 {sharpe:.3f}",
                f"信息比率 {metrics['information_ratio']:.3f}",
            ],
            "回撤较深或恢复时间较长时，即便最终收益为正，也可能面临较高持有压力。",
            "观察净值能否在回撤后重新创新高，以及收益是否集中于少数交易。",
        ),
        _make_role(
            "反方观点分析师",
            "可能失效的情景",
            f"{strategy_label}可能在不匹配其风格的行情中失效",
            [
                f"策略风格为“{profile['style']}”，适用环境是：{profile['best_market']}",
                f"主要失效情景：{profile['failure_mode']}",
                "当前报告未纳入真实滑点、涨跌停、停牌和冲击成本",
                "样本内表现不等同于样本外表现",
            ],
            "策略结果会受到参数敏感性、成交摩擦和执行约束影响。",
            "若换参数或换样本后结论明显变化，应降低对当前策略有效性的置信度。",
        ),
        _make_role(
            "综合结论分析师",
            "综合研究结论",
            f"综合研究倾向为“{stance}”，研究动作倾向为“{action}”",
            [
                f"趋势评分 {analysis['trend_score']}/100",
                f"超额收益 {_pct(excess)}",
                f"最大回撤 {_pct(-max_dd)}",
                f"风险状态“{risk}”",
            ],
            "当技术面、超额收益和风险控制相互冲突时，结论置信度应下调。",
            "后续需要同时跟踪价格结构、策略净值和回撤恢复情况。",
        ),
    ]

    thesis = []
    if trend == "偏强":
        thesis.append("技术面处于相对强势结构，价格与均线关系对趋势延续更友好。")
    elif trend == "偏弱":
        thesis.append("技术面偏弱，当前核心在于识别风险并等待趋势修复信号。")
    else:
        thesis.append("技术面处于中性状态，适合观察策略在震荡环境中的信号质量和风险暴露。")

    if excess > 0:
        thesis.append(f"{strategy_label}在样本内跑赢买入持有基准，说明“{profile['style']}”规则曾经贡献过超额收益。")
    else:
        thesis.append(f"{strategy_label}在样本内未跑赢买入持有基准，说明当前参数组合的“{profile['style']}”优势有限。")

    if max_dd < 0.35:
        thesis.append("最大回撤相对可控，有利于评估策略的风险管理效果。")
    else:
        thesis.append("最大回撤偏深，说明收益表现需要与资金波动压力一起评估。")

    counterarguments = [
        "历史回测是样本内表现，不代表未来市场环境下仍然有效。",
        f"{strategy_label}对参数和行情风格较敏感，若市场环境偏离“{profile['best_market']}”，结论可能变化。",
        profile["failure_mode"],
        "滑点、涨跌停、停牌、冲击成本等交易约束可能削弱实际执行效果。",
    ]
    if excess > 0:
        counterarguments.append("即使样本内跑赢基准，也可能只是适配了这一段历史行情。")
    else:
        counterarguments.append("样本内跑输基准不代表策略完全无效，也可能需要切换市场环境或参数后再评估。")

    watch_points = [
        "价格能否重新站上并稳定运行在 MA20 / MA60 上方。",
        "MACD 是否从空头或震荡状态转为明确多头结构。",
        "RSI 是否进入过热区间，导致短线追高风险上升。",
        profile["watch"],
        "最大回撤区间后净值是否能创新高，验证策略恢复能力。",
        "更换参数或股票样本后，超额收益是否仍然稳定存在。",
    ]

    action_plan = []
    if action == "观望等待":
        action_plan = [
            "当前研究动作倾向为观望等待，不宜把单一信号或短线反弹直接等同于趋势反转。",
            f"对{strategy_label}而言，后续重点是验证“{profile['style']}”条件是否重新匹配当前行情。",
            "若价格重新站上 MA20，且 MACD 由空头转为金叉或多头，可重新评估趋势修复强度。",
            "若价格跌破最近支撑位并放量下行，应优先控制回撤风险，而不是左侧摊低成本。",
        ]
    elif action == "等待确认":
        action_plan = [
            "当前研究动作倾向为等待确认，核心是观察方向选择，而不是提前假设突破或破位。",
            f"对{strategy_label}而言，需观察{profile['watch']}。",
            "若价格突破最近压力位并保持在 MA20 上方，可视为趋势改善信号之一。",
            "若价格回落至支撑位附近但缩量企稳，可继续观察策略信号是否同步改善。",
        ]
    else:
        action_plan = [
            "当前研究动作倾向为谨慎跟踪，趋势结构相对有利，但仍需关注追高后的回撤压力。",
            f"对{strategy_label}而言，需持续检查{profile['quality_focus']}。",
            "若价格突破主要压力位且量能改善，趋势延续概率会提高。",
            "若价格跌回 MA20 下方或 MACD 转弱，应降低对趋势延续的置信度。",
        ]

    risk_categories = [
        f"趋势风险：当前趋势结论为“{analysis['trend_conclusion']}”，趋势评分 {analysis['trend_score']}/100。",
        f"关键价位风险：上方压力参考 {resistance_text}；下方支撑参考 {support_text}。",
        f"回测风险：最大回撤 {_pct(-max_dd)}，最长回撤持续 {metrics['max_drawdown_duration']} 个交易日。",
        f"模型风险：{strategy_label}属于“{profile['style']}”规则，参数敏感性和行情风格切换会影响样本外稳定性。",
        "交易执行风险：真实滑点、涨跌停、停牌和冲击成本可能使实际结果低于回测。",
    ]

    evidence_chain = [
        f"趋势证据：趋势状态为“{trend}”，趋势评分 {analysis['trend_score']}/100，均线结构为“{analysis['ma_structure']}”，MACD 为“{analysis['macd_status']}”。",
        f"价位证据：上方压力参考 {resistance_text}；下方支撑参考 {support_text}。",
        f"收益证据：{strategy_label}属于“{profile['style']}”策略，总收益率 {_pct(metrics['total_return'])}，基准收益率 {_pct(metrics['benchmark_return'])}，超额收益 {_pct(excess)}。",
        f"风险证据：最大回撤 {_pct(-max_dd)}，波动率 {_pct(metrics['volatility'])}，夏普比率 {sharpe:.3f}。",
    ]

    executive_summary = [
        f"综合研究倾向：{stance}。",
        f"当前趋势：{analysis['trend_conclusion']}，研究动作：{action}。",
        f"技术面状态：{trend}，风险状态：{risk}，趋势评分：{analysis['trend_score']}/100。",
        f"{strategy_label}的策略风格：{profile['style']}；相对基准超额收益：{_pct(excess)}，最大回撤：{_pct(-max_dd)}。",
        "结论未纳入外部新闻、财务预测或估值假设。",
    ]

    return {
        "stance": stance,
        "roles": roles,
        "thesis": thesis,
        "counterarguments": counterarguments,
        "watch_points": watch_points,
        "action_plan": action_plan,
        "risk_categories": risk_categories,
        "evidence_chain": evidence_chain,
        "executive_summary": executive_summary,
        "strategy_profile": profile,
    }
