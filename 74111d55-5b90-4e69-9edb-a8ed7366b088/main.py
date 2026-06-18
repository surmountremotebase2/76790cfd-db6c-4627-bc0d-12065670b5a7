#from surmount.base_class import Strategy, TargetAllocation
from surmount.logging import log
import math


class TradingStrategy(Strategy):
    def __init__(self):
        self.safe_asset = "BIL"
        self.market_filter = "SPY"
        self.vix_ticker = "VIX"

        # Stocks only. ETFs are data proxies, not portfolio candidates.
        self.universe = [
            "NVDA", "AVGO", "AMD", "TSM", "ASML", "MU", "ARM",
            "VRT", "ANET", "ETN", "PWR", "GEV",
            "GE", "HWM", "RTX", "TDG", "HEI",
            "MSFT", "META", "GOOGL", "AMZN", "PLTR", "PANW", "CRWD",
            "HOOD", "COIN"
        ]

        self.sector_etfs = {
            "SEMI": "SMH",
            "TECH": "QQQ",
            "INDUSTRIAL": "XLI",
            "AEROSPACE": "ITA",
            "INFRASTRUCTURE": "PAVE",
            "FINTECH": "ARKF"
        }

        self.sector = {
            "NVDA": "SEMI", "AVGO": "SEMI", "AMD": "SEMI", "TSM": "SEMI",
            "ASML": "SEMI", "MU": "SEMI", "ARM": "SEMI",

            "MSFT": "TECH", "META": "TECH", "GOOGL": "TECH", "AMZN": "TECH",
            "PLTR": "TECH", "PANW": "TECH", "CRWD": "TECH",

            "HOOD": "FINTECH", "COIN": "FINTECH",

            "VRT": "INFRASTRUCTURE", "ANET": "INFRASTRUCTURE",
            "ETN": "INFRASTRUCTURE", "PWR": "INFRASTRUCTURE",
            "GEV": "INFRASTRUCTURE",

            "GE": "AEROSPACE", "HWM": "AEROSPACE", "RTX": "AEROSPACE",
            "TDG": "AEROSPACE", "HEI": "AEROSPACE"
        }

        self.tickers = list(set(
            self.universe
            + list(self.sector_etfs.values())
            + [self.safe_asset, self.market_filter, self.vix_ticker]
        ))

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

        self.atr_period = 14
        self.max_noise_ratio = 0.08
        self.min_volume_ratio = 0.75

        self.max_positions = 6
        self.bull_max_invested = 0.85
        self.caution_max_invested = 0.45

        self.top_sector_count = 3
        self.max_names_per_sector = 2

        self.min_weight = 0.04
        self.max_weight = 0.15

        self.dd_reduce_level = 0.12
        self.dd_cash_level = 0.18

        self.profit_target_pct = 0.50

        self.tier_weights = {
            "NVDA": 1.35, "AVGO": 1.45, "AMD": 1.10, "TSM": 1.15,
            "ASML": 1.10, "MU": 0.90, "ARM": 0.75,

            "VRT": 1.25, "ANET": 1.25, "ETN": 1.15,
            "PWR": 1.15, "GEV": 1.10,

            "GE": 1.10, "HWM": 1.20, "RTX": 1.00,
            "TDG": 1.05, "HEI": 1.05,

            "MSFT": 1.15, "META": 1.15, "GOOGL": 1.05,
            "AMZN": 1.05, "PLTR": 0.75, "PANW": 1.10,
            "CRWD": 1.00,

            "HOOD": 0.65, "COIN": 0.65
        }

    @property
    def interval(self):
        return "1day"

    @property
    def assets(self):
        return self.tickers

    def is_held(self, holdings, ticker):
        h = holdings.get(ticker)

        if not h:
            return False

        try:
            if isinstance(h, dict):
                qty = h.get("quantity", h.get("shares", h.get("weight", 0)))
                return float(qty or 0) > 0

            return float(h) > 0

        except Exception:
            return False

    def get_series(self, ohlcv, ticker, field):
        values = []

        if not ohlcv:
            return values

        if isinstance(ohlcv, dict):
            if ticker in ohlcv:
                for bar in ohlcv[ticker]:
                    try:
                        if field in bar and bar[field] is not None:
                            values.append(float(bar[field]))
                    except Exception:
                        continue

            elif field in ohlcv and ticker in ohlcv[field]:
                for val in ohlcv[field][ticker]:
                    try:
                        if val is not None:
                            values.append(float(val))
                    except Exception:
                        continue

        elif isinstance(ohlcv, list):
            for bar in ohlcv:
                try:
                    if ticker in bar and isinstance(bar[ticker], dict) and field in bar[ticker]:
                        values.append(float(bar[ticker][field]))

                    elif field in bar and isinstance(bar[field], dict) and ticker in bar[field]:
                        values.append(float(bar[field][ticker]))

                except Exception:
                    continue

        return values

    def sma(self, values, period):
        if len(values) < period:
            return None

        return sum(values[-period:]) / period

    def rsi(self, values, period):
        if len(values) < period + 1:
            return None

        gains = []
        losses = []

        for i in range(-period, 0):
            change = values[i] - values[i - 1]
            gains.append(change if change >= 0 else 0)
            losses.append(abs(change) if change < 0 else 0)

        avg_gain = sum(gains) / period
        avg_loss = sum(losses) / period

        if avg_loss == 0:
            return 100

        return 100 - (100 / (1 + (avg_gain / avg_loss)))

    def atr(self, ohlcv, ticker, period):
        highs = self.get_series(ohlcv, ticker, "high")
        lows = self.get_series(ohlcv, ticker, "low")
        closes = self.get_series(ohlcv, ticker, "close")

        if len(closes) < period + 1:
            return None

        if len(highs) < period or len(lows) < period:
            return None

        trs = []

        for i in range(-period, 0):
            tr = max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i - 1]),
                abs(lows[i] - closes[i - 1])
            )
            trs.append(tr)

        return sum(trs) / period

    def get_entry_price(self, holdings, ticker, current_price):
        h = holdings.get(ticker, {})

        if isinstance(h, dict):
            for key in ["avg_price", "average_price", "cost_basis", "average_cost", "avg_cost"]:
                try:
                    if key in h and float(h[key]) > 0:
                        return float(h[key])
                except Exception:
                    pass

        return current_price

    def momentum_score(self, closes):
        if len(closes) < self.momentum_3m:
            return None

        m3 = (closes[-1] / closes[-self.momentum_3m]) - 1
        m1 = (closes[-1] / closes[-self.momentum_1m]) - 1
        w2 = (closes[-1] / closes[-self.momentum_2w]) - 1

        return (m3 * 0.50) + (m1 * 0.30) + (w2 * 0.20)

    def sector_momentum_score(self, closes):
        score = self.momentum_score(closes)

        if score is None:
            return None

        sma50 = self.sma(closes, 50)
        sma150 = self.sma(closes, 150)

        if sma50 and sma150 and closes[-1] > sma50 and sma50 > sma150:
            score += 0.05

        return score

    def get_top_sectors(self, ohlcv):
        scores = []

        for sector_name, etf in self.sector_etfs.items():
            closes = self.get_series(ohlcv, etf, "close")
            score = self.sector_momentum_score(closes)

            if score is not None:
                scores.append((sector_name, score))

        scores.sort(key=lambda x: x[1], reverse=True)

        top = [s[0] for s in scores[:self.top_sector_count]]
        log(f"Top sectors: {top}")

        return top

    def vix_exposure_multiplier(self, ohlcv):
        vix_closes = self.get_series(ohlcv, self.vix_ticker, "close")

        if not vix_closes:
            return 1.0

        vix = vix_closes[-1]

        if vix < 20:
            return 1.0

        if vix < 30:
            log(f"VIX elevated: {vix:.1f}. Exposure cut to 70%.")
            return 0.70

        log(f"VIX high: {vix:.1f}. Exposure cut to 35%.")
        return 0.35

    def market_drawdown_status(self, ohlcv):
        closes = self.get_series(ohlcv, self.market_filter, "close")

        if len(closes) < 120:
            return "NORMAL"

        peak = max(closes[-120:])
        current = closes[-1]

        if peak <= 0:
            return "NORMAL"

        dd = (peak - current) / peak

        if dd >= self.dd_cash_level:
            log(f"SPY drawdown brake: {dd:.1%}. Full BIL.")
            return "CASH"

        if dd >= self.dd_reduce_level:
            log(f"SPY drawdown reduce mode: {dd:.1%}.")
            return "REDUCED"

        return "NORMAL"

    def vol_adjusted_weight(self, closes, ticker):
        tier = self.tier_weights.get(ticker, 1.0)

        if len(closes) < 21:
            return tier

        returns = []

        for i in range(-20, 0):
            if closes[i - 1] > 0:
                returns.append((closes[i] / closes[i - 1]) - 1)

        if not returns:
            return tier

        mean_ret = sum(returns) / len(returns)
        variance = sum((r - mean_ret) ** 2 for r in returns) / len(returns)
        vol = math.sqrt(variance)

        if vol <= 0:
            return tier

        return tier * min(1.0, 0.022 / vol)

    def run(self, data):
        allocation = {ticker: 0.0 for ticker in self.tickers}

        ohlcv = data.get("ohlcv")
        holdings = data.get("holdings", {})

        if not ohlcv:
            allocation[self.safe_asset] = 1.0
            return TargetAllocation(allocation)

        drawdown_status = self.market_drawdown_status(ohlcv)

        if drawdown_status == "CASH":
            allocation[self.safe_asset] = 1.0
            return TargetAllocation(allocation)

        market_closes = self.get_series(ohlcv, self.market_filter, "close")

        if len(market_closes) < self.market_sma_slow:
            allocation[self.safe_asset] = 1.0
            return TargetAllocation(allocation)

        m_sma_fast = self.sma(market_closes, self.market_sma_fast)
        m_sma_slow = self.sma(market_closes, self.market_sma_slow)
        current_market_price = market_closes[-1]

        if current_market_price > m_sma_fast and m_sma_fast > m_sma_slow:
            max_invested = self.bull_max_invested
        elif current_market_price < m_sma_slow:
            allocation[self.safe_asset] = 1.0
            return TargetAllocation(allocation)
        else:
            max_invested = self.caution_max_invested

        if drawdown_status == "REDUCED":
            max_invested = min(max_invested, 0.42)

        max_invested = min(max_invested * self.vix_exposure_multiplier(ohlcv), 1.0)

        top_sectors = self.get_top_sectors(ohlcv)
        candidates = []

        for ticker in self.universe:
            closes = self.get_series(ohlcv, ticker, "close")

            if len(closes) < max(self.stock_sma_slow, self.momentum_3m) + 5:
                continue

            current_price = closes[-1]
            is_asset_held = self.is_held(holdings, ticker)
            ticker_sector = self.sector.get(ticker, "OTHER")

            if not is_asset_held and ticker_sector not in top_sectors:
                continue

            s_sma_fast = self.sma(closes, self.stock_sma_fast)
            s_sma_slow = self.sma(closes, self.stock_sma_slow)
            stock_rsi = self.rsi(closes, self.rsi_period)
            atr_val = self.atr(ohlcv, ticker, self.atr_period)

            skip_due_to_exit = False

            if is_asset_held:
                entry_p = self.get_entry_price(holdings, ticker, current_price)

                if entry_p > 0 and current_price >= entry_p * (1.0 + self.profit_target_pct):
                    skip_due_to_exit = True
                elif s_sma_fast and current_price < s_sma_fast:
                    skip_due_to_exit = True
                elif s_sma_slow and current_price < s_sma_slow:
                    skip_due_to_exit = True
                elif stock_rsi and stock_rsi >= self.rsi_exit:
                    skip_due_to_exit = True
                elif atr_val and s_sma_fast and current_price <= s_sma_fast - (1.5 * atr_val):
                    skip_due_to_exit = True

            if skip_due_to_exit:
                allocation[ticker] = 0.0
                continue

            if not is_asset_held:
                if not s_sma_fast or not s_sma_slow:
                    continue

                if current_price < s_sma_fast or current_price < s_sma_slow or s_sma_fast < s_sma_slow:
                    continue

                if not stock_rsi or not (self.rsi_min <= stock_rsi <= self.rsi_max):
                    continue

                if not atr_val or current_price <= 0:
                    continue

                if (atr_val / current_price) > self.max_noise_ratio:
                    continue

                vols = self.get_series(ohlcv, ticker, "volume")

                if len(vols) >= 20:
                    avg_vol = sum(vols[-20:]) / 20

                    if vols[-1] < avg_vol * self.min_volume_ratio:
                        continue

            score = self.momentum_score(closes)

            if score is not None:
                candidates.append({
                    "ticker": ticker,
                    "score": score,
                    "closes": closes,
                    "is_held": is_asset_held
                })

        selected = []
        selected_tickers = set()
        sector_counts = {}

        # Pass 1: Keep existing positions, explicitly checking sector caps to prevent overexposure
        held_candidates = [item for item in candidates if item["is_held"]]
        held_candidates.sort(key=lambda x: x["score"], reverse=True)

        for item in held_candidates:
            if len(selected) >= self.max_positions:
                break

            t = item["ticker"]
            sect = self.sector.get(t, "OTHER")

            # SAFETY LOCK: Trim legacy names if they drift beyond sector limits
            if sector_counts.get(sect, 0) >= self.max_names_per_sector:
                log(f"Trimming weaker held position {t} to enforce sector concentration limits.")
                continue

            selected.append(item)
            selected_tickers.add(t)
            sector_counts[sect] = sector_counts.get(sect, 0) + 1

        # Pass 2: Fill remaining portfolio slots with top new candidates
        candidates.sort(key=lambda x: x["score"], reverse=True)

        for item in candidates:
            if len(selected) >= self.max_positions:
                break

            t = item["ticker"]

            if t in selected_tickers:
                continue

            sect = self.sector.get(t, "OTHER")

            if sector_counts.get(sect, 0) >= self.max_names_per_sector:
                continue

            selected.append(item)
            selected_tickers.add(t)
            sector_counts[sect] = sector_counts.get(sect, 0) + 1

        if not selected:
            allocation[self.safe_asset] = 1.0
            return TargetAllocation(allocation)

        total_raw = sum(
            self.vol_adjusted_weight(item["closes"], item["ticker"])
            for item in selected
        )

        if total_raw <= 0:
            allocation[self.safe_asset] = 1.0
            return TargetAllocation(allocation)

        preliminary = {}

        for item in selected:
            t = item["ticker"]
            raw = self.vol_adjusted_weight(item["closes"], t)
            w = max_invested * (raw / total_raw)
            w = min(w, self.max_weight)

            if w >= self.min_weight:
                preliminary[t] = w

        total_prelim = sum(preliminary.values())

        if total_prelim <= 0:
            allocation[self.safe_asset] = 1.0
            return TargetAllocation(allocation)

        scale = min(max_invested / total_prelim, 1.0)
        total_assigned = 0.0

        for t, w in preliminary.items():
            final_w = round(w * scale, 4)

            if final_w >= self.min_weight:
                allocation[t] = final_w
                total_assigned += final_w

        total_assigned = round(total_assigned, 4)

        if total_assigned > max_invested:
            remainder = round(total_assigned - max_invested, 4)
            held_equities = [t for t in self.universe if allocation[t] > 0]

            if remainder > 0 and held_equities:
                largest_ticker = max(held_equities, key=lambda x: allocation[x])
                allocation[largest_ticker] = round(allocation[largest_ticker] - remainder, 4)
                total_assigned = round(total_assigned - remainder, 4)

        allocation[self.safe_asset] = round(max(0.0, 1.0 - total_assigned), 4)

        return TargetAllocation(allocation)
text.txt