<div align="center">

# Alchequant

### 本地量化研究与分析平台

把 A 股历史行情、技术面分析、策略回测、因子观察和 HTML 报告整理到一个本地工作台里。

![Python](https://img.shields.io/badge/Python-3.10--3.12-2563eb?style=for-the-badge&logo=python&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-App-ff4b4b?style=for-the-badge&logo=streamlit&logoColor=white)
![Backtrader](https://img.shields.io/badge/Backtrader-Engine-0f172a?style=for-the-badge)
![Plotly](https://img.shields.io/badge/Plotly-Charts-3f4f75?style=for-the-badge&logo=plotly&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-Local_Data-2ea44f?style=for-the-badge&logo=sqlite&logoColor=white)

![Alchequant 本地量化研究工作台](assets/alchequant-readme-hero.png)

</div>

---

## 一句话介绍

Alchequant 不是实盘交易软件，也不是聊天式选股助手。它更像一张本地研究桌：数据在本地、逻辑可复现、图表能交互、报告能导出。

适合用来做课程项目、策略实验、股票池观察、研究报告生成和量化分析流程展示。

## 核心体验

<table>
  <tr>
    <td width="33%"><b>本地可跑</b><br/>默认带 SQLite 示例库，不联网也能看到真实分析结果。</td>
    <td width="33%"><b>解释清楚</b><br/>K 线图上直接显示均线、RSI 阈值、唐奇安通道和买卖点。</td>
    <td width="33%"><b>报告完整</b><br/>把技术面、回测、回撤、交易明细和风险说明整理成 HTML。</td>
  </tr>
  <tr>
    <td><b>策略可比</b><br/>双均线、RSI、唐奇安统一回测口径，和买入持有基准对照。</td>
    <td><b>因子观察</b><br/>用动量、趋势、风险、活跃度和价格分位给股票池做横截面评分。</td>
    <td><b>研究可复现</b><br/>Streamlit、命令行和 Notebook 共用同一套 <code>src/</code> 模块。</td>
  </tr>
</table>

## 研究链路

```text
本地行情数据 -> 技术面结构 -> 策略回测 -> 因子排名 -> HTML 报告
```

这条链路是项目的主线。界面适合交互分析，脚本适合自动生成报告，Notebook 适合复现实验过程。

## 快速开始

建议使用 Python 3.10 到 3.12。

```bash
git clone https://github.com/Eleeoeat/Alchequant.git
cd Alchequant
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

浏览器打开：

```text
http://localhost:8501
```

Windows 可以双击：

```text
run.bat
```

macOS / Linux：

```bash
bash run_mac.sh
```

## 命令行生成报告

默认双均线报告：

```bash
python scripts/generate_report.py --code 000001 --strategy sma --no-open
```

RSI 策略报告：

```bash
python scripts/generate_report.py --code 000001 --strategy rsi --period 14 --oversold 30 --overbought 70 --no-open
```

唐奇安通道报告：

```bash
python scripts/generate_report.py --code 000001 --strategy donchian --entry-period 20 --exit-period 10 --no-open
```

如果配置了 OpenAI-compatible API Key，也可以开启 AI 增强报告。AI 只负责把报告文字写得更顺，不参与指标、图表、支撑压力位和回测结果计算。

## 示例数据

发布版自带 `data/stocks.db`，用于离线演示和复现。

| 内容 | 数量 |
|---|---:|
| 成分股清单 | 280 只 |
| 有日线数据的股票 | 28 只 |
| 日线记录 | 65,699 行 |
| 数据范围 | 2015-01-05 至 2025-12-31 |
| 原始数据来源 | AKShare，本地 SQLite 缓存 |

需要更新或扩展数据时：

```bash
python scripts/download_data.py
```

这一步需要联网，也会受到网络环境、代理设置、数据源可用性和接口限流影响。

## 研究笔记

`notebooks/` 提供一组轻量研究笔记，用来复现数据读取、指标计算、策略回测、报告生成和因子评分等关键步骤。

## 项目结构

```text
Alchequant/
├── app.py                    # Streamlit 主界面
├── src/
│   ├── analysis.py           # 技术面分析
│   ├── backtest.py           # Backtrader 回测封装
│   ├── charts.py             # Plotly 图表
│   ├── config.py             # 主题和默认配置
│   ├── database.py           # SQLite 读写
│   ├── data_fetcher.py       # AKShare 数据获取
│   ├── factors.py            # 因子评分
│   ├── llm_report.py         # 可选 AI 报告文字增强
│   ├── report.py             # HTML 报告生成
│   ├── report_agents.py      # 本地规则化多角色研究摘要
│   ├── strategy.py           # Backtrader 策略
│   └── utils.py              # 通用工具函数
├── scripts/
│   ├── download_data.py      # 下载/增量更新数据
│   ├── generate_report.py    # 命令行生成 HTML 报告
│   └── list_stocks.py        # 导出本地股票清单
├── notebooks/                # 可复现研究笔记
├── data/
│   └── stocks.db             # 示例 SQLite 数据库
├── results/                  # 运行时输出目录
├── .streamlit/               # Streamlit 主题配置
├── requirements.txt
├── run.bat
└── run_mac.sh
```

## 技术栈

| 环节 | 工具 |
|---|---|
| 数据源 | AKShare |
| 数据存储 | SQLite |
| 数据处理 | Pandas / NumPy |
| 回测引擎 | Backtrader |
| 图表 | Plotly |
| Web UI | Streamlit |
| 报告 | HTML + Plotly |

## 风险提示

本项目仅用于量化研究、学习和历史数据分析，不构成任何投资建议。历史回测结果不代表未来收益。真实交易还会受到滑点、手续费、税费、停牌、涨跌停、流动性、数据质量和执行约束影响。
