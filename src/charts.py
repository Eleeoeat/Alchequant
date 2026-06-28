# -*- coding: utf-8 -*-
"""Alchequant 图表渲染 — Plotly K线图、净值曲线、策略对比"""

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from src.config import COLORS, CHART_THEME
from src.utils import find_max_drawdown_period, build_trade_hover


def _calc_rsi(close, period):
    """按 Wilder 平滑近似计算 RSI，用于前端解释图。"""
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, pd.NA)
    return 100 - (100 / (1 + rs))


def render_kline_chart(ohlcv, trades, start_date=None, end_date=None, highlight_date=None,
                       strategy_name=None, strategy_params=None):
    """渲染 K线+成交量+策略依据 交互式图表 (Plotly)

    彻底替代 mplfinance，支持缩放/平移/联动。

    Args:
        ohlcv: 含 date/open/high/low/close/volume 列的 DataFrame
        trades: 交易列表 (由 TradeRecorder 生成)
        start_date: 显示起始日期 (str 或 None)
        end_date: 显示结束日期 (str 或 None)
        highlight_date: 高亮日期，用于表格联动 (str 或 None)
        strategy_name: 当前策略显示名
        strategy_params: 当前策略参数，用于绘制解释性指标

    Returns:
        plotly.graph_objects.Figure
    """
    params = strategy_params or {}
    df_all = ohlcv.copy()
    df_all['date'] = pd.to_datetime(df_all['date'])
    df_all = df_all.sort_values('date')

    if strategy_name == '双均线交叉':
        fast = int(params.get('fast', 5))
        slow = int(params.get('slow', 20))
        df_all[f'MA{fast}'] = df_all['close'].rolling(fast).mean()
        df_all[f'MA{slow}'] = df_all['close'].rolling(slow).mean()
    elif strategy_name == 'RSI超买超卖':
        period = int(params.get('period', 14))
        df_all['RSI'] = _calc_rsi(df_all['close'], period)
    elif strategy_name == '唐奇安通道突破':
        entry = int(params.get('entry_period', 20))
        exit_p = int(params.get('exit_period', 10))
        df_all['通道上轨'] = df_all['high'].shift(1).rolling(entry).max()
        df_all['通道下轨'] = df_all['low'].shift(1).rolling(exit_p).min()

    df = df_all.copy()

    # [联动] 统一时间窗口过滤
    if start_date:
        df = df[df['date'] >= pd.Timestamp(start_date)]
    if end_date:
        df = df[df['date'] <= pd.Timestamp(end_date)]

    if df.empty:
        fig = go.Figure()
        fig.update_layout(
            template=CHART_THEME['template'],
            height=CHART_THEME['height_kline'],
            paper_bgcolor=CHART_THEME['paper_bgcolor'],
            plot_bgcolor=CHART_THEME['plot_bgcolor'],
            annotations=[dict(
                text='📊 当前时间范围内无数据',
                showarrow=False, font=dict(size=16, color=COLORS['text_muted']),
                xref='paper', yref='paper', x=0.5, y=0.5,
            )],
        )
        return fig

    show_rsi = strategy_name == 'RSI超买超卖'
    rows = 3 if show_rsi else 2
    row_heights = [0.68, 0.18, 0.14] if show_rsi else [0.75, 0.25]

    fig = make_subplots(
        rows=rows, cols=1, shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=row_heights,
    )

    # K线
    kline_hover = [
        f'日期: {d.strftime("%Y-%m-%d")}<br>'
        f'开: {o:.2f}<br>高: {h:.2f}<br>低: {l:.2f}<br>收: {c:.2f}<br>'
        f'量: {v:,.0f}'
        for d, o, h, l, c, v in zip(
            df['date'], df['open'], df['high'], df['low'], df['close'], df['volume']
        )
    ]
    fig.add_trace(go.Candlestick(
        x=df['date'], open=df['open'], high=df['high'],
        low=df['low'], close=df['close'],
        name='K线',
        increasing_line_color=COLORS['up'],
        decreasing_line_color=COLORS['down'],
        increasing_fillcolor=COLORS['up'],
        decreasing_fillcolor=COLORS['down'],
        hovertext=kline_hover,
        hoverinfo='text',
    ), row=1, col=1)

    # 策略依据线：让买卖信号有可解释的视觉参照
    if strategy_name == '双均线交叉':
        fast = int(params.get('fast', 5))
        slow = int(params.get('slow', 20))
        fig.add_trace(go.Scatter(
            x=df['date'], y=df[f'MA{fast}'],
            mode='lines',
            name=f'MA{fast}',
            line=dict(color='#38bdf8', width=1.4),
            hovertemplate=f'MA{fast}: %{{y:.2f}}<extra></extra>',
        ), row=1, col=1)
        fig.add_trace(go.Scatter(
            x=df['date'], y=df[f'MA{slow}'],
            mode='lines',
            name=f'MA{slow}',
            line=dict(color='#fbbf24', width=1.4),
            hovertemplate=f'MA{slow}: %{{y:.2f}}<extra></extra>',
        ), row=1, col=1)
    elif strategy_name == '唐奇安通道突破':
        fig.add_trace(go.Scatter(
            x=df['date'], y=df['通道上轨'],
            mode='lines',
            name='突破上轨',
            line=dict(color='#38bdf8', width=1.3),
            hovertemplate='突破上轨: %{y:.2f}<extra></extra>',
        ), row=1, col=1)
        fig.add_trace(go.Scatter(
            x=df['date'], y=df['通道下轨'],
            mode='lines',
            name='离场下轨',
            line=dict(color='#f97316', width=1.3),
            hovertemplate='离场下轨: %{y:.2f}<extra></extra>',
        ), row=1, col=1)

    # 成交量
    vol_colors = [COLORS['up'] if c >= o else COLORS['down']
                  for o, c in zip(df['open'], df['close'])]
    fig.add_trace(go.Bar(
        x=df['date'], y=df['volume'],
        marker_color=vol_colors,
        name='成交量',
        showlegend=False,
        hovertemplate='日期: %{x|%Y-%m-%d}<br>成交量: %{y:,.0f}<extra></extra>',
    ), row=2, col=1)

    if show_rsi:
        oversold = int(params.get('oversold', 30))
        overbought = int(params.get('overbought', 70))
        fig.add_trace(go.Scatter(
            x=df['date'], y=df['RSI'],
            mode='lines',
            name='RSI',
            line=dict(color='#a78bfa', width=1.5),
            hovertemplate='RSI: %{y:.2f}<extra></extra>',
        ), row=3, col=1)
        fig.add_hline(
            y=overbought, line_dash='dot', line_color=COLORS['negative'],
            line_width=1, opacity=0.8, row=3, col=1,
            annotation_text='超买', annotation_position='top left',
        )
        fig.add_hline(
            y=oversold, line_dash='dot', line_color=COLORS['positive'],
            line_width=1, opacity=0.8, row=3, col=1,
            annotation_text='超卖', annotation_position='bottom left',
        )

    # 买卖信号标记
    if trades:
        buy_x, buy_y, buy_text = [], [], []
        sell_x, sell_y, sell_text = [], [], []
        date_set = set(df['date'].dt.strftime('%Y-%m-%d'))

        for i, t in enumerate(trades):
            d_in = pd.Timestamp(t['date_in']).strftime('%Y-%m-%d')
            d_out = pd.Timestamp(t['date_out']).strftime('%Y-%m-%d')

            if d_in in date_set:
                buy_x.append(pd.Timestamp(t['date_in']))
                buy_y.append(t['price_in'])
                buy_text.append(build_trade_hover(t, i))

            if d_out in date_set:
                sell_x.append(pd.Timestamp(t['date_out']))
                sell_y.append(t['price_out'])
                sell_text.append(build_trade_hover(t, i))

        if buy_x:
            fig.add_trace(go.Scatter(
                x=buy_x, y=buy_y,
                mode='markers',
                marker=dict(symbol='triangle-up', size=7, color=COLORS['positive'],
                            opacity=0.6, line=dict(width=0.5, color='white')),
                name='买入',
                text=buy_text,
                hoverinfo='text',
            ), row=1, col=1)

        if sell_x:
            fig.add_trace(go.Scatter(
                x=sell_x, y=sell_y,
                mode='markers',
                marker=dict(symbol='triangle-down', size=7, color=COLORS['negative'],
                            opacity=0.6, line=dict(width=0.5, color='white')),
                name='卖出',
                text=sell_text,
                hoverinfo='text',
            ), row=1, col=1)

    # [联动] 交易明细行点击 → 白色垂直高亮线
    if highlight_date:
        fig.add_vline(
            x=pd.Timestamp(highlight_date),
            line_dash='dot', line_color=COLORS['highlight'],
            line_width=1.5, opacity=0.7,
            row='all', col='all',
        )

    # 布局配置
    fig.update_layout(
        template=CHART_THEME['template'],
        height=CHART_THEME['height_kline'] + (120 if show_rsi else 0),
        margin=CHART_THEME['margin'],
        paper_bgcolor=CHART_THEME['paper_bgcolor'],
        plot_bgcolor=CHART_THEME['plot_bgcolor'],
        xaxis_rangeslider=dict(visible=True, thickness=0.05),
        legend=dict(orientation='h', yanchor='bottom', y=1.02, x=0),
        hovermode='x unified',
    )

    fig.update_xaxes(gridcolor=COLORS['grid'], tickformat='%Y-%m-%d', row=2, col=1)
    fig.update_yaxes(gridcolor=COLORS['grid'], row=1, col=1)
    fig.update_yaxes(gridcolor=COLORS['grid'], row=2, col=1)
    if show_rsi:
        fig.update_yaxes(gridcolor=COLORS['grid'], range=[0, 100], row=3, col=1)

    return fig


