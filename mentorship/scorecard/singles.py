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
    ('m2025', '17'): ('switch', 'IOFED depth decided on SMC 17 (Mase 2026-11-08); 2025 L04/L05/L16/L54 back partial short of CE, still a switch; L46 OB+SIBI drill is a separate entry model'),
    ('m2025', '24'): (EXCLUDE, 'forex London close window; engine trades index futures'),
    ('m2025', '28'): ('agrees', 'compatible statements; nothing changes'),
    ('m2026smc', '17'): ('default', 'IOFED depth: partial short of CE (062, 063) vs 1 tick past candle 1 (024, 032); tie, Mase 2026-11-08 picked 1 tick past candle 1; short of CE a switch'),
    ('m2026smc', '19'): ('default, needs threshold', 'HRLR "candles sharing a range" needs a numeric threshold before it can be coded'),
    ('m2026smc', '83'): ('switch', 'nested ORGs: widest (019, Aug-Oct 2026) vs last three ORGs (BIAS-SOURCE C, Apr 2026); 1-1 tie, Mase 2026-11-08 picked last three ORGs graded; widest nested is a switch'),
    ('m2026smc', '101'): ('default, flagged', 'stop entry through the rejection block open (131); limit entries were never counted, so a count could reverse this'),
    ('m2026smc', '103'): (EXCLUDE, 'position sizing is outside the engine ($1k risk reporting)'),
    # 2026-11-08 recheck of the remaining 2024 singles: no opposing video; other playlists agree.
    ('m2024', '41'): ('default', 'also 2023 038, 101; CC cc10_019; SMC 036, 058'),
    ('m2024', '43'): ('default', 'light size agrees with SMC 022, 025, 028 (seek and destroy, do not over-leverage); Monday skip is L14 only'),
    ('m2024', '65'): ('default', 'also L35, L38, SMC 062 (prior day FPFVG as reference/draw)'),
    ('m2024', '83'): ('default', 'also L04, L06 (cluster of NDOGs sets the direction)'),
    ('m2024', '89'): ('default', 'also 2023 067, L49, SMC 007, 036, 037, 2025 L34, L78, TE te59'),
    ('m2024', '91'): ('default', 'also 2023 060 (shorts only above equilibrium of inception-to-terminus)'),
    ('m2024', '93'): ('default', 'also 2023 031, 042, 090; 2025 L80, L82; SMC 012 ("never 5 or 15")'),
    ('m2024', '97'): ('default', 'also 2023 100, L48, SMC 071 (no entry into the 10:00 release)'),
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
