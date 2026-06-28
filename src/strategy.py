import backtrader as bt

__all__ = ['BuyAndHold', 'RsiStrategy', 'DonchianBreakout', 'SmaCross']


class BuyAndHold(bt.Strategy):
    """买入持有策略：首个可交易日买入，之后一直持有到回测结束"""

    def __init__(self):
        self.order = None
        self.has_bought = False

    def next(self):
        if self.order or self.has_bought:
            return
        self.order = self.buy()
        self.has_bought = True

    def notify_order(self, order):
        if order.status in [order.Submitted, order.Accepted]:
            return
        self.order = None


class RsiStrategy(bt.Strategy):
    """RSI 超买超卖策略：RSI 低位买入，高位卖出"""

    params = (
        ('period', 14),
        ('oversold', 30),
        ('overbought', 70),
    )

    def __init__(self):
        self.rsi = bt.ind.RSI_Safe(self.data.close, period=self.params.period)
        self.order = None

    def next(self):
        if self.order:
            return
        if not self.position and self.rsi < self.params.oversold:
            self.order = self.buy()
        elif self.position and self.rsi > self.params.overbought:
            self.order = self.close()

    def notify_order(self, order):
        if order.status in [order.Submitted, order.Accepted]:
            return
        self.order = None


class DonchianBreakout(bt.Strategy):
    """唐奇安通道突破策略：突破 N 日高点买入，跌破 M 日低点卖出"""

    params = (
        ('entry_period', 20),
        ('exit_period', 10),
    )

    def __init__(self):
        self.entry_high = bt.ind.Highest(self.data.high(-1), period=self.params.entry_period)
        self.exit_low = bt.ind.Lowest(self.data.low(-1), period=self.params.exit_period)
        self.order = None

    def next(self):
        if self.order:
            return
        if not self.position and self.data.close[0] > self.entry_high[0]:
            self.order = self.buy()
        elif self.position and self.data.close[0] < self.exit_low[0]:
            self.order = self.close()

    def notify_order(self, order):
        if order.status in [order.Submitted, order.Accepted]:
            return
        self.order = None


class SmaCross(bt.Strategy):
    """双均线交叉策略：短期均线上穿长期均线买入（金叉），下穿卖出（死叉）"""

    params = (
        ('fast', 5),
        ('slow', 20),
    )

    def __init__(self):
        sma_fast = bt.ind.SMA(period=self.params.fast)
        sma_slow = bt.ind.SMA(period=self.params.slow)
        self.crossover = bt.ind.CrossOver(sma_fast, sma_slow)
        self.order = None

    def log(self, txt, dt=None):
        dt = dt or self.datas[0].datetime.date(0)
        print(f'{dt.isoformat()} {txt}')

    def notify_order(self, order):
        if order.status in [order.Submitted, order.Accepted]:
            return
        if order.status in [order.Completed]:
            if order.isbuy():
                self.log(f'买入 {order.executed.size} 股 @ {order.executed.price:.2f}')
            else:
                self.log(f'卖出 {order.executed.size} 股 @ {order.executed.price:.2f}')
        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log('订单取消/拒绝')
        self.order = None

    def next(self):
        if self.order:
            return
        if not self.position:
            if self.crossover > 0:
                self.order = self.buy()
        elif self.crossover < 0:
            self.order = self.close()
