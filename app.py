# -*- coding: utf-8 -*-
"""Alchequant — 金融量化分析平台（主界面）

职责：UI 布局、session_state 状态管理、参数校验与事件路由
所有图表渲染逻辑已迁移至 src/charts.py
所有工具函数已迁移至 src/utils.py
所有配置项已迁移至 src/config.py
"""
import os

import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from src.database import get_connection, get_stock_list, get_stock_data, get_date_range, get_stock_count
from src.backtest import run_backtest_detailed, compare_strategies_detailed
from src.strategy import DonchianBreakout, RsiStrategy, SmaCross
from src.config import COLORS, QUICK_RANGES, QUICK_RANGE_DEFAULT, STRATEGY_PRESETS, CACHE_TTL
from src.charts import render_kline_chart, render_equity_curve, render_compare_chart
from src.factors import (
    FACTOR_COLUMNS,
    SORT_FACTORS,
    build_factor_explanation,
    calculate_factor_scores,
    export_factor_rank,
    filter_factor_scores,
    get_candidate_list,
)
from src.report import generate_html_report, open_report
from src.utils import (
    format_pct, format_currency, validate_params,
    calc_quick_start, get_selected_rows,
)

st.set_page_config(
    page_title='Alchequant',
    page_icon='💎',
    layout='wide',
)


# ============================================================
#  策略注册表
# ============================================================

STRATEGIES = {
    '双均线交叉': {
        'class': SmaCross,
        'params': {
            'fast': {'label': '短期周期', 'min': 3, 'max': 30, 'default': 5},
            'slow': {'label': '长期周期', 'min': 10, 'max': 120, 'default': 20},
        },
        'desc': '金叉买入，死叉卖出',
    },
    'RSI超买超卖': {
        'class': RsiStrategy,
        'params': {
            'period': {'label': 'RSI周期', 'min': 5, 'max': 30, 'default': 14},
            'oversold': {'label': '超卖阈值', 'min': 10, 'max': 45, 'default': 30},
            'overbought': {'label': '超买阈值', 'min': 55, 'max': 90, 'default': 70},
        },
        'desc': 'RSI 低位买入，高位卖出',
    },
    '唐奇安通道突破': {
        'class': DonchianBreakout,
        'params': {
            'entry_period': {'label': '突破周期', 'min': 10, 'max': 120, 'default': 20},
            'exit_period': {'label': '离场周期', 'min': 5, 'max': 60, 'default': 10},
        },
        'desc': '突破过去高点买入，跌破过去低点卖出',
    },
}


def get_default_params(strat_name):
    """从策略注册表读取默认参数。"""
    return {
        key: cfg['default']
        for key, cfg in STRATEGIES[strat_name]['params'].items()
    }


def get_strategy_notes(strat_name, params):
    """生成当前策略的规则说明，帮助用户理解买卖信号来源。"""
    if strat_name == '双均线交叉':
        fast = params.get('fast', 5)
        slow = params.get('slow', 20)
        return [
            f'MA{fast} 上穿 MA{slow} 时买入，代表短期趋势转强。',
            f'MA{fast} 下穿 MA{slow} 时卖出，代表短期趋势转弱。',
            '图中的两条均线就是买卖信号的直接判断依据。',
        ]
    if strat_name == 'RSI超买超卖':
        period = params.get('period', 14)
        oversold = params.get('oversold', 30)
        overbought = params.get('overbought', 70)
        return [
            f'使用 {period} 日 RSI 衡量价格短期强弱。',
            f'RSI 低于 {oversold} 时买入，认为短线进入超卖区域。',
            f'RSI 高于 {overbought} 时卖出，认为短线进入超买区域。',
        ]
    if strat_name == '唐奇安通道突破':
        entry = params.get('entry_period', 20)
        exit_p = params.get('exit_period', 10)
        return [
            f'收盘价突破过去 {entry} 日最高价时买入，捕捉价格向上突破。',
            f'收盘价跌破过去 {exit_p} 日最低价时卖出，控制突破失败风险。',
            '图中的上轨和下轨分别对应买入触发线与离场触发线。',
        ]
    return [STRATEGIES[strat_name]['desc']]


# ============================================================
#  缓存函数
# ============================================================

