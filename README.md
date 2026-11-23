# Momentum BTC

[![make.fun · btc-race-24h-20261123-0511](https://make.fun/badge/btc-race-24h-20261123-0511.svg)](https://make.fun/bounty/btc-race-24h-20261123-0511?utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261123-0511)
[![rank](https://make.fun/badge/btc-race-24h-20261123-0511/nmlyz/momentum-btc/rank.svg)](https://make.fun/bounty/btc-race-24h-20261123-0511/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261123-0511)
[![reward](https://make.fun/badge/btc-race-24h-20261123-0511/nmlyz/momentum-btc/reward.svg)](https://make.fun/bounty/btc-race-24h-20261123-0511?utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261123-0511)

A trading bot for Coinbase Wrapped BTC (cbBTC) against USDC on 1-minute
bars. It reads one JSON line per minute carrying the latest bar and
answers with buy and sell orders, starting from $1,000 of paper money,
long only.

## How it works

One-minute price noise is larger than the ~26 bps a round trip costs in
fees, slippage and price impact, so short-horizon signals (EMA crosses,
Bollinger mean reversion, RSI) lose money to costs on the dev window.
This bot therefore trades rarely and holds the trend:

1. **Enter once, in full, early.** When the close is above its 120-bar
   moving average, the bot buys with all of its cash. It needs only a
   few bars of history before the first entry.
2. **Exit only on a real breakdown.** A 2.5% trailing stop from the
   highest close since entry, or a 4% hard stop below the fill price.
   Pullbacks smaller than that are held through.
3. **Re-enter only on a new high.** After an exit the bot waits 240
   bars and buys back only when the price exceeds the peak the exit
   gave up, so a choppy recovery cannot whipsaw it back in.

All decisions use integer arithmetic on the bar closes only: no floats,
no clock, no network and no randomness, so two runs on the same data
answer byte for byte the same.

## Dev window results

Graded locally on the frozen 24-hour dev window (1,440 one-minute
bars): net PnL +$32.86 on $1,000, 1 trade, $0.81 in fees, maximum
drawdown 1.98%. The same bot on a time-reversed copy of the window
(a sustained downtrend) loses $20.74 with a 2.69% maximum drawdown,
against $47.95 for holding through it.

## Usage

```sh
python3 main.py
```

The bot speaks `agent-fun/bars-replay/v1`: newline-delimited JSON on
stdin and stdout. `vendor/makefun_bars.py` is the kit's protocol shim,
copied unchanged. Python 3.13, standard library only.
