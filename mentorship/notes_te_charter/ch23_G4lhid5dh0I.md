# ch23 ICT Charter Price Action Model 7 \ Sell-side Trade Plan + Algorithmic Theory (G4lhid5dh0I)
Trade plan ~2020 + lecture recorded 2022 / slides / 30 min. Captions only.
Source tier: Charter. 2023 wins on conflicts. FX units.

## Summary
Model 7 trade plan is the mirror of Model 6: IPDA 20/40/60-day dealing range (no Sundays), short premium FVGs or buy stops in stage-1/stage-2 redistribution of a MM sell model (target the discount PD array / original consolidation) or a MM buy model (target sell-side below old lows at terminus). 15m/5m premium FVG converging with <= +3 SD in London or NY; 5m order-flow entry drill or buy-stop raid; sell limit at convergence - 5 pips; TP 20/40, close 80% at 60; stop high + 20 pips. Lecture: sell-side runs are faster than buy-side; in a MM sell model's stage-2 distribution check whether it can be a crash and let a portion ride.

## Rules
- Preparation: note all medium and high impact events for the week; consider weekly profile from structure + calendar ~0:52-1:26
- IPDA dealing range: highest high / lowest low of last 20, 40 or 60 trading days, no Sundays ~1:26-1:58
- Next draw: which old low below; discount PD array in the direction of the weekly range bias, reached on a day with an economic event (volatility injection) ~1:58-2:40
- MM sell model: wait stage 1 or 2 redistribution, short, target terminus at the discount PD array; MM buy model: same, target the old low where the buy model starts ~2:40-3:48
- Trade planning: convergence of manipulation opposite your bias at a calendar volatility time; short premium FVGs or buy stops in stage 1/2 ~3:48-4:20
- Entry frame: 15m or 5m premium FVG converging with no more than +3 SD during London or NY open; scalping protocols allowed for less risk ~4:20-4:54
- Targets: MM buy model -> sell-side below old lows at terminus; MM sell model -> original consolidation ~4:54
- Execution: 5m institutional order flow entry drill in a retracement higher in London/NY kill zones, or a buy-stop raid ~4:54-5:30
- Orders: sell limit, all at the same price = SD/PD array convergence - 5 pips; TP1 20 pips, TP2 40 pips; at 60 pips close 80% ~5:30-5:57
- Stop = high + 20 pips; re-enter if stopped; day trades may need several attempts ~5:57-6:36
- 25/50/75 stop protocol: at 25% of objective reduce stop 25%, at 50% reduce 50%, at 75% stop at break-even ~6:36-7:11
- Position size = equity x risk% / stop pips; always round down; avoid standard lots ~7:11-9:33
- After a full-risk loss: halve risk until 50% of the loss is recovered; halve again on another loss; after 5 wins in a row halve risk ~9:33-10:38
- Sell-side low resistance runs are faster, more violent and larger than buy-side ~12:06-13:48
- In a MM sell model (bearish market) stage-2 distribution, check intermarket, macro and geopolitical context for a crash scenario; if so take only a small portion off and let the rest ride ~13:48-16:28, ~29:06-29:34
- MM buy model sell side = "controlled demolition" to a discount, not a crash ~19:35-21:01
- Gaps through stops cause slippage beyond the stop in crash moves ~21:31-22:30

## Trade examples
- Crude oil 2020 to -$40 as a parabolic stage-2 distribution that blew through a $11 target ~14:53-16:28

## Definitions
- Controlled demolition: decline to a discount PD array expected to reverse
- Volatility injection: economic calendar event used for the low resistance run

## Open questions
- "Let a runner ride in a crash regime" needs a regime flag: switch `crash_regime_runner` (default off)
- Entry offset 5 pips, stop 20 pips, TP 20/40/60: index mapping is our interpretation