@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def load_stock_list():
    """加载股票列表并附带日期范围"""
    conn = get_connection('data/stocks.db')
    df = get_stock_list(conn)
    stocks = []
    for _, row in df.iterrows():
        start_d, end_d = get_date_range(conn, row['code'])
        if start_d is not None:
            stocks.append({'code': row['code'], 'name': row['name'],
                           'start': str(start_d), 'end': str(end_d)})
    conn.close()
    return pd.DataFrame(stocks)


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def run_backtest_cached(code, strat_name, params, cash, commission, position_pct):
    """缓存回测结果，键由 code+策略名+参数+回测设置构成"""
    cfg = STRATEGIES[strat_name]
    return run_backtest_detailed(
        code, cfg['class'],
        strategy_params=params,
        cash=cash,
        commission=commission,
        position_pct=position_pct,
    )


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def run_compare_cached(code, strat_names, cash, commission, position_pct):
    """缓存策略对比结果"""
    strategy_list = [
        (STRATEGIES[n]['class'], get_default_params(n))
        for n in strat_names
    ]
    return compare_strategies_detailed(
        code,
        strategy_list,
        cash=cash,
        commission=commission,
        position_pct=position_pct,
    )


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def load_factor_scores(lookback_days, min_obs):
    """缓存因子评分结果。"""
    return calculate_factor_scores(
        db_path='data/stocks.db',
        lookback_days=lookback_days,
        min_obs=min_obs,
    )


# ============================================================
#  回调函数
# ============================================================

def apply_preset():
    """策略预设选择回调：将预设参数写入 slider 的 session_state"""
    preset = st.session_state.get('preset', '自定义')
    if preset in STRATEGY_PRESETS:
        p = STRATEGY_PRESETS[preset]
        st.session_state['p_双均线交叉_fast'] = p['fast']
        st.session_state['p_双均线交叉_slow'] = p['slow']


def on_quick_range_change():
    """快捷时间范围变更回调：清除高亮日期"""
    st.session_state.highlight_date = None


# ============================================================
#  主页面
# ============================================================

st.markdown('# 💎 Alchequant')
st.markdown('*本地量化分析平台 — 选股、策略、回测、对比，一站完成*')
st.markdown('')

page = st.pills(
    '导航',
    options=['策略回测', '策略对比', '因子看板', '数据总览'],
    default='策略回测',
    label_visibility='collapsed',
)

stock_df = load_stock_list()
stock_options = [f"{r['code']} {r['name']}" for _, r in stock_df.iterrows()] if not stock_df.empty else []


# ============================================================
#  策略回测页面
# ============================================================

