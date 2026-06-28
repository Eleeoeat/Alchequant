# -*- coding: utf-8 -*-
"""Alchequant 配置中心 — 颜色常量、默认参数、图表主题"""

COLORS = {
    'primary': '#615fff',
    'up': '#ef5350',
    'down': '#26a69a',
    'benchmark': '#f59e0b',
    'bg': '#0f172b',
    'bg_secondary': '#1d293d',
    'grid': '#2d3748',
    'border': '#314158',
    'text': '#e2e8f0',
    'text_muted': '#a0aec0',
    'text_dim': '#718096',
    'positive': '#22c55e',
    'negative': '#ef5350',
    'highlight': '#ffffff',
}

CHART_THEME = {
    'template': 'plotly_dark',
    'paper_bgcolor': '#0f172b',
    'plot_bgcolor': '#0f172b',
    'height_kline': 700,
    'height_equity': 400,
    'height_compare': 400,
    'margin': dict(l=60, r=20, t=40, b=30),
}

QUICK_RANGES = ['YTD', '1Y', '3Y', '5Y', '全部']
QUICK_RANGE_DEFAULT = '3Y'

STRATEGY_PRESETS = {
    '激进型(5,20)': {'fast': 5, 'slow': 20},
    '稳健型(10,60)': {'fast': 10, 'slow': 60},
    '长线型(20,120)': {'fast': 20, 'slow': 120},
}

CACHE_TTL = 3600
