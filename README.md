<div align="center">

# Alchequant

### 一个放在本地运行的 A 股量化研究工作台

从行情数据、技术面分析、策略回测，到因子筛选和 HTML 报告，尽量把量化研究里最常用的一条链路做成一个干净、可复现、能直接打开的工具。

![Python](https://img.shields.io/badge/Python-3.10%2B-2563eb?style=for-the-badge&logo=python&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-App-ff4b4b?style=for-the-badge&logo=streamlit&logoColor=white)
![Backtrader](https://img.shields.io/badge/Backtrader-Engine-0f172a?style=for-the-badge)
![Plotly](https://img.shields.io/badge/Plotly-Charts-3f4f75?style=for-the-badge&logo=plotly&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-Local_Data-2ea44f?style=for-the-badge&logo=sqlite&logoColor=white)

`AKShare` · `SQLite` · `Backtrader` · `Plotly` · `Streamlit` · `Pandas`

<br/>

![Alchequant 本地量化研究工作台](assets/alchequant-readme-hero.png)

</div>

---

## 为什么做这个

很多量化项目要么偏实盘交易，要么偏在线数据接口，要么偏大模型聊天。Alchequant 想做得更朴素一点：让数据留在本地，让指标和回测可复现，让图表和报告能说清楚“为什么是这个结论”。

它更像一个研究桌面，而不是交易按钮。适合用来做课程项目、策略实验、股票池观察、报告生成和本地量化分析流程演示。

## 打开以后能做什么

| 场景 | 你会看到什么 |
|---|---|
| **看数据** | 本地股票池、数据覆盖范围、每只股票的日线记录 |
| **跑策略** | 双均线交叉、RSI 超买超卖、唐奇安通道突破 |
| **看买卖依据** | K 线图上直接显示均线、RSI 阈值、唐奇安通道上下轨 |
| **比较策略** | 统一从 0% 起步，看不同策略和买入持有基准谁更稳 |
| **做横截面研究** | 用动量、趋势、风险、活跃度、价格分位给股票池打分 |
| **出报告** | 生成 HTML 综合报告，包含技术面、回测表现、风险和交易明细 |
| **接入 AI 改写** | 可选调用 OpenAI-compatible API，让报告文字更自然，但数据仍由本地计算 |

## 研究链路

Alchequant 的核心思路是把研究流程串起来，而不是让每一步散落在不同脚本里：

```text
本地行情数据 -> 技术面结构 -> 策略回测 -> 因子排名 -> HTML 报告
```

默认包含 SQLite 示例数据库，所以即使不联网，也可以直接打开平台看真实结果。

## 快速开始

建议使用 Python 3.10 或更高版本。

```bash
git clone https://github.com/<your-user>/Alchequant.git
cd Alchequant
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

启动后访问：

```text
http://localhost:8501
```

Windows 可以直接双击：

```text
run.bat
```

macOS / Linux：

```bash
bash run_mac.sh
```

## 命令行报告

有时候不想打开页面，只想快速生成一份报告，也可以直接走脚本。

```bash
python scripts/generate_report.py --code 000001 --strategy sma --no-open
```

换成 RSI：

```bash
python scripts/generate_report.py --code 000001 --strategy rsi --period 14 --oversold 30 --overbought 70 --no-open
```

换成唐奇安通道：

```bash
python scripts/generate_report.py --code 000001 --strategy donchian --entry-period 20 --exit-period 10 --no-open
```

可选 AI 增强：

```bash
python scripts/generate_report.py --code 000001 --llm --llm-api-key YOUR_KEY --llm-model gpt-4o-mini --no-open
```

AI 只负责把文字写得更顺，不参与指标、图表、支撑压力位和回测结果计算。

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

`notebooks/` 提供一组轻量研究笔记，用来复现数据读取、指标计算、策略回测、报告生成和因子评分等关键步骤。正式逻辑仍然放在 `src/` 中，Notebook 只负责展示研究过程。

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
├── notebooks/                # 可复现研究路线
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