if page == '策略回测':
    cols = st.columns([1, 3])

    # ---- 左侧控制面板 ----
    left_cell = cols[0].container(border=True, height='stretch')

    with left_cell:
        st.markdown('### ⚙️ 参数设置')

        stock_sel = st.selectbox('股票', stock_options, key='bt_stock', placeholder='选择股票...')
        selected_code = stock_sel.split(' ')[0] if stock_sel else None

        strat_sel = st.selectbox('策略', list(STRATEGIES.keys()), key='bt_strat')

        if strat_sel == '双均线交叉':
            # [优化] 策略预设模板
            st.markdown('---')
            st.selectbox(
                '策略预设', ['自定义'] + list(STRATEGY_PRESETS.keys()),
                key='preset', on_change=apply_preset,
            )
        else:
            st.markdown('---')
            st.caption(STRATEGIES[strat_sel]['desc'])

        # 策略参数
        st.markdown('**策略参数**')
        params = {}
        if STRATEGIES[strat_sel]['params']:
            for key, cfg in STRATEGIES[strat_sel]['params'].items():
                params[key] = st.slider(
                    cfg['label'], cfg['min'], cfg['max'], cfg['default'],
                    key=f'p_{strat_sel}_{key}',
                )
        else:
            st.caption('该策略无需额外参数')

        # [优化] 回测设置折叠
        with st.expander('回测设置'):
            cash = st.number_input('初始资金', 10000, 10000000, 100000, 10000, key='bt_cash')
            commission = st.number_input(
                '手续费率',
                min_value=0.0,
                max_value=0.01,
                value=0.001,
                step=0.0001,
                format='%.4f',
                key='bt_commission',
                help='0.001 表示单边 0.1%，频繁交易策略对该参数更敏感。',
            )
            position_pct = st.slider(
                '单次建仓比例',
                min_value=10,
                max_value=100,
                value=95,
                step=5,
                key='bt_position_pct',
                help='每次买入时使用可用资金的比例。保留少量现金可减少满仓失败和手续费影响。',
            )

        # [P4] 参数实时校验
        is_valid, error_msg = validate_params(params, cash, commission, position_pct)
        if not is_valid:
            st.warning(f'❌ {error_msg}')

        run_bt = st.button('🚀 运行回测', type='primary', use_container_width=True, disabled=not is_valid)

    # ---- 右侧结果区域 ----
    right_cell = cols[1].container(border=True, height='stretch')

    # 运行回测
    if run_bt and selected_code:
        with st.spinner('⏳ 回测中...'):
            try:
                result = run_backtest_cached(
                    selected_code, strat_sel, params, cash, commission, position_pct,
                )
                st.session_state.backtest_result = result
                st.session_state.backtest_meta = {
                    'strategy_name': strat_sel,
                    'params': params.copy(),
                    'cash': cash,
                    'commission': commission,
                    'position_pct': position_pct,
                }
                st.session_state.error_msg = None
                st.session_state.highlight_date = None
            except Exception as e:
                st.session_state.backtest_result = None
                st.session_state.error_msg = str(e)

    result = st.session_state.get('backtest_result')
    error = st.session_state.get('error_msg')

    # [P4] 错误处理边界防御
    if error:
        with right_cell:
            st.error(f'❌ 回测失败：{error}')
        st.stop()

    if not result:
        right_cell.info('👈 选择股票和参数，点击运行回测', icon='💎')
        st.stop()

    # 从结果提取数据
    s = result['summary']
    trades = result['trades']
    equity = result['equity_curve']
    ohlcv = result['ohlcv']
    meta = st.session_state.get('backtest_meta', {
        'strategy_name': strat_sel,
        'params': params.copy(),
        'cash': cash,
        'commission': commission,
        'position_pct': position_pct,
    })
    active_strategy = meta['strategy_name']
    active_params = meta['params']

    # 计算基准
    bench_df = ohlcv.copy().sort_values('date')
    first_close = float(bench_df['close'].iloc[0])
    bench_df['benchmark_value'] = s['initial_cash'] * (bench_df['close'] / first_close)
    bench_df['date'] = pd.to_datetime(bench_df['date'])

    # 全局时间范围
    full_start = pd.Timestamp(ohlcv['date'].min())
    full_end = pd.Timestamp(ohlcv['date'].max())

    # [联动] 提前计算全局时间范围，供净值曲线、K线图、交易明细统一使用
    range_key = st.session_state.get('quick_range', QUICK_RANGE_DEFAULT)
    calc = calc_quick_start(range_key, full_end)
    effective_start = calc.date() if calc else full_start.date()
    effective_end = full_end.date()
    ds_key = f'ds_{range_key}'
    de_key = f'de_{range_key}'
    if ds_key in st.session_state:
        effective_start = st.session_state[ds_key]
    if de_key in st.session_state:
        effective_end = st.session_state[de_key]

    # ---- 指标卡片 ----
    with right_cell:
        m_cols = st.columns(4)
        tr = s['total_return']
        m_cols[0].metric(
            '总收益率', format_pct(tr),
            delta=format_pct(tr),
            delta_color='normal' if tr >= 0 else 'inverse',
        )
        m_cols[1].metric(
            '年化收益', format_pct(s['annual_return']),
            delta=f'（数据覆盖 {s["data_days"]} 交易日）',
        )
        m_cols[2].metric(
            '夏普比率', f'{s["sharpe_ratio"]:.3f}',
            delta_color='inverse' if s['sharpe_ratio'] < 0 else 'normal',
        )
        m_cols[3].metric(
            '最大回撤', f'{s["max_drawdown"] * 100:.2f}% ⚠️',
            delta_color='inverse',
        )

        m2 = st.columns(4)
        m2[0].metric('胜率', f'{s["win_rate"] * 100:.1f}%')
        m2[1].metric('交易次数', str(s['total_trades']))
        m2[2].metric('最终资金', format_currency(s['final_value']))
        m2[3].metric('盈亏比', f'{s["profit_factor"]:.2f}')

        st.caption(
            f'回测设置：手续费率 {s.get("commission", 0.001) * 100:.2f}% / '
            f'单次建仓 {s.get("position_pct", 95):.0f}%'
        )

        with st.expander('AI增强报告（可选）'):
            use_ai_report = st.checkbox(
                '使用 AI 生成专业差异化文字',
                value=False,
                key='use_ai_report',
                help='本地指标和图表仍由系统计算，AI 只负责改写报告文字。关闭时完全不调用 API。',
            )
            ai_cols = st.columns([1, 1, 1])
            with ai_cols[0]:
                llm_model = st.text_input(
                    '模型',
                    value=os.getenv('LLM_MODEL') or os.getenv('OPENAI_MODEL') or 'gpt-4o-mini',
                    key='llm_model',
                )
            with ai_cols[1]:
                llm_base_url = st.text_input(
                    'Base URL',
                    value=os.getenv('LLM_BASE_URL') or os.getenv('OPENAI_BASE_URL') or 'https://api.openai.com/v1',
                    key='llm_base_url',
                )
            with ai_cols[2]:
                llm_api_key = st.text_input(
                    'API Key',
                    value='',
                    type='password',
                    key='llm_api_key',
                    placeholder='留空读取环境变量',
                )
            st.caption('支持 OpenAI-compatible 接口。API Key 只在本次生成时使用，不写入项目文件。')

        report_cols = st.columns([1, 3])
        with report_cols[0]:
            make_report = st.button('📄 生成HTML报告', use_container_width=True)
        with report_cols[1]:
            if make_report:
                stock_name = stock_sel.split(' ', 1)[1] if stock_sel and ' ' in stock_sel else ''
                try:
                    report_path = generate_html_report(
                        result,
                        stock_code=selected_code,
                        stock_name=stock_name,
                        strategy_name=active_strategy,
                        strategy_params=active_params,
                        ai_config={
                            'enabled': use_ai_report,
                            'api_key': llm_api_key,
                            'base_url': llm_base_url,
                            'model': llm_model,
                        },
                    )
                    opened = open_report(report_path)
                    if opened:
                        st.success('报告已生成，并已用系统默认程序打开 HTML 文件。')
                    else:
                        st.success(f'报告已生成：{report_path.as_posix()}')
                except Exception as e:
                    st.error(f'报告生成失败：{e}')

        st.markdown('---')
        st.markdown('#### 📈 净值曲线')
        st.plotly_chart(
            render_equity_curve(equity, bench_df,
                                start_date=str(effective_start),
                                end_date=str(effective_end)),
            use_container_width=True,
        )

    # ---- K 线图（全宽）----
    st.markdown('---')

    # [P0] 快捷时间选择器
    header_cols = st.columns([3, 2])
    with header_cols[0]:
        st.markdown('#### 📊 K线图')
    with header_cols[1]:
        st.pills(
            '⏱ 时间范围', QUICK_RANGES, default=QUICK_RANGE_DEFAULT,
            key='quick_range', on_change=on_quick_range_change,
        )

    # [联动] 动态 key：切换快捷范围时重置日期选择器
    range_key = st.session_state.get('quick_range', QUICK_RANGE_DEFAULT)
    start_key = f'ds_{range_key}'
    end_key = f'de_{range_key}'

    calc = calc_quick_start(range_key, full_end)
    default_s = calc.date() if calc else full_start.date()
    default_e = full_end.date()

    date_cols = st.columns([1, 1, 2])
    with date_cols[0]:
        chart_start = st.date_input('开始日期', value=default_s, key=start_key)
    with date_cols[1]:
        chart_end = st.date_input('结束日期', value=default_e, key=end_key)

    with st.expander('策略信号说明', expanded=True):
        for note in get_strategy_notes(active_strategy, active_params):
            st.markdown(f'- {note}')

    # 读取高亮日期（表格联动）
    highlight_date = st.session_state.get('highlight_date')

    st.plotly_chart(
        render_kline_chart(
            ohlcv, trades,
            start_date=str(chart_start),
            end_date=str(chart_end),
            highlight_date=highlight_date,
            strategy_name=active_strategy,
            strategy_params=active_params,
        ),
        use_container_width=True,
    )

    # ---- 交易明细 ----
    st.markdown('---')
    st.markdown('#### 📋 交易明细')

    if trades:
        tbl = pd.DataFrame(trades)
        tbl = tbl.rename(columns={
            'date_in': '买入日期',
            'date_out': '卖出日期',
            'price_in': '买入价',
            'price_out': '卖出价',
            'size': '数量',
            'pnl': '盈亏',
            'pnlcomm': '净盈亏(含手续费)',
        })
        tbl['收益率'] = (tbl['卖出价'] / tbl['买入价'] - 1) * 100

        # 日期清洗
        tbl['买入日期'] = pd.to_datetime(tbl['买入日期']).dt.strftime('%Y-%m-%d')
        tbl['卖出日期'] = pd.to_datetime(tbl['卖出日期']).dt.strftime('%Y-%m-%d')

        # 净盈亏列类型转换
        if '净盈亏(含手续费)' in tbl.columns:
            tbl['净盈亏(含手续费)'] = pd.to_numeric(tbl['净盈亏(含手续费)'], errors='coerce')

        # [P1] 交易筛选器
        filter_cols = st.columns([1, 1, 2])
        with filter_cols[0]:
            trade_filter = st.selectbox(
                '筛选', ['全部交易', '仅盈利', '仅亏损', '收益率>5%'],
                key='trade_filter',
            )
        with filter_cols[1]:
            date_filter_link = st.checkbox('按K线日期筛选', value=True, key='date_filter_link')

        # 应用筛选
        filtered = tbl.copy()
        if trade_filter == '仅盈利':
            filtered = filtered[filtered['盈亏'] > 0]
        elif trade_filter == '仅亏损':
            filtered = filtered[filtered['盈亏'] < 0]
        elif trade_filter == '收益率>5%':
            filtered = filtered[filtered['收益率'] > 5]

        # [联动] 日期范围筛选与K线同步
        if date_filter_link:
            filtered = filtered[
                (pd.to_datetime(filtered['买入日期']) >= pd.Timestamp(chart_start)) &
                (pd.to_datetime(filtered['卖出日期']) <= pd.Timestamp(chart_end))
            ]

        if filtered.empty:
            st.info('📊 当前筛选条件下无交易记录')
        else:
            # [P2] 条件格式 — A股习惯：红盈绿亏
            def highlight_pnl(val):
                if pd.isna(val):
                    return ''
                return f'background-color: {"#ef535022" if val >= 0 else "#26a69a22"}'

            styled = filtered.style.format({
                '买入价': '{:.2f}',
                '卖出价': '{:.2f}',
                '盈亏': '{:+,.2f}',
                '净盈亏(含手续费)': '{:+,.2f}',
                '收益率': '{:+.2f}%',
                '数量': '{:.0f}',
            }).map(highlight_pnl, subset=['盈亏', '净盈亏(含手续费)'])

            # [联动] 表格行点击 → K线垂直高亮线
            selection = st.dataframe(
                styled,
                use_container_width=True,
                height=300,
                on_select='rerun',
                selection_mode=['multi-row'],
                hide_index=True,
            )

            selected_rows = get_selected_rows(selection)
            if selected_rows:
                row_idx = selected_rows[0]
                st.session_state.highlight_date = str(filtered.iloc[row_idx]['买入日期'])
            else:
                st.session_state.highlight_date = None

            # 净盈亏列说明
            st.caption('💡 *净盈亏(含手续费)：扣除佣金和印花税后的实际盈亏*')
    else:
        st.info('📊 该参数组合下未产生任何交易，请调整策略参数')


