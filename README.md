# Alchequant

Alchequant 是一个本地量化研究与分析平台，面向 A 股历史行情数据，提供数据查看、策略回测、多策略对比、因子研究和 HTML 综合报告生成。

项目定位是“本地研究工作台”，不是实盘交易系统，也不构成投资建议。默认读取本地 SQLite 示例数据，离线也可以打开平台并复现主要分析流程。

## 功能特性

- 本地数据管理：使用 SQLite 保存股票列表和日线 OHLCV 数据。
- 策略回测：基于 Backtrader 支持双均线、RSI 超买超卖、唐奇安通道突破。
- 策略对比：用累计收益率视角比较主动策略与买入持有基准。
- 交互图表：Plotly K 线、成交量、买卖点、策略依据线、净值曲线和回撤标注。
- 因子看板：基于本地行情计算动量、趋势、风险、活跃度和价格分位评分。
- HTML 报告：生成技术面 + 回测 + 风险 + 多角色研究摘要的综合报告。
- 可选 AI 增强：支持 OpenAI-compatible Chat Completions，只改写报告文字，不参与指标计算。

## 快速开始

建议使用 Python 3.10+。

```bash
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Windows 也可以双击：

```text
run.bat
```

macOS / Linux：

```bash
bash run_mac.sh
```

打开浏览器访问：

```text
http://localhost:8501
```

## 示例数据

发布版默认包含 `data/stocks.db` 示例数据库：

- 成分股清单：280 只
- 有日线数据股票：28 只
- 日线记录：65,699 行
- 数据范围：2015-01-05 至 2025-12-31
- 数据来源：AKShare 获取后缓存到本地 SQLite

示例数据用于离线演示和功能复现，不代表完整沪深 300 数据集。需要更新或补全数据时，可运行：

```bash
python scripts/download_data.py
```

该命令会访问 AKShare 数据源，受网络、代理和接口限流影响。

## 命令行报告

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

也可以通过环境变量提供密钥：

```bash
set LLM_API_KEY=YOUR_KEY
set LLM_BASE_URL=https://api.openai.com/v1
set LLM_MODEL=gpt-4o-mini
python scripts/generate_report.py --code 000001 --llm --no-open
```

API Key 不应写入项目文件，也不应提交到 GitHub。

## 项目结构

```text
Alchequant/
├── app.py                    # Streamlit 主界面
├── src/                      # 核心模块
│   ├── analysis.py           # 技术面分析
│   ├── backtest.py           # Backtrader 回测封装
│   ├── charts.py             # Plotly 图表
│   ├── config.py             # 颜色、主题和默认配置
│   ├── database.py           # SQLite 读写
│   ├── data_fetcher.py       # AKShare 数据获取
│   ├── factors.py            # 因子研究与评分
│   ├── llm_report.py         # 可选 AI 报告文字增强
│   ├── report.py             # HTML 报告生成
│   ├── report_agents.py      # 本地规则化多角色研究摘要
│   ├── strategy.py           # 策略类
│   └── utils.py              # 工具函数
├── scripts/
│   ├── download_data.py      # 下载/增量更新数据
│   ├── generate_report.py    # 命令行生成 HTML 报告
│   └── list_stocks.py        # 导出本地股票清单
├── notebooks/                # 研究路线 Notebook
├── data/
│   └── stocks.db             # 示例 SQLite 数据库
├── results/                  # 运行时输出目录，GitHub 默认不提交临时结果
├── .streamlit/config.toml    # Streamlit 主题
├── requirements.txt
├── run.bat
└── run_mac.sh
```

## Notebook 路线

`notebooks/` 用于复现研究过程：

- 01 获取数据
- 02 数据清洗
- 03 技术指标
- 04 第一个策略
- 05 回测与评价
- 06 策略库扩展
- 07 综合报告生成
- 08 因子研究看板

Notebook 是研究说明材料，正式应用入口仍是 `app.py`。

## 发布说明

适合提交到 GitHub 的内容包括源码、说明文档、Notebook、示例数据库和通用启动脚本。

不应提交：

- API Key、`.env`、本地密钥文件
- `.claude/`、`.agents/` 等本地工作区状态
- `__pycache__/`、`.ipynb_checkpoints/`
- 大量临时 `results/` 报告和图表
- 个人电脑绝对路径

详见 `发布清单.md`。

## 风险提示

本项目只用于量化研究、教学和历史数据分析。所有回测结果均依赖历史样本、参数假设和本地数据质量，不能代表未来收益。实际交易还会受到滑点、手续费、停牌、涨跌停、流动性和执行约束影响。
