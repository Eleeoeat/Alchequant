# Alchequant

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![Streamlit](https://img.shields.io/badge/UI-Streamlit-ff4b4b)
![Backtrader](https://img.shields.io/badge/Backtest-Backtrader-1f77b4)
![Plotly](https://img.shields.io/badge/Charts-Plotly-3f4f75)
![Data](https://img.shields.io/badge/Data-AKShare%20%2B%20SQLite-2ea44f)

Alchequant is a local quantitative research workstation for A-share historical data. It combines data management, technical analysis, strategy backtesting, cross-strategy comparison, factor research, and HTML report generation in one Streamlit app.

Alchequant 是一个本地量化研究工作台，面向 A 股历史行情数据，覆盖数据管理、技术面分析、策略回测、多策略对比、因子研究和 HTML 综合报告生成。

> This project is for research and education only. It is not a trading system and does not provide investment advice.

## Why Alchequant

Many financial AI projects focus on online news, LLM agents, or cloud workflows. Alchequant focuses on a smaller but reproducible loop:

```text
Local data -> Technical analysis -> Strategy backtest -> Factor ranking -> HTML report
```

The default release includes a local SQLite sample database, so the app can run offline and still show real analysis results.

## Features

| Module | What it does |
|---|---|
| Data overview | Browse local stock coverage, date ranges, and OHLCV records |
| Strategy backtest | Run SMA crossover, RSI reversal, and Donchian breakout strategies |
| Strategy comparison | Compare active strategies against a buy-and-hold benchmark |
| Interactive charts | Plotly K-line, volume, strategy signals, equity curve, and drawdown region |
| Factor research | Rank the local stock pool by momentum, trend, risk, liquidity, and price-position factors |
| HTML report | Generate a structured stock report with technical evidence, backtest metrics, risk analysis, and trade details |
| Optional AI writing | Use an OpenAI-compatible API to rewrite report text while keeping all numbers local and deterministic |

## Quick Start

```bash
git clone https://github.com/<your-user>/Alchequant.git
cd Alchequant
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Then open:

```text
http://localhost:8501
```

Windows:

```text
run.bat
```

macOS / Linux:

```bash
bash run_mac.sh
```

## Command Line Report

Generate a default SMA crossover report:

```bash
python scripts/generate_report.py --code 000001 --strategy sma --no-open
```

Generate an RSI report:

```bash
python scripts/generate_report.py --code 000001 --strategy rsi --period 14 --oversold 30 --overbought 70 --no-open
```

Generate a Donchian breakout report:

```bash
python scripts/generate_report.py --code 000001 --strategy donchian --entry-period 20 --exit-period 10 --no-open
```

Enable optional AI-enhanced writing:

```bash
python scripts/generate_report.py --code 000001 --llm --llm-api-key YOUR_KEY --llm-model gpt-4o-mini --no-open
```

The AI layer only rewrites report text. Indicators, charts, support/resistance levels, and backtest results are calculated locally.

## Data

The release includes `data/stocks.db`, a small local SQLite sample database:

| Item | Value |
|---|---:|
| Stock list | 280 constituents |
| Stocks with OHLCV data | 28 |
| Daily records | 65,699 |
| Date range | 2015-01-05 to 2025-12-31 |
| Original source | AKShare, cached locally |

To update or extend the local database:

```bash
python scripts/download_data.py
```

This command requires network access and may be affected by proxy settings, source availability, or API rate limits.

## Research Notebooks

The notebooks are a reproducible research guide, not a second implementation of the app.

They intentionally contain compact code because the real logic lives in `src/`. Each notebook imports the same production modules used by Streamlit and demonstrates one research step:

| Notebook | Purpose |
|---|---|
| `01_获取数据.ipynb` | Inspect the SQLite database and sample coverage |
| `02_数据清洗.ipynb` | Check OHLCV quality and calculate returns |
| `03_技术指标.ipynb` | Use `src.analysis` to generate technical indicators and structured conclusions |
| `04_第一个策略.ipynb` | Run the first SMA crossover backtest through `run_backtest_detailed()` |
| `05_回测与评价.ipynb` | Calculate benchmark return, excess return, drawdown, and trade quality |
| `06_策略库扩展.ipynb` | Compare SMA, RSI, and Donchian strategies |
| `07_综合报告生成.ipynb` | Generate a full HTML report from notebook code |
| `08_因子研究看板.ipynb` | Reproduce the factor ranking logic behind the Streamlit factor page |

This design keeps notebooks stable and readable: if the app logic improves, notebooks automatically use the updated modules instead of drifting into an outdated copy.

## Project Structure

```text
Alchequant/
├── app.py                    # Streamlit app
├── src/
│   ├── analysis.py           # Technical analysis
│   ├── backtest.py           # Backtrader wrapper
│   ├── charts.py             # Plotly charts
│   ├── config.py             # Theme and defaults
│   ├── database.py           # SQLite access
│   ├── data_fetcher.py       # AKShare data fetcher
│   ├── factors.py            # Factor scoring
│   ├── llm_report.py         # Optional AI report writing
│   ├── report.py             # HTML report generation
│   ├── report_agents.py      # Rule-based multi-role research summary
│   ├── strategy.py           # Backtrader strategies
│   └── utils.py              # Shared utilities
├── scripts/
│   ├── download_data.py
│   ├── generate_report.py
│   └── list_stocks.py
├── notebooks/
├── data/
│   └── stocks.db
├── results/
├── .streamlit/
├── requirements.txt
├── run.bat
└── run_mac.sh
```

## Architecture

```text
AKShare
   |
   v
SQLite local database
   |
   +--> Streamlit app
   |       +--> technical analysis
   |       +--> backtest engine
   |       +--> factor ranking
   |       +--> Plotly charts
   |
   +--> command line report
   |
   +--> research notebooks
```

## Roadmap

- Event study for earnings, dividends, limit-up/limit-down days, and major announcements
- Portfolio backtesting across multiple stocks and weights
- More strategy templates and parameter search
- Report UI tabs for overview, technical analysis, backtest, trades, and export
- Optional deployment guide for Streamlit Community Cloud or local Docker

## Disclaimer

Alchequant is for research, learning, and reproducible historical analysis. Historical backtests do not imply future returns. Real trading is affected by slippage, liquidity, commissions, taxes, suspensions, price limits, data quality, and execution constraints.