# ============================================================
#  策略对比页面
# ============================================================

elif page == '策略对比':
    cols = st.columns([1, 3])

    left_cell = cols[0].container(border=True, height='stretch')

    with left_cell:
        st.markdown('### ⚙️ 对比设置')
        stock_sel = st.selectbox('股票', stock_options, key='cmp_stock')
        selected_code = stock_sel.split(' ')[0] if stock_sel else None

        compare_strats = st.multiselect(
            '选择策略', list(STRATEGIES.keys()),
            default=list(STRATEGIES.keys())[:min(3, len(STRATEGIES))],
            key='cmp_strats',
        )

        with st.expander('回测设置'):
            cmp_cash = st.number_input('初始资金', 10000, 10000000, 100000, 10000, key='cmp_cash')
            cmp_commission = st.number_input(
                '手续费率',
                min_value=0.0,
                max_value=0.01,
                value=0.001,
                step=0.0001,
                format='%.4f',
                key='cmp_commission',
            )
            cmp_position_pct = st.slider(
                '单次建仓比例',
                min_value=10,
                max_value=100,
                value=95,
                step=5,
                key='cmp_position_pct',
            )

        run_cmp = st.button('🚀 运行对比', type='primary', use_container_width=True)

    right_cell = cols[1].container(border=True, height='stretch')

    if not run_cmp or not selected_code or not compare_strats:
        right_cell.info('👈 选择股票和策略，点击运行对比', icon='💎')
        st.stop()

    with st.spinner('⏳ 对比中...'):
        try:
            results = run_compare_cached(
                selected_code,
                compare_strats,
                cmp_cash,
                cmp_commission,
                cmp_position_pct,
            )
        except Exception as e:
            right_cell.error(f'❌ 对比失败：{e}')
            st.stop()

    with right_cell:
        st.markdown('#### 📈 多策略累计收益率对比')
        st.caption('曲线统一从 0% 起步，橙色虚线为买入持有基准；右侧标签显示区间最终累计收益。')
        st.plotly_chart(render_compare_chart(results), use_container_width=True)

    st.markdown('---')
    st.markdown('#### 📋 策略排名与指标对比')
    rows = []
    ranked_results = sorted(results, key=lambda item: item['summary']['total_return'], reverse=True)
    benchmark_return = None
    if ranked_results:
        ohlcv = ranked_results[0]['ohlcv'].copy().sort_values('date')
        benchmark_return = float(ohlcv['close'].iloc[-1] / ohlcv['close'].iloc[0] - 1)

    for idx, r in enumerate(ranked_results, start=1):
        s = r['summary']
        rows.append({
            '排名': idx,
            '策略': s['strategy'],
            '总收益率': format_pct(s['total_return']),
            '基准收益': format_pct(benchmark_return) if benchmark_return is not None else '--',
            '超额收益': format_pct(s['total_return'] - benchmark_return) if benchmark_return is not None else '--',
            '年化': format_pct(s['annual_return']),
            '夏普': f'{s["sharpe_ratio"]:.3f}',
            '最大回撤': f'{s["max_drawdown"] * 100:.2f}%',
            '胜率': f'{s["win_rate"] * 100:.1f}%',
            '交易次数': s['total_trades'],
        })
    compare_df = pd.DataFrame(rows)

    def color_signed_text(val):
        if not isinstance(val, str) or val == '--':
            return ''
        if val.startswith('+'):
            return 'color: #ef5350; font-weight: 600'
        if val.startswith('-'):
            return 'color: #26a69a; font-weight: 600'
        return ''

    styled_compare = compare_df.style.map(
        color_signed_text,
        subset=['总收益率', '超额收益', '年化'],
    )
    st.dataframe(styled_compare, use_container_width=True, hide_index=True)


