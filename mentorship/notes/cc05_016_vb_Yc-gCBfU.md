# cc05_016 ICT Mentorship Core Content - Month 05 - Stop Entry Techniques For Long Term Traders (vb_Yc-gCBfU)
Lesson "7.1" of the 2017 mentorship. Market: USDJPY (forex) plus an unlabeled daily example. Timeframes: monthly/weekly for bias, daily for execution. Duration ~14 min. Examples from 2015-2016.

## Summary
Long-term entry technique: with the monthly/weekly pointing to a PD array beyond price, wait for a daily candle that closes against that direction, then place a stop order at that candle's open (buy stop above a down candle's open, sell stop below an up candle's open). Repeat on every new opposite candle; re-add partials taken off when price returns to the same open. This is the order-block entry expressed as a stop order. Swing/position timeframe; the logic maps to "enter on the return through the OB open" intraday.

## Rules
- Bias filter (long): monthly and/or weekly (preferably both) show a PD array above the daily price, e.g. a weekly bearish OB or a weekly/monthly FVG. ~0:24-0:33, ~1:49-2:16 [chart] [new]
- Setup candle: the daily must CLOSE as a down candle; it is not valid while it is still forming. ~0:36-0:48 [chart] [new]
- Entry: buy stop at the open of that down-close candle (buying strength as price trades back up through the open). ~0:50-1:26 [chart] [new]
- Shorts mirror: higher TF draws to a PD array below; the daily must close up; sell stop at the up candle's open. ~5:54-6:34 [new]
- No fill: cancel and move the stop to the open of the next down-close candle; repeat on each new down candle. Accept missed moves. ~3:08-3:41 [new]
- Each successive down-close candle can also be an add-on buy stop at its open. ~10:30-11:04 [chart]
- Partial profit and re-add: after a large move in favor, take some off; if price comes back to the same open, put that same size back on (keeps a similar average). ~4:37-5:13, ~7:19-7:48 [new]
- Stop: below the most recent daily swing low and a reference point to be given in lesson 8 (not specified here). ~10:14-10:28
- Keep doing this until price reaches the monthly/weekly premium PD array. The closer to that premium, the weaker the down candles; prefer buying at or below equilibrium of the monthly/weekly range. ~5:13-5:51 [new]
- Sizing: start with ~half normal size, build the rest on returns to the same candles (they become OBs later). ~13:17-13:45 [new]

## Trade examples
- Generic daily uptrend (frames ~9:40-11:00): small down candle near the high -> buy stop at its open; first one unfilled ("missed"); next down candle filled when the following candle opened below its open and traded up. Then three consecutive down candles each gave a buy-stop entry; the middle one may have filled. ~8:42-11:09 [chart; no prices on the slide]
- USDJPY 2015-2016 short: monthly old high from 2007 near 123.50 pierced in 2015, rejected, market structure broke (monthly frame ~11:20 shows the shaded 2015-16 sell-off from ~125 to ~99). ~11:16-11:44 [chart]
- Daily (frame ~12:20): red weekly/monthly premium box ~116-118 on the left; arrows mark five up candles in Feb-Mar 2016 (~113-114 area) whose opens (blue lines ~113.4, ~112.4, ~111.6) were sell-stop entries; each tripped soon after and price fell toward ~106-108. ~12:00-12:27 [chart]
- Daily (frame ~12:40): rally into a mitigation block ~111.3-111.7 in late Apr 2016; arrow on the up candle, sell stop at its open filled the next day; drop of several hundred pips, later over 1,000 pips. ~12:30-12:57 [chart]

## Definitions
- A down-close candle is a bullish OB; returning through its open is the long entry. Up-close candle = bearish OB, sell at its open. ~2:30-2:49, ~6:47-7:03 (consistent with Ep 03/08)
- "Mitigation block" used as a sell level in the Apr 2016 example but still not defined. ~12:31

## Seen only on the charts
- In the generic example the fill happens on a gap-down open below the down candle's open, then the candle trades up through it (stop triggered intraday on the next bar).
- USDJPY daily shading marks the whole bearish leg; the 5 up candles are at the premium of each small daily range, not random up candles.

## Open questions
- "Monthly and/or weekly": is one timeframe enough? Text says preferably both.
- Exact stop reference deferred to lesson 8.
- How far price can move without fill before the setup is abandoned (only "next down candle").
- Intraday adaptation (e.g. 5m down candle + 1h/4h draw) is our extrapolation; the lesson is daily-only.
- Forex-only: pip counts and USDJPY specifics.
