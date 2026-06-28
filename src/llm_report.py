# -*- coding: utf-8 -*-
"""AI 增强报告撰写层。

大模型只负责改写和组织报告文字，不负责计算指标，也不允许补充未提供的数据。
默认使用 OpenAI-compatible Chat Completions 接口，支持 OpenAI、DeepSeek 等兼容服务。
"""

from __future__ import annotations

import json
import os
from typing import Any
from urllib import request, error


REQUIRED_KEYS = [
    "headline_summary",
    "executive_summary",
    "trend_analysis",
    "key_levels_analysis",
    "strategy_analysis",
    "drawdown_analysis",
    "thesis",
    "counterarguments",
    "watch_points",
    "action_plan",
    "risk_categories",
    "final_conclusion",
]


def _pct(value: float) -> str:
    return f"{value * 100:+.2f}%"


def _num(value: float, digits: int = 3) -> str:
    return f"{value:.{digits}f}"


def _compact_levels(levels: list[dict]) -> list[dict]:
    return [
        {
            "name": item["name"],
            "price": round(item["price"], 2),
            "distance": item["distance_text"],
            "basis": item["basis"],
        }
        for item in levels[:5]
    ]


def build_llm_payload(
    stock_code: str,
    stock_name: str,
    strategy_name: str,
    strategy_params: dict,
    analysis: dict,
    metrics: dict,
    agent_report: dict,
    strategy_profile: dict | None = None,
) -> dict:
    """把本地计算结果压缩成给大模型的结构化输入。"""
    profile = strategy_profile or agent_report.get("strategy_profile") or {}
    return {
        "stock": {
            "code": stock_code,
            "name": stock_name,
            "data_range": f"{analysis['start_date']} 至 {analysis['end_date']}",
            "latest_trade_date": analysis["latest_trade_date"],
            "latest_close": round(analysis["latest_close"], 2),
        },
        "technical": {
            "trend_status": analysis["trend_status"],
            "trend_conclusion": analysis["trend_conclusion"],
            "trend_score": analysis["trend_score"],
            "research_action": analysis["research_action"],
            "risk_status": analysis["risk_status"],
            "ma_structure": analysis["ma_structure"],
            "ma5": round(analysis["ma5"], 2),
            "ma20": round(analysis["ma20"], 2),
            "ma60": round(analysis["ma60"], 2),
            "macd_status": analysis["macd_status"],
            "rsi14": round(analysis["rsi14"], 2),
            "rsi_status": analysis["rsi_status"],
            "return_20d": _pct(analysis["return_20d"]),
            "return_60d": _pct(analysis["return_60d"]),
            "return_120d": _pct(analysis["return_120d"]),
            "volatility20": _pct(analysis["volatility20"]),
            "volume_status": analysis["volume_status"],
            "volume_change": _pct(analysis["volume_change"]),
            "drawdown_from_120d_high": _pct(analysis["drawdown_from_high"]),
            "rebound_from_120d_low": _pct(analysis["rebound_from_low"]),
            "resistance_levels": _compact_levels(analysis["resistance_levels"]),
            "support_levels": _compact_levels(analysis["support_levels"]),
        },
        "backtest": {
            "strategy": strategy_name,
            "params": strategy_params,
            "strategy_profile": profile,
            "initial_cash": round(metrics["initial_cash"], 2),
            "final_value": round(metrics["final_value"], 2),
            "commission": _pct(metrics.get("commission", 0.001)),
            "position_pct": f"{metrics.get('position_pct', 95):.0f}%",
            "total_return": _pct(metrics["total_return"]),
            "benchmark_return": _pct(metrics["benchmark_return"]),
            "excess_return": _pct(metrics["excess_return"]),
            "annual_return": _pct(metrics["annual_return"]),
            "alpha": _pct(metrics["alpha"]),
            "beta": _num(metrics["beta"], 3),
            "sharpe_ratio": _num(metrics["sharpe_ratio"], 3),
            "sortino_ratio": _num(metrics["sortino_ratio"], 3),
            "calmar_ratio": _num(metrics["calmar_ratio"], 3),
            "information_ratio": _num(metrics["information_ratio"], 3),
            "tracking_error": _pct(metrics["tracking_error"]),
            "volatility": _pct(metrics["volatility"]),
            "downside_volatility": _pct(metrics["downside_volatility"]),
            "max_drawdown": _pct(-metrics["max_drawdown"]),
            "max_drawdown_duration": metrics["max_drawdown_duration"],
            "total_trades": metrics["total_trades"],
            "win_rate": _pct(metrics["win_rate"]),
            "avg_hold_days": round(metrics["avg_hold_days"], 1),
            "best_trade": _pct(metrics["best_trade"]),
            "worst_trade": _pct(metrics["worst_trade"]),
        },
        "local_framework": {
            "stance": agent_report["stance"],
            "analyst_notes": [
                {
                    "name": role.get("name"),
                    "focus": role.get("focus"),
                    "judgement": role.get("judgement"),
                    "evidence": role.get("evidence"),
                    "implication": role.get("implication"),
                    "watch": role.get("watch"),
                }
                for role in agent_report["roles"]
            ],
            "evidence_chain": agent_report["evidence_chain"],
            "thesis": agent_report["thesis"],
            "counterarguments": agent_report["counterarguments"],
            "watch_points": agent_report["watch_points"],
            "action_plan": agent_report["action_plan"],
            "risk_categories": agent_report["risk_categories"],
        },
    }