# ============================================================
#  因子看板页面
# ============================================================

elif page == '因子看板':
    cols = st.columns([1, 3])

    left_cell = cols[0].container(border=True, height='stretch')
    with left_cell:
        st.markdown('### 🧭 因子设置')
        lookback_days = st.selectbox(
            '研究窗口',
            options=[120, 180, 252, 504],
            index=2,
            format_func=lambda x: f'近{x}个交易日',
            key='factor_lookback',
            help='决定因子计算最多使用多长的历史窗口。例如近120个交易日会用最近120个交易日计算趋势、风险和动量。'
        )
        min_obs = st.slider(
            '样本过滤门槛',
            60,
            min(240, lookback_days),
            min(120, lookback_days),
            20,
            key='factor_min_obs',
            help='只用于过滤数据太少的股票，不改变动量60日、动量120日、波动率20日等因子的计算公式。',
        )
        sort_factor = st.selectbox('排序因子', list(SORT_FACTORS.keys()), key='factor_sort')
        risk_filter = st.selectbox('风险过滤', ['全部', '低', '中', '高'], key='factor_risk')
        top_n = st.slider('Top N 数量', 5, 28, 10, 1, key='factor_top_n')
        refresh = st.button('🔄 重新计算', type='primary', use_container_width=True)
        if refresh:
            load_factor_scores.clear()

        st.markdown('---')
        st.caption(
            '研究窗口决定指标取数范围；样本过滤门槛只决定股票是否纳入计算。'
            '若当前股票池都满足门槛，调节门槛不会改变已纳入股票的因子数值。'
        )
        st.caption('所有评分来自本地行情数据计算；价格分位为行情代理指标，不等同于财务估值。')
        with st.expander('因子说明'):
            st.markdown('- 综合评分：动量 35% + 趋势 25% + 风险 20% + 活跃度 10% + 价格分位 10%。')
            st.markdown('- 动量类、趋势类、风险评分：数值越高越靠前。')
            st.markdown('- 20日波动率、120日价格分位：默认低值优先，用于寻找波动或位置相对更低的标的。')
            st.markdown('- 候选名单：综合评分靠前且风险等级不是“高”的研究名单，不代表买入建议。')

    factors = load_factor_scores(lookback_days, min_obs)
    right_cell = cols[1].container(border=True, height='stretch')

    if factors.empty:
        right_cell.warning('当前数据库没有足够数据用于因子计算。')
        st.stop()

    ranked = filter_factor_scores(factors, sort_factor, risk_filter, top_n)
    candidates = get_candidate_list(factors, top_n)
    sort_direction = '低值优先' if SORT_FACTORS.get(sort_factor) in {'波动率20日', '价格分位120日', '最大回撤'} else '高值优先'

    with right_cell:
        metric_cols = st.columns(4)
        metric_cols[0].metric('覆盖股票', f'{len(factors)}')
        metric_cols[1].metric('候选数量', f'{len(get_candidate_list(factors, 999))}')
        metric_cols[2].metric('平均综合评分', f'{factors["综合评分"].mean():.1f}')
        metric_cols[3].metric('高风险数量', f'{(factors["风险等级"] == "高").sum()}')
        st.caption(
            f'本次使用近 {lookback_days} 个交易日作为研究窗口，'
            f'剔除少于 {min_obs} 个有效样本的股票；当前纳入 {len(factors)} 只。'
        )
        st.caption(f'当前排序：{sort_factor}（{sort_direction}）；风险过滤：{risk_filter}。')

        st.markdown('#### 📋 因子排名')
        table_cols = [
            '代码', '名称', '最新日期', '综合评分', '候选标记', '风险等级',
            '动量60日', '动量120日', '波动率20日', '最大回撤', '成交量比20日', '价格分位120日',
        ]

        def color_risk(val):
            if val == '高':
                return 'color: #ef5350; font-weight: 600'
            if val == '低':
                return 'color: #22c55e; font-weight: 600'
            return 'color: #f59e0b; font-weight: 600'

        if ranked.empty:
            st.info('当前风险过滤条件下没有可展示股票，请放宽风险过滤或降低样本过滤门槛。')
        else:
            display_ranked = ranked[table_cols].copy()
            styled_ranked = display_ranked.style.format({
                '综合评分': '{:.2f}',
                '动量60日': '{:+.2%}',
                '动量120日': '{:+.2%}',
                '波动率20日': '{:.2%}',
                '最大回撤': '{:.2%}',
                '成交量比20日': '{:.2f}',
                '价格分位120日': '{:.1%}',
            }).map(color_risk, subset=['风险等级'])
            st.dataframe(styled_ranked, use_container_width=True, hide_index=True, height=360)

        export_cols = st.columns([1, 3])
        with export_cols[0]:
            if st.button('💾 导出CSV', use_container_width=True):
                path = export_factor_rank(factors)
                st.session_state.factor_export_path = str(path)
        with export_cols[1]:
            export_path = st.session_state.get('factor_export_path')
            if export_path:
                st.success(f'已导出：{export_path}')
                st.download_button(
                    '下载最新因子排名',
                    data=factors.to_csv(index=False, encoding='utf-8-sig'),
                    file_name=export_path.split('\\')[-1].split('/')[-1],
                    mime='text/csv',
                )

        st.markdown('---')
        chart_metric = SORT_FACTORS.get(sort_factor, '综合评分')
        chart_title = f'📊 Top {len(ranked)} {sort_factor}'
        st.markdown(f'#### {chart_title}')
        st.caption('柱状图跟随左侧的排序因子、风险过滤和 Top N 数量；悬停可查看综合评分与风险等级。')
        chart_df = ranked.copy()
        if chart_df.empty:
            st.info('当前筛选条件下没有可绘制的柱状图。')
        else:
            score_min = float(chart_df[chart_metric].min())
            score_max = float(chart_df[chart_metric].max())
            score_span = max(score_max - score_min, 5.0)
            y_min = score_min - score_span * 0.25
            y_max = score_max + score_span * 0.25
            if chart_metric in FACTOR_COLUMNS:
                y_min = max(0, y_min)
                y_max = min(100, y_max)
            elif score_min < 0 < score_max:
                y_min = min(y_min, 0)
                y_max = max(y_max, 0)
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=chart_df['名称'],
                y=chart_df[chart_metric],
                marker_color=[
                    COLORS['negative'] if risk == '高' else COLORS['primary']
                    for risk in chart_df['风险等级']
                ],
                customdata=chart_df[['代码', '综合评分', '风险等级', '候选标记']].values,
                hovertemplate=(
                    '%{customdata[0]} %{x}<br>'
                    f'{sort_factor}: %{{y:.2f}}<br>'
                    '综合评分: %{customdata[1]:.2f}<br>'
                    '风险等级: %{customdata[2]}<br>'
                    '状态: %{customdata[3]}<extra></extra>'
                ),
            ))
            fig.update_layout(
                template='plotly_dark',
                height=360,
                margin=dict(l=50, r=20, t=20, b=80),
                paper_bgcolor=COLORS['bg'],
                plot_bgcolor=COLORS['bg'],
                yaxis=dict(range=[y_min, y_max], gridcolor=COLORS['grid'], title=sort_factor),
                xaxis=dict(tickangle=-30, gridcolor=COLORS['grid']),
            )
            st.plotly_chart(fig, use_container_width=True)

    st.markdown('---')
    lower_cols = st.columns([2, 1])
    with lower_cols[0].container(border=True):
        st.markdown('#### ✅ 因子筛选候选名单')
        candidate_cols = ['代码', '名称', '综合评分', '风险等级', '动量60日', '趋势评分', '风险评分']
        candidate_display = candidates[candidate_cols].copy()
        st.dataframe(
            candidate_display.style.format({
                '综合评分': '{:.2f}',
                '动量60日': '{:+.2%}',
                '趋势评分': '{:.2f}',
                '风险评分': '{:.2f}',
            }).map(color_risk, subset=['风险等级']),
            use_container_width=True,
            hide_index=True,
            height=300,
        )

    with lower_cols[1].container(border=True):
        st.markdown('#### ⚠️ 风险提示')
        risk_table = factors.sort_values(['风险等级', '波动率20日'], ascending=[False, False]).head(8)
        st.dataframe(
            risk_table[['代码', '名称', '风险等级', '波动率20日', '最大回撤']].style.format({
                '波动率20日': '{:.2%}',
                '最大回撤': '{:.2%}',
            }).map(color_risk, subset=['风险等级']),
            use_container_width=True,
            hide_index=True,
            height=300,
        )

    st.markdown('---')
    st.markdown('#### 🔎 单只股票因子解释')
    factor_options = [f"{r['代码']} {r['名称']}" for _, r in factors.iterrows()]
    selected_factor_stock = st.selectbox('选择股票', factor_options, key='factor_detail_stock')
    selected_factor_code = selected_factor_stock.split(' ')[0]
    detail_row = factors[factors['代码'] == selected_factor_code].iloc[0]
    score_df = pd.DataFrame({
        '评分项': FACTOR_COLUMNS,
        '分数': [detail_row[col] for col in FACTOR_COLUMNS],
    })
    score_fig = go.Figure()
    score_fig.add_trace(go.Bar(
        x=score_df['评分项'],
        y=score_df['分数'],
        marker_color=[COLORS['primary'], '#38bdf8', '#f59e0b', '#22c55e', '#a78bfa', '#f97316'],
        hovertemplate='%{x}: %{y:.2f}<extra></extra>',
    ))
    score_fig.update_layout(
        template='plotly_dark',
        height=280,
        margin=dict(l=40, r=20, t=15, b=60),
        paper_bgcolor=COLORS['bg'],
        plot_bgcolor=COLORS['bg'],
        yaxis=dict(range=[0, 100], gridcolor=COLORS['grid'], title='评分'),
        xaxis=dict(tickangle=-20, gridcolor=COLORS['grid']),
    )
    st.plotly_chart(score_fig, use_container_width=True)
    for line in build_factor_explanation(detail_row):
        st.markdown(f'- {line}')


