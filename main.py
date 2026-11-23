"""Momentum hold bot for cbBTC (CBBTC/USDC) on 1-minute bars.

Strategy, found by testing against the frozen dev window and against
reversed and shuffled copies of it:

* Buy once, in full, early, while the price holds above its 120-bar
  moving average, and otherwise stay in cash. One-minute noise is
  larger than the ~26 bps a round trip costs, so every short-horizon
  signal tested (EMA crosses, Bollinger mean reversion, RSI) lost
  money to fees on the dev window; holding the trend is what pays.
* Exit only on a real breakdown: a 2.5% trailing stop from the
  highest close since entry, or a 4% hard stop below the fill price.
* After an exit, wait 240 bars and re-enter only on a new high above
  the peak the exit gave up, so a choppy recovery cannot whipsaw the
  bot back in.

All decisions use integer arithmetic on the bar closes only: no
floats, no clock, no network, no randomness, so two runs on the same
data answer byte for byte the same.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor"))

import makefun_bars

SYMBOL = "CBBTC"
# Trend filter: price above the mean of the last SMA_BARS closes.
SMA_BARS = 120
# Earliest batch that may trade (a few bars of history first).
ENTER_MIN_BARS = 10
# Trailing stop: sell when the close falls below 97.5% of the peak
# close since entry (2.5%).
TRAIL_NUM = 975
TRAIL_DEN = 1000
# Hard stop: sell when the close falls below 96% of the fill price.
STOP_NUM = 96
STOP_DEN = 100
# Bars to wait after an exit before a re-entry may be considered.
COOLDOWN_BARS = 240
# Never let the slippage guard reject an order on a gap: the trailing
# and hard stops already bound what a fill may cost.
MAX_SLIPPAGE_BPS = 10_000


class Bot:
    def __init__(self):
        # Closes as seen, one per batch (the latest close repeats when
        # a batch carries no bar for the symbol).
        self.closes = []
        # Running sum of the last SMA_BARS closes, for the exact
        # integer moving average.
        self.sma_sum = 0
        # Fill price of the open position (0 when flat), and the
        # highest close since the fill.
        self.entry_price = 0
        self.peak = 0
        # Seq of the last exit decision, and the peak it gave up.
        self.last_exit_seq = -10 ** 9
        self.last_peak = 0
        self.entered_once = False

    def on_batch(self, state, batch):
        close = state.close(SYMBOL)
        if close is None:
            return []
        close = int(close)
        self.closes.append(close)
        self.sma_sum += close
        if len(self.closes) > SMA_BARS:
            self.sma_sum -= self.closes[-SMA_BARS - 1]

        # Learn the fill price of a buy that landed on this batch.
        for fill in batch.get("fills", []):
            if (
                fill.get("symbol") == SYMBOL
                and fill.get("side") == "buy"
                and fill.get("status") == "filled"
            ):
                self.entry_price = int(fill["price"])
                self.peak = close
                self.entered_once = True

        holding = state.positions.get(SYMBOL)
        if holding is not None and holding.qty > 0:
            if self.entry_price == 0 and holding.cost > 0:
                # Fill missed: recover the entry price from the
                # position's cost (spend) and quantity, exactly as the
                # fill priced it: price = spend * 10^13 / (qty * 10^6).
                self.entry_price = (
                    holding.cost * 10**13 // (holding.qty * 10**6)
                )
            if close > self.peak:
                self.peak = close
            if self.entry_price > 0:
                if close * TRAIL_DEN < self.peak * TRAIL_NUM:
                    return self._sell(state)
                if close * STOP_DEN < self.entry_price * STOP_NUM:
                    return self._sell(state)
            return []

        # Flat: reset the entry markers and look for a new entry.
        self.entry_price = 0
        self.peak = 0
        if state.warming_up:
            return []
        if state.seq < ENTER_MIN_BARS:
            return []
        if state.seq - self.last_exit_seq < COOLDOWN_BARS:
            return []
        n = len(self.closes) if len(self.closes) < SMA_BARS else SMA_BARS
        # close above the moving average: close > sma_sum / n.
        if close * n <= self.sma_sum:
            return []
        # After an exit, re-enter only on a new high above the peak
        # the exit gave up.
        if self.entered_once and close <= self.last_peak:
            return []
        room = state.weight_room(SYMBOL)
        notional = state.cash if state.cash < room else room
        if notional < int(state.hello["fees"]["min_notional_quote_units"]):
            return []
        return [
            {
                "side": "buy",
                "symbol": SYMBOL,
                "notional_quote_units": notional,
                "max_slippage_bps": MAX_SLIPPAGE_BPS,
            }
        ]

    def _sell(self, state):
        holding = state.positions.get(SYMBOL)
        if holding is None or holding.qty <= 0:
            return []
        self.last_exit_seq = state.seq
        self.last_peak = self.peak
        return [
            {
                "side": "sell",
                "symbol": SYMBOL,
                "qty": holding.qty,
                "max_slippage_bps": MAX_SLIPPAGE_BPS,
            }
        ]


makefun_bars.run(Bot().on_batch)