def render_equity_curve(equity_df, benchmark_df=None, start_date=None, end_date=None):
    """渲染策略净值曲线 + 基准 + 最大回撤标注

    Args:
        equity_df: 含 date/value 列的 DataFrame
        benchmark_df: 含 date/benchmark_value 列的 DataFrame (可选)
        start_date: 显示起始日期 (str 或 None)
        end_date: 显示结束日期 (str 或 None)

    Returns:
        plotly.graph_objects.Figure
    """
    eq = equity_df.copy()
    eq['date'] = pd.to_datetime(eq['date'])
    eq = eq.sort_values('date')

    # [联动] 统一时间窗口过滤
    if start_date:
        eq = eq[eq['date'] >= pd.Timestamp(start_date)]
    if end_date:
        eq = eq[eq['date'] <= pd.Timestamp(end_date)]

    if eq.empty:
        fig = go.Figure()
        fig.update_layout(
            template=CHART_THEME['template'],
            height=CHART_THEME['height_equity'],
            paper_bgcolor=CHART_THEME['paper_bgcolor'],
            plot_bgcolor=CHART_THEME['plot_bgcolor'],
            annotations=[dict(
                text='📊 当前时间范围内无数据',
                showarrow=False, font=dict(size=16, color=COLORS['text_muted']),
                xref='paper', yref='paper', x=0.5, y=0.5,
            )],
        )
        return fig

    init_cash = float(eq['value'].iloc[0])

    fig = go.Figure()

    # 策略净值线：主色实线
    fig.add_trace(go.Scatter(
        x=eq['date'], y=eq['value'],
        mode='lines',
        name='策略净值',
        line=dict(color=COLORS['primary'], width=2.5),
        opacity=1.0,
        hovertemplate='日期: %{x|%Y-%m-%d}<br>策略: %{y:,.2f}<extra></extra>',
    ))

    # 基准净值线：橙色半透明实线（非虚线），共用同一 Y 轴
    if benchmark_df is not None and not benchmark_df.empty:
        bm = benchmark_df.copy()
        bm['date'] = pd.to_datetime(bm['date'])
        bm = bm.sort_values('date')
        if start_date:
            bm = bm[bm['date'] >= pd.Timestamp(start_date)]
        if end_date:
            bm = bm[bm['date'] <= pd.Timestamp(end_date)]

        merged = eq[['date', 'value']].rename(columns={'value': 'sv'})
        merged = merged.merge(bm[['date', 'benchmark_value']], on='date', how='left')
        merged['excess_pct'] = ((merged['sv'] - merged['benchmark_value']) / init_cash * 100).round(2)

        fig.add_trace(go.Scatter(
            x=bm['date'], y=bm['benchmark_value'],
            mode='lines',
            name='基准净值',
            line=dict(color=COLORS['benchmark'], width=1.5),
            opacity=0.5,
            customdata=merged['excess_pct'].values,
            hovertemplate=(
                '日期: %{x|%Y-%m-%d}<br>'
                '基准: %{y:,.2f}<br>'
                '超额: %{customdata:+.2f}%<extra></extra>'
            ),
        ))

    # 最大回撤标注：半透明红色遮罩 + 文字
    dd_info = find_max_drawdown_period(eq)
    if dd_info:
        peak_date, trough_date, dd_pct = dd_info
        mask = (eq['date'] >= pd.Timestamp(peak_date)) & (eq['date'] <= pd.Timestamp(trough_date))
        dd_segment = eq[mask]

        if not dd_segment.empty:
            peak_val = float(eq.loc[eq['date'] == pd.Timestamp(peak_date), 'value'].iloc[0])

            fig.add_trace(go.Scatter(
                x=dd_segment['date'],
                y=[peak_val] * len(dd_segment),
                mode='lines',
                line=dict(color='rgba(239,83,80,0.3)', width=0),
                showlegend=False,
                hoverinfo='skip',
            ))
            fig.add_trace(go.Scatter(
                x=dd_segment['date'],
                y=dd_segment['value'].astype(float),
                mode='lines',
                fill='tonexty',
                fillcolor='rgba(239,83,80,0.12)',
                line=dict(color='rgba(239,83,80,0)', width=0),
                showlegend=False,
                hoverinfo='skip',
            ))
            mid_idx = len(dd_segment) // 2
            fig.add_annotation(
                x=dd_segment['date'].iloc[mid_idx],
                y=peak_val,
                text=(
                    f'最大回撤 -{dd_pct * 100:.2f}% '
                    f'({pd.Timestamp(peak_date).strftime("%Y-%m")} ~ '
                    f'{pd.Timestamp(trough_date).strftime("%Y-%m")})'
                ),
                showarrow=False,
                yshift=15,
                font=dict(color=COLORS['negative'], size=11),
            )

    fig.update_layout(
        template=CHART_THEME['template'],
        height=CHART_THEME['height_equity'],
        margin=CHART_THEME['margin'],
        paper_bgcolor=CHART_THEME['paper_bgcolor'],
        plot_bgcolor=CHART_THEME['plot_bgcolor'],
        legend=dict(orientation='h', yanchor='bottom', y=1.02, x=0),
        hovermode='x unified',
        xaxis=dict(gridcolor=COLORS['grid'], tickformat='%Y-%m'),
        yaxis=dict(gridcolor=COLORS['grid']),
    )

    return fig


