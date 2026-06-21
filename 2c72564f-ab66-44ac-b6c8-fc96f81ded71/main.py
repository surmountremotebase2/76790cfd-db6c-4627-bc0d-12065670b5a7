from surmount.base_class import Strategy, TargetAllocation
import math


class TradingStrategy(Strategy):
    def __init__(self):
        self.market_filter = "SPY"

        self.universe = [
            "NVDA", "AVGO", "AMD", "TSM", "ASML", "MU",
            "ANET", "ETN", "PWR",
            "GE", "HWM", "RTX",
            "MSFT", "META", "GOOGL", "AMZN", "PANW", "CRWD"
        ]

        self.tickers = self.universe + [self.market_filter]

        self.max_positions = 6
        self.bull_max_invested = 0.85
        self.caution_max_invested = 0.45

        self.market_sma_fast = 50
        self.market_sma_slow = 200
        self.stock_sma_fast = 50
        self.stock_sma_slow = 150

        self.momentum_3m = 63
        self.momentum_1m = 21
        self.momentum_2w = 10

        self.rsi_period = 14
        self.rsi_min = 45
        self.rsi_max = 72
        self.rsi_exit = 82

        self.min_weight = 0.04
        self.max_weight = 0.15
        self.profit_target_pct = 0.50

        self.tier_weights = {
            "NVDA": 1.35, "AVGO": 1.45, "AMD": 1.10,
            "TSM": 1.15, "ASML": 1.10, "MU": 0.90,
            "ANET": 1.25, "ETN": 1.15, "PWR": 1.15,
            "GE": 1.10, "HWM": 1.20, "RTX": 1.00,
            "MSFT": 1.15, "META": 1.15, "GOOGL": 1.05,
            "AMZN": 1.05, "PANW": 1.10, "CRWD": 1.00
        }

    @property
    def interval(self):
        return "1day"

    @property
    def assets(self):
        return self.tickers

    def get_series(self, ohlcv, ticker, field):
        values = []
        try:
            bars = ohlcv.get(ticker, [])
            for bar in bars:
                value = bar.get(field)
                if value is not None:
                    values.append(float(value))
        except Exception:
            pass
        return values

    def sma(self, values, period):
        if len(values) < period:
            return None
        return sum(values[-period:]) / float(period)

    def rsi(self, values, period):
        if len(values) < period + 1:
            return None

        gains = 0.0
        losses = 0.0

        for i in range(-period, 0):
            change = values[i] - values[i - 1]
            if change > 0:
                gains += change
            else:
                losses += abs(change)

        avg_gain = gains / float(period)
        avg_loss = losses / float(period)

        if avg_loss == 0:
            return 100.0

        rs = avg_gain / avg_loss
        return 100.0 - (100.0 / (1.0 + rs))

    def momentum_score(self, closes):
        if len(closes) < self.momentum_3m + 1:
            return None

        if closes[-self.momentum_3m] <= 0:
            return None
        if closes[-self.momentum_1m] <= 0:
            return None
        if closes[-self.momentum_2w] <= 0:
            return None

        m3 = closes[-1] / closes[-self.momentum_3m] - 1.0
        m1 = closes[-1] / closes[-self.momentum_1m] - 1.0
        m2w = closes[-1] / closes[-self.momentum_2w] - 1.0

        return (m3 * 0.50) + (m1 * 0.30) + (m2w * 0.20)

    def is_held(self, holdings, ticker):
        try:
            h = holdings.get(ticker)
            if not h:
                return False

            if isinstance(h, dict):
                quantity = h.get("quantity", h.get("shares", h.get("weight", 0)))
                return float(quantity or 0) > 0

            return float(h) > 0
        except Exception:
            return False

    def get_entry_price(self, holdings, ticker, current_price):
        try:
            h = holdings.get(ticker, {})
            if isinstance(h, dict):
                keys = ["avg_price", "average_price", "cost_basis", "average_cost", "avg_cost"]
                for key in keys:
                    value = h.get(key)
                    if value is not None and float(value) > 0:
                        return float(value)
        except Exception:
            pass

        return current_price

    def vol_adjusted_weight(self, closes, ticker):
        tier = self.tier_weights.get(ticker, 1.0)

        if len(closes) < 21:
            return tier

        returns = []

        for i in range(-20, 0):
            previous_close = closes[i - 1]
            if previous_close > 0:
                returns.append(closes[i] / previous_close - 1.0)

        if not returns:
            return tier

        mean_return = sum(returns) / float(len(returns))
        variance = sum((r - mean_return) ** 2 for r in returns) / float(len(returns))
        volatility = math.sqrt(variance)

        if volatility <= 0:
            return tier

        return tier * min(1.0, 0.022 / volatility)

    def run(self, data):
        allocation = {}

        for ticker in self.tickers:
            allocation[ticker] = 0.0

        ohlcv = data.get("ohlcv", {})
        holdings = data.get("holdings", {})

        if not ohlcv:
            return TargetAllocation(allocation)

        market_closes = self.get_series(ohlcv, self.market_filter, "close")

        if len(market_closes) < self.market_sma_slow:
            return TargetAllocation(allocation)

        spy_price = market_closes[-1]
        spy_sma50 = self.sma(market_closes, self.market_sma_fast)
        spy_sma200 = self.sma(market_closes, self.market_sma_slow)

        if spy_sma50 is None or spy_sma200 is None:
            return TargetAllocation(allocation)

        if spy_price < spy_sma200:
            return TargetAllocation(allocation)

        if spy_price > spy_sma50 and spy_sma50 > spy_sma200:
            max_invested = self.bull_max_invested
        else:
            max_invested = self.caution_max_invested

        candidates = []

        for ticker in self.universe:
            closes = self.get_series(ohlcv, ticker, "close")

            if len(closes) < self.stock_sma_slow + 5:
                continue

            price = closes[-1]
            sma50 = self.sma(closes, self.stock_sma_fast)
            sma150 = self.sma(closes, self.stock_sma_slow)
            stock_rsi = self.rsi(closes, self.rsi_period)
            score = self.momentum_score(closes)

            if sma50 is None:
                continue
            if sma150 is None:
                continue
            if stock_rsi is None:
                continue
            if score is None:
                continue

            held = self.is_held(holdings, ticker)

            if held:
                entry_price = self.get_entry_price(holdings, ticker, price)

                if price >= entry_price * (1.0 + self.profit_target_pct):
                    continue

                if price < sma50:
                    continue

                if price < sma150:
                    continue

                if stock_rsi >= self.rsi_exit:
                    continue

            else:
                if price < sma50:
                    continue

                if price < sma150:
                    continue

                if sma50 < sma150:
                    continue

                if stock_rsi < self.rsi_min:
                    continue

                if stock_rsi > self.rsi_max:
                    continue

            candidates.append({
                "ticker": ticker,
                "score": score,
                "closes": closes
            })

        candidates.sort(key=lambda item: item["score"], reverse=True)

        selected = candidates[:self.max_positions]

        if not selected:
            return TargetAllocation(allocation)

        raw_total = 0.0

        for item in selected:
            raw_total += self.vol_adjusted_weight(item["closes"], item["ticker"])

        if raw_total <= 0:
            return TargetAllocation(allocation)

        preliminary = {}

        for item in selected:
            ticker = item["ticker"]
            raw_weight = self.vol_adjusted_weight(item["closes"], ticker)
            weight = max_invested * raw_weight / raw_total
            weight = min(weight, self.max_weight)

            if weight >= self.min_weight:
                preliminary[ticker] = weight

        total_preliminary = sum(preliminary.values())

        if total_preliminary <= 0:
            return TargetAllocation(allocation)

        scale = min(max_invested / total_preliminary, 1.0)

        for ticker in preliminary:
            final_weight = preliminary[ticker] * scale
            if final_weight >= self.min_weight:
                allocation[ticker] = round(final_weight, 4)

        return TargetAllocation(allocation)