from binance.client import Client
import time
import numpy as np
import talib


# API密钥信息
api_key = 'YOUR_API_KEY'
secret_key = 'YOUR_SECRET_KEY'

# 交易参数

"""
`symbol`：您要交易的加密货币对，此处为BTC/USDT。
`interval`：您要使用的K线时间间隔，此处为小时级别的K线。
`quantity`：每次下单的数量，此处为1个BTC。
`stop_loss_pct`：止损比例，当价格下跌到某个比例以下时会触发止损，此处设置为2%。
`take_profit_pct`：止盈比例，当价格上涨到某个比例以上时会触发止盈，此处设置为2%。
"""

symbol = 'BTCUSDT'
interval = '1h'
quantity = 0.001
stop_loss_pct = 0.02
take_profit_pct = 0.02


class BinanceTrader:
    def __init__(self, api_key, secret_key):
        try:
            # 初始化API连接
            self.client = Client(api_key, secret_key)
            # 初始化历史K线缓存
            self.historical_klines = {}
        except Exception as e:
            # 发生错误时打印错误信息并关闭API连接
            print(f'初始化API时发生错误: {e}')
            self.client = None

    def __del__(self):
        try:
            # 关闭API连接
            if self.client is not None:
                pass
        except Exception as e:
            # 发生错误时打印错误信息
            print(f'关闭API连接时发生错误: {e}')

    def get_historical_klines(self, symbol, interval, limit):
        """
        获取历史K线数据

        :param symbol: 交易对
        :param interval: K线周期
        :param limit: 返回的K线数量
        :return: 历史K线数据的时间、高价、低价和收盘价
        """
        # 检查历史K线缓存是否已经存在该交易对的K线数据
        if symbol in self.historical_klines and interval in self.historical_klines[symbol]:
            times, high_prices, low_prices, close_prices = self.historical_klines[symbol][interval]
        else:
            times, high_prices, low_prices, close_prices = None, None, None, None
            try:
                # 获取历史K线数据
                kline_data = self.client.futures_klines(symbol=symbol, interval=interval, limit=limit)

                # 将k线数据转换为numpy数组
                klines = np.array(kline_data)

                # 分离出不同的价格数据
                times = klines[:, 0]
                high_prices = klines[:, 2].astype(float)
                low_prices = klines[:, 3].astype(float)
                close_prices = klines[:, 4].astype(float)

                # 缓存K线数据
                if symbol not in self.historical_klines:
                    self.historical_klines[symbol] = {}
                self.historical_klines[symbol][interval] = (times, high_prices, low_prices, close_prices)

            except Exception as e:
                # 发生错误时打印错误信息
                print(f'获取历史K线数据时发生错误: {e}')

        # 返回不同的价格数据
        return times, high_prices, low_prices, close_prices

    def calculate_super_trend(self, close_prices, period, multiplier, upper_bound=0, lower_bound=0, buy_signal=False,
                              sell_signal=False):
        """
        计算超级趋势指标

        :param close_prices: 收盘价序列
        :param period: ATR指标的时间窗口大小
        :param multiplier: 计算上轨和下轨的倍数
        :param upper_bound: 上轨列表，用于生成买入信号
        :param lower_bound: 下轨列表，用于生成卖出信号
        :param buy_signal: 是否生成买入信号
        :param sell_signal: 是否生成卖出信号
        :return: 上轨、下轨和超级趋势指标
        """
        # 计算ATR指标
        high_prices = np.zeros_like(close_prices)
        low_prices = np.zeros_like(close_prices)
        high_prices[0] = close_prices[0]
        low_prices[0] = close_prices[0]
        i = 1
        while i < len(close_prices):
            high_prices[i] = max(close_prices[i], high_prices[i - 1])
            low_prices[i] = min(close_prices[i], low_prices[i - 1])
            i += 1

        tr = np.maximum(high_prices - low_prices, np.abs(high_prices - np.roll(close_prices, 1)),
                         np.abs(low_prices - np.roll(close_prices, 1)))
        atr = talib.SMA(tr, period)

        # 计算超级趋势指标
        upper_band = (high_prices + low_prices) / 2 + multiplier * atr
        lower_band = (high_prices + low_prices) / 2 - multiplier * atr
        super_trend = np.where(close_prices > upper_band, lower_band, upper_band)

        # 生成买入/卖出信号
        if buy_signal:
            upper_bound.append(upper_band[-1])
        if sell_signal:
            lower_bound.append(lower_band[-1])

        # 返回计算结果
        return upper_band, lower_band, super_trend

    def run_strategy(self, symbol, interval, quantity, stop_loss_pct, take_profit_pct):
        """
        运行交易策略

        :param symbol: 交易对
        :param interval: K线周期
        :param quantity: 下单数量
        :param stop_loss_pct: 止损比例
        :param take_profit_pct: 止盈比例
        """
        # 获取历史K线数据
        times, high_prices, low_prices, close_prices = self.get_historical_klines(symbol, interval, limit=100)

        # 计算超级趋势指标
        upper_band, lower_band, super_trend = self.calculate_super_trend(close_prices, period=10, multiplier=3)

        # 循环执行交易策略
        while True:
            try:
                # 获取最新的K线数据
                kline_data = self.client.futures_klines(symbol=symbol, interval=interval, limit=1)

                # 将k线数据转换为numpy数组
                klines = np.array(kline_data)

                # 获得最新的价格和时间
                price = float(klines[-1][4])
                time = klines[-1][0]

                # 添加最新的收盘价到收盘价列表中
                close_prices = np.append(close_prices, [price])

                # 重新计算超级趋势指标
                upper_band, lower_band, super_trend = self.calculate_super_trend(close_prices, period=10, multiplier=3,
                                                                                 upper_bound=upper_band,
                                                                                 lower_bound=lower_band,
                                                                                 buy_signal=True, sell_signal=True)

                # 判断是否满足止损条件
                if price <= (1 - stop_loss_pct) * super_trend[-1]:
                    order = self.client.create_order(
                        symbol=symbol,
                        side=Client.SIDE_SELL,
                        type=Client.ORDER_TYPE_MARKET,
                        quantity=quantity
                    )
                    print(f'stop loss triggered at price {price} at time {time}')
                    break

                # 判断是否满足止盈条件
                if price >= (1 + take_profit_pct) * super_trend[-1]:
                    order = self.client.create_order(
                        symbol=symbol,
                        side=Client.SIDE_SELL,
                        type=Client.ORDER_TYPE_MARKET,
                        quantity=quantity
                    )
                    print(f'take profit triggered at price {price} at time {time}')
                    break

                # 输出当前价格和趋势指标信息
                print(f'current price: {price}, '
                      f'super trend upper band: {upper_band[-1]}, '
                      f'super trend lower band: {lower_band[-1]}')

                # 暂停一段时间，防止频繁调用API
                time.sleep(60)

            except Exception as e:
                # 发生错误时打印错误信息并继续执行策略
                print(f'发生错误: {e}')
                continue


# 初始化交易器
trader = BinanceTrader(api_key, secret_key)

# 运行交易策略
if trader.client is not None:
    trader.run_strategy(symbol, interval, quantity, stop_loss_pct, take_profit_pct)
else:
    print('连接API失败，请检查密钥信息。')