def _benchmark_return_series(ohlcv):
    bm = ohlcv.copy().sort_values('date')
    bm['date'] = pd.to_datetime(bm['date'])
    first_close = float(bm['close'].iloc[0])
    bm['return_pct'] = (bm['close'] / first_close - 1) * 100
    return bm[['date', 'return_pct']]


def render_compare_chart(results, show_benchmark=True):
    """渲染多策略归一化累计收益率对比曲线

    Args:
        results: 策略回测结果列表 (由 compare_strategies_detailed 返回)
        show_benchmark: 是否展示买入持有基准

    Returns:
        plotly.graph_objects.Figure
    """
    colors = ['#38bdf8', '#f97316', '#a78bfa', '#22c55e', '#ef4444']

    fig = go.Figure()

    ranked = sorted(
        [r for r in results if r.get('equity_curve') is not None and not r['equity_curve'].empty],
        key=lambda item: item['summary']['total_return'],
        reverse=True,
    )

    if show_benchmark and ranked:
        bm = _benchmark_return_series(ranked[0]['ohlcv'])
        bench_ret = float(bm['return_pct'].iloc[-1])
        fig.add_trace(go.Scatter(
            x=bm['date'],
            y=bm['return_pct'],
            mode='lines',
            name=f'买入持有基准 ({bench_ret:+.1f}%)',
            line=dict(color=COLORS['benchmark'], width=2, dash='dot'),
            opacity=0.85,
            hovertemplate='日期: %{x|%Y-%m-%d}<br>基准累计收益: %{y:+.2f}%<extra></extra>',
        ))

    for i, r in enumerate(ranked):
        eq = r.get('equity_curve')
        eq = eq.copy().sort_values('date')
        eq['date'] = pd.to_datetime(eq['date'])
        start_value = float(eq['value'].iloc[0])
        eq['return_pct'] = (eq['value'] / start_value - 1) * 100
        ret = float(eq['return_pct'].iloc[-1])
        name = r['summary']['strategy']
        line_width = 3 if i == 0 else 2
        fig.add_trace(go.Scatter(
            x=eq['date'],
            y=eq['return_pct'],
            mode='lines',
            name=f'#{i + 1} {name} ({ret:+.1f}%)',
            line=dict(color=colors[i % len(colors)], width=line_width),
            hovertemplate=(
                f'{name}<br>'
                '日期: %{x|%Y-%m-%d}<br>'
                '累计收益: %{y:+.2f}%<extra></extra>'
            ),
        ))
        fig.add_annotation(
            x=eq['date'].iloc[-1],
            y=eq['return_pct'].iloc[-1],
            text=f'{ret:+.1f}%',
            showarrow=False,
            xanchor='left',
            xshift=8,
            font=dict(color=colors[i % len(colors)], size=12),
        )

    fig.add_hline(
        y=0,
        line_dash='dash',
        line_color=COLORS['text_dim'],
        line_width=1,
        opacity=0.6,
    )

    fig.update_layout(
        template=CHART_THEME['template'],
        height=CHART_THEME['height_compare'] + 80,
        margin=dict(l=70, r=90, t=30, b=35),
        legend=dict(orientation='h', yanchor='bottom', y=1.02, x=0),
        paper_bgcolor=CHART_THEME['paper_bgcolor'],
        plot_bgcolor=CHART_THEME['plot_bgcolor'],
        xaxis=dict(gridcolor=COLORS['grid'], tickformat='%Y-%m'),
        yaxis=dict(gridcolor=COLORS['grid'], ticksuffix='%', title='累计收益率'),
        hovermode='x unified',
    )
    return fig