def _extract_json(text: str) -> dict:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:].strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start >= 0 and end > start:
        cleaned = cleaned[start:end + 1]
    return json.loads(cleaned)


def _normalise_sections(data: dict) -> dict:
    result = {}
    for key in REQUIRED_KEYS:
        value = data.get(key)
        if isinstance(value, list):
            result[key] = [str(v).strip() for v in value if str(v).strip()]
        elif value is None:
            result[key] = [] if key in {"thesis", "counterarguments", "watch_points", "action_plan", "risk_categories"} else ""
        else:
            result[key] = str(value).strip()
    return result


def build_harness_prompt(payload: dict) -> list[dict]:
    """构造 harness 式结构化提示词。

    结构固定为：Role -> Objective -> Context -> Inputs -> Constraints ->
    Process -> Output Contract -> Quality Gate。这样能降低跑题、编造和格式漂移。
    """
    system_prompt = """# ROLE
你是严谨的证券研究报告撰写助手，负责把量化系统已经计算好的结构化结果改写为专业中文研究报告。

# OBJECTIVE
生成自然、具体、差异化的投资研究报告文字。你的价值在于解释和组织，不在于重新计算或补充外部信息。

# NON-NEGOTIABLE CONSTRAINTS
1. 只能使用用户提供的 payload，不得编造新闻、财报、估值、行业信息、机构观点、市场传闻或实时行情。
2. 不得改变 payload 中的数值、方向和结论，不得自行重新计算指标。
3. 可以给出研究倾向、风险判断和观察条件，但不得写“保证收益”“一定上涨”“强烈买入”“无风险”等表达。
4. 不得出现“课堂”“演示”“项目”“作业”“教学”等非专业报告语境词。
5. 所有建议必须是条件化观察语言，例如“若...则...需要重新评估”，不得直接下达交易指令。
6. 输出必须是合法 JSON 对象，不要 Markdown，不要代码块，不要额外解释。

# STYLE
使用专业投研口吻，结论先行，证据跟随。避免机械模板句，必须结合该股票的具体趋势、价位、回测、回撤和风险数据。"""

    user_prompt = {
        "HARNESS": {
            "role": "证券研究报告撰写助手",
            "objective": "基于 payload 生成专业、自然、差异化的中文报告段落。",
            "context": {
                "report_type": "技术面 + 策略回测综合投资研究报告",
                "calculation_owner": "所有指标、图表、支撑压力、回测结果均由本地系统计算",
                "model_owner": "模型只负责撰写和组织文字",
            },
            "input_contract": {
                "payload": "唯一可信输入。payload 外的信息一律视为未知，不得引用。",
                "numeric_values": "必须保持原样引用，不得修改、推导或重新计算。",
                "missing_data": "如果 payload 没有提供某类数据，必须写成未纳入或无法判断，不得补充想象内容。",
            },
            "writing_process": [
                "先判断核心结论：趋势、风险、策略表现三者是否一致。",
                "再写证据链：均线/MACD/RSI/关键价位/回测超额/回撤/手续费率/建仓比例。",
                "写策略段时必须先识别策略范式：趋势跟随、震荡反转或价格突破；不同范式要使用不同分析逻辑。",
                "再写反方观点：说明哪些情况下当前结论可能失效。",
                "最后写观察条件：用 if/then 条件表达，不写直接交易命令。",
            ],
            "output_contract": {
                "type": "json_object",
                "required_keys": REQUIRED_KEYS,
                "schema": {
                    "headline_summary": "string，80-140字，核心结论先行",
                    "executive_summary": "array，3-5条，每条20-60字",
                    "trend_analysis": "string，180-280字，解释趋势、均线、MACD、RSI、量能和近期高低点",
                    "key_levels_analysis": "string，160-260字，解释支撑压力、突破/跌破条件",
                    "strategy_analysis": "string，180-280字，必须结合 backtest.strategy_profile、commission 和 position_pct，解释该策略范式的收益来源、适用行情、失效情景、基准对比、交易质量和回测设置影响",
                    "drawdown_analysis": "string，160-260字，解释最大回撤、恢复压力、波动和风险承受",
                    "thesis": "array，3-5条研究论点，每条必须有数据依据",
                    "counterarguments": "array，3-5条反方观点，说明结论可能失效的条件",
                    "watch_points": "array，4-6条后续观察点，尽量具体到均线、MACD、价位或净值结构",
                    "action_plan": "array，3-5条条件化操作观察，不能直接推荐买卖",
                    "risk_categories": "array，4-6条主要风险分类",
                    "final_conclusion": "string，160-260字，直接写综合结论、主要矛盾和后续观察，不要解释报告用途",
                },
            },
            "quality_gate": [
                "检查是否所有 required_keys 都存在。",
                "检查是否没有 Markdown、代码块和多余解释。",
                "检查是否没有引用 payload 外的信息。",
                "检查策略分析是否明确使用了 payload.backtest.strategy_profile，而不是写成通用回测模板。",
                "检查是否没有出现课堂、演示、项目、作业、教学等词。",
                "检查是否没有保证收益或确定性价格预测。",
            ],
        },
        "payload": payload,
    }
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": json.dumps(user_prompt, ensure_ascii=False)},
    ]


def _validate_sections(sections: dict) -> None:
    missing = [key for key in REQUIRED_KEYS if key not in sections]
    if missing:
        raise ValueError(f"AI 输出缺少字段: {', '.join(missing)}")


def generate_llm_sections(
    payload: dict,
    api_key: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
    timeout: int = 60,
) -> dict:
    """调用 OpenAI-compatible API，返回报告文字段落。"""
    key = api_key or os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not key:
        raise ValueError("缺少 API Key")

    base = (base_url or os.getenv("LLM_BASE_URL") or os.getenv("OPENAI_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
    model_name = model or os.getenv("LLM_MODEL") or os.getenv("OPENAI_MODEL") or "gpt-4o-mini"
    endpoint = f"{base}/chat/completions"

    body = {
        "model": model_name,
        "messages": build_harness_prompt(payload),
        "temperature": 0.45,
    }
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = request.Request(
        endpoint,
        data=data,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"LLM API HTTP {exc.code}: {detail[:300]}") from exc

    parsed: dict[str, Any] = json.loads(raw)
    content = parsed["choices"][0]["message"]["content"]
    sections = _extract_json(content)
    _validate_sections(sections)
    return _normalise_sections(sections)
