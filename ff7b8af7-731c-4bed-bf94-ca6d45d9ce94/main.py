from surmount.base_class import Strategy, TargetAllocation
import math

class TradingStrategy(Strategy):
    def __init__(self):
        self.safe_asset = None
        self.market_filter = "SPY"
        self.vix_ticker = "VIX"

        self.universe = [
            "NVDA", "AVGO", "AMD", "TSM", "ASML", "MU",
            "ANET", "ETN", "PWR",
            "GE", "HWM", "RTX",
            "MSFT", "META", "GOOGL", "AMZN", "PANW", "CRWD"
        ]

        self.sector = {
            "NVDA": "SEMI", "AVGO": "SEMI", "AMD": "SEMI", "TSM": "SEMI", "ASML": "SEMI", "MU": "SEMI",
            "MSFT": "TECH", "META": "TECH", "GOOGL": "TECH", "AMZN": "TECH", "PANW": "TECH", "CRWD": "TECH",
            "ANET": "INFRASTRUCTURE", "ETN": "INFRASTRUCTURE", "PWR": "INFRASTRUCTURE",
            "GE": "AEROSPACE", "HWM": "AEROSPACE", "RTX": "AEROSPACE"
        }

        self.tickers = list(set(self.universe + [self.market_filter, self.vix_ticker]))

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
            "NVDA": 1.35, "AVGO": 1.45, "AMD": 1.10, "TSM": 1.15, "ASML": 1.10, "MU": 0.90,
            "ANET": 1.25, "ETN": 1.15, "PWR": 1.15,
            "GE": 1.10, "HWM": 1.20, "RTX": 1.00,
            "MSFT": 1.15, "META": 1.15, "GOOGL": 1.05, "AMZN": 1.05, "PANW": 1.10, "CRWD": 1.00
        }

    @property
    def interval(self):
        return "1day"

    @property
    def assets(self):
        return self.tickers

    def is_held(self, holdings, ticker):
        h = holdings.