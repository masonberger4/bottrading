# cc06_002 ICT Mentorship Core Content - Month 06 - Elements To Successful Swing Trading (Xs1i0aIeTME)
February 2017, swing trading lesson 2 (~0:11) / forex framing (EURUSD, USDCHF, USDX; gold and soybeans as allocation examples) / no price charts, slides only / 22m. Theory lesson plus a "mock trading plan" homework; the actual swing model and its two setups are promised for lesson 3 (~4:05, ~19:27).

## Summary
A checklist of hallmarks for a valid swing trade (HTF trend, clear HTF order flow, rates, COT, obvious opposing PD array, seasonals, intermarket), plus confirmation tools: SMT/relative strength vs the dollar index and "bank accumulation" (down-close candles hold as support in an uptrend). Insists on static, rule-based filtering, a portfolio risk cap, and a minimum 3:1 reward-to-risk. No entry trigger yet.

## Rules
- Hallmarks checklist (more is better; not all are required): 1) obvious trend on HTF charts or price has left a consolidation, 2) HTF institutional order flow clear, 3) interest-rate market supports the trade (rising/falling yields; yield divergence = shift coming), 4) COT confirms (optional, enhances probability), 5) opposing PD array obvious on monthly/weekly/daily, 6) seasonal tendency (optional), 7) supporting intermarket analysis ~0:24-1:52, ~2:09-2:28 [chart] [new]
- "Opposing PDA" = the objective: a clearly visible monthly/weekly/daily PD array on the other side of price to trade toward ~1:28-1:40 [chart] [new] (our reading of "opposing")
- SMT confirmation for swing entries: buy EURUSD on a lower low while USDX makes a lower high; short USDCHF on a lower high while USDX makes a higher high ~4:08-4:47 [chart] [new]. For indices this maps to ES vs NQ divergence (already used intraday, Ep 03).
- Bank accumulation test (uptrend): each down-close candle becomes support and price goes higher afterward; each broken swing high is followed by higher highs. Distribution (downtrend): up-close candles become resistance and broken swing lows lead to lower lows ~4:53-6:38 [new]
- Institutions buy only at a discount when the algorithm retraces; in a bull trend focus on down-close candles as entries, in a bear trend on up-close candles ~5:34-6:12 [new]
- Draw: monthly/weekly price levels not traded at in recent weeks/months (imbalances) are strong magnets. Price at equilibrium -> expect a move out of consolidation to an imbalance: up to a premium, or down to a deep discount ~7:38-8:15 [chart] [new]
- Prefer the cleanest price action; if you have to argue with yourself whether a level is an OB or liquidity, pass ~8:20-9:26 [chart] [new]
- Check that price respects institutional (round) levels: big figure 00, mid figure 50, and 20/80, 30/70 ~9:28-9:41 [chart] (FX pip levels; index analogue not given)
- Every trade passes the same static rule-based filter. Fail = no trade, no exceptions, even if ICT says he likes it ~9:50-10:32 [chart] [new]
- Pass = execute only if risk and equity management permit: a total open-risk cap applies. If the cap is used, either skip or close an existing trade for a better one (faster expected payout / higher probability) ~10:36-12:30 [chart] [new]
- Minimum 3:1 reward-to-risk; slide says this is net profitable at 34% accuracy. Aim for 5:1 where possible; the setups with the most movement potential give the best R:R ~12:34-13:33 [chart] [new]

## Trade examples
None. Allocation example only: long gold expecting 1240 vs soybeans expected to rise a full dollar; prefer the one likely to pay faster ("velocity of money") when risk is capped ~11:16-11:47.

## Definitions
- Institutional sponsorship: evidence from relative strength / SMT that big players back the move ~4:08-4:47
- Bank accumulation / distribution: down candles acting as support in an uptrend / up candles acting as resistance in a downtrend ~4:53-6:38
- Institutional levels: 00, 50, 20/80, 30/70 price levels ~9:30

## Seen only on the charts
- The slides fade bullets in one at a time; the last hallmark (supporting intermarket analysis) is faded on the 1:40 frame but spoken at ~1:49 [chart]
- Mock trading plan slide lists: what you look for first, what makes a valid setup, profit objectives, risk management, filter process; use one hindsight example ~16:20 [chart]

## Open questions
- No entry trigger, stop or target rule here; lesson 3 (the swing model, two setups) is needed before coding.
- Total-exposure cap is not given as a number (cc05_018 gives 1% per trade).
- "Institutional order flow clear on HTF" is not defined numerically; presumably the trending/left-consolidation test from cc06_001.
- Rates/COT/seasonals/intermarket are optional filters; for SPY/QQQ the bot could start without them and add later.
- 3:1 minimum: measured to the opposing PD array from the entry, with the stop from cc05_018's 40-day rule? That would reject many trades; not stated.
