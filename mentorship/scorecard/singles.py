"""Mase 2026-11-06: one video beats an engine default that no video supports. Every
"not scored" one-source rule in digest_map.csv becomes a DRAFT default (engine behaviour
= switch), except the rows listed in STATUS below. Writes singles.csv; defaults.py adds it
to DEFAULTS.md."""
import csv, os
H = os.path.dirname(os.path.abspath(__file__))
EXCLUDE = 'excluded'
STATUS = {  # (digest, num): (status, reason)
    ('te_charter', '2'): (EXCLUDE, 'clock question (MT4 server time), not a rule; check frames'),
    ('te_charter', '4'): (EXCLUDE, 'internal to one Charter FX model; engine does not run Charter models'),
    ('te_charter', '5'): (EXCLUDE, 'internal to the Charter models'),
    ('te_charter', '6'): (EXCLUDE, 'swing/position models only; engine is intraday'),
    ('te_charter', '7'): (EXCLUDE, 'single Charter model definition'),
    ('te_charter', '9'): (EXCLUDE, 'slide vs audio; needs the frames first'),
    ('m2024', '16'): (EXCLUDE, 'beginner risk rules; experienced version wins (Mase 2026-11-06)'),
    ('m2024', '19'): (EXCLUDE, 'Silver Bullet is settled off'),
    ('m2024', '30'): ('default', 'post-holiday: 2023 090 skip the AM only vs 2024 L21 skip the whole Tuesday; 1-1 tie, Mase 2026-11-08 picked AM only; whole day a switch'),
    ('m2025', '6'): ('agrees', '2023 and 2026 agree; nothing changes'),
    ('m2026smc', '17'): ('default', 'IOFED depth: partial short of CE (062, 063) vs 1 tick past candle 1 (024, 032); tie, Mase 2026-11-08 picked 1 tick past candle 1; short of CE a switch'),
    ('m2026smc', '19'): ('default, needs threshold', 'HRLR "candles sharing a range" needs a numeric threshold before it can be coded'),
    ('m2026smc', '83'): ('switch', 'nested ORGs: widest (019, Aug-Oct 2026) vs last three ORGs (BIAS-SOURCE C, Apr 2026); 1-1 tie, Mase 2026-11-08 picked last three ORGs graded; widest nested is a switch'),
    ('m2026smc', '101'): ('default, flagged', 'stop entry through the rejection block open (131); limit entries were never counted, so a count could reverse this'),
    ('m2026smc', '103'): (EXCLUDE, 'position sizing is outside the engine ($1k risk reporting)'),
}
rows = [r for r in csv.DictReader(open(os.path.join(H, 'digest_map.csv'), encoding='utf-8'))
        if 'not scored' in r['note'].lower()]
out = []
for r in rows:
    st, why = STATUS.get((r['digest'], r['num']), ('default', ''))
    note = r['note'].split(':', 1)[1].strip() if ':' in r['note'] else r['note']
    out.append(dict(digest=r['digest'], num=r['num'], status=st, rule=note, reason=why))
with open(os.path.join(H, 'singles.csv'), 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=list(out[0])); w.writeheader(); w.writerows(out)
if __name__ == '__main__':
    from collections import Counter
    print(len(out), Counter(o['status'] for o in out))