# ============================================================
#  数据总览页面
# ============================================================

elif page == '数据总览':
    cols = st.columns([1, 3])

    left_cell = cols[0].container(border=True, height='stretch')

    with left_cell:
        st.markdown('### 📊 数据库统计')
        conn = get_connection('data/stocks.db')
        total = len(get_stock_list(conn))
        count = get_stock_count(conn)
        conn.close()

        st.metric('沪深300成分股', str(total))
        st.metric('已下载数据', str(count))

        if not stock_df.empty:
            st.metric('数据范围', f'{stock_df["start"].str[:7].min()} ~ {stock_df["end"].str[:7].max()}')

    right_cell = cols[1].container(border=True, height='stretch')

    with right_cell:
        st.markdown('#### 📋 股票清单')
        search = st.text_input('搜索', placeholder='代码或名称...')
        display = stock_df.rename(columns={'code': '代码', 'name': '名称', 'start': '起始', 'end': '结束'})
        if search:
            mask = display['代码'].str.contains(search) | display['名称'].str.contains(search)
            display = display[mask]
        st.dataframe(display, use_container_width=True, height=500, hide_index=True)


# 页脚
st.markdown('')
st.markdown('---')
st.caption('💎 Alchequant | 数据: AKShare | 引擎: Backtrader | 框架: Streamlit')
