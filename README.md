<div align="center">

# Alchequant

**本地量化研究与分析平台**

面向 A 股历史行情数据，覆盖数据管理、技术面分析、策略回测、多策略对比、因子研究与 HTML 综合报告生成。

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

## 目录

- [项目定位](#项目定位)
- [功能特性](#功能特性)
- [快速开始](#快速开始)
- [命令行生成报告](#命令行生成报告)
- [示例数据](#示例数据)
- [Notebook 是做什么的](#notebook-是做什么的)
- [项目结构](#项目结构)
- [技术栈](#技术栈)
- [风险提示](#风险提示)

## 项目定位

Alchequant 的目标不是做实盘交易系统，而是搭建一个 **可复现、可解释、可离线运行** 的量化研究工作台。

## 项目亮点

很多金融 AI 项目侧重新闻、Agent 或在线数据接口。Alchequant 更关注一个小而完整的本地研究闭环：

```text
本地数据 -> 技术面分析 -> 策略回测 -> 因子排名 -> HTML 报告
```

发布版默认包含 SQLite 示例数据库，因此即使没有联网，也可以打开平台并看到真实分析结果。

<table>
  <tr>
    <td><strong>本地优先</strong><br/>默认读取 SQLite 示例数据库，减少网络和接口波动影响。</td>
    <td><strong>研究闭环</strong><br/>从数据、策略、因子到报告，覆盖完整量化分析路径。</td>
    <td><strong>解释友好</strong><br/>每个策略都展示买卖依据线，报告保留证据链和风险说明。</td>
  </tr>
  <tr>
    <td><strong>轻量部署</strong><br/>纯 Python 技术栈，无需数据库服务、消息队列或实盘网关。</td>
    <td><strong>可复现</strong><br/>Streamlit、脚本和 Notebook 共用同一套核心模块。</td>
    <td><strong>可扩展</strong><br/>策略、因子、报告和数据源均按模块拆分。</td>
  </tr>
</table>

## 功能特性

| 模块 | 功能 |
|---|---|
| **数据总览** | 查看本地股票池、数据覆盖范围和 OHLCV 记录 |
| **策略回测** | 支持双均线交叉、RSI 超买超卖、唐奇安通道突破 |
| **策略对比** | 对比主动策略与买入持有基准的累计收益表现 |
| **交互图表** | Plotly K 线、成交量、买卖点、策略依据线、净值曲线和回撤区间 |
| **因子看板** | 基于本地行情计算动量、趋势、风险、活跃度和价格分位评分 |
| **HTML 报告** | 生成技术面、回测指标、风险分析、交易明细和多角色研究摘要 |
| **可选 AI 增强** | 支持 OpenAI-compatible API 改写报告文字，指标和图表仍由本地计算 |

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

<details>
<summary><strong>Windows 一键启动</strong></summary>

```text
run.bat
```

</details>

<details>
<summary><strong>macOS / Linux 启动</strong></summary>

```bash
bash run_mac.sh
```

</details>

## 命令行生成报告

生成默认双均线报告：

```bash
python scripts/generate_report.py --code 000001 --strategy sma --no-open
```

生成 RSI 报告：

```bash
python scripts/generate_report.py --code 000001 --strategy rsi --period 14 --oversold 30 --overbought 70 --no-open
```

生成唐奇安通道报告：

```bash
python scripts/generate_report.py --code 000001 --strategy donchian --entry-period 20 --exit-period 10 --no-open
```

启用可选 AI 增强：

```bash
python scripts/generate_report.py --code 000001 --llm --llm-api-key YOUR_KEY --llm-model gpt-4o-mini --no-open
```

AI 只负责改写报告文字，不参与指标、图表、支撑压力位或回测结果计算。

## 示例数据

发布版包含 `data/stocks.db` 示例数据库：

| 内容 | 数量 |
|---|---:|
| 成分股清单 | 280 只 |
| 有日线数据的股票 | 28 只 |
| 日线记录 | 65,699 行 |
| 数据范围 | 2015-01-05 至 2025-12-31 |
| 原始数据来源 | AKShare，本地 SQLite 缓存 |

如需更新或扩展本地数据库：

```bash
python scripts/download_data.py
```

该命令需要联网，可能受到网络环境、代理设置、数据源可用性或接口限流影响。

## Notebook 是做什么的

`notebooks/` 不是第二套应用代码，而是项目的可复现研究路线。

Notebook 里的代码刻意保持简洁，因为正式逻辑都封装在 `src/` 中。这样做有两个好处：

1. Notebook 更像实验说明书，适合阅读和复现。
2. Streamlit、命令行脚本和 Notebook 共用同一套核心模块，避免三份代码互相漂移。

| Notebook | 作用 |
|---|---|
| `01_获取数据.ipynb` | 查看 SQLite 数据库和样例股票覆盖情况 |
| `02_数据清洗.ipynb` | 检查 OHLCV 数据质量，计算收益率 |
| `03_技术指标.ipynb` | 调用 `src.analysis` 生成技术指标和结构化结论 |
| `04_第一个策略.ipynb` | 用 `run_backtest_detailed()` 跑双均线策略 |
| `05_回测与评价.ipynb` | 计算基准收益、超额收益、回撤和交易质量 |
| `06_策略库扩展.ipynb` | 对比双均线、RSI、唐奇安三类策略 |
| `07_综合报告生成.ipynb` | 从 Notebook 中生成完整 HTML 报告 |
| `08_因子研究看板.ipynb` | 复现 Streamlit 因子看板背后的评分逻辑 |

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

本项目仅用于量化研究、学习和历史数据分析，不构成任何投资建议。历史回测结果不代表未来收益。实际交易还会受到滑点、手续费、税费、停牌、涨跌停、流动性、数据质量和执行约束影响。
