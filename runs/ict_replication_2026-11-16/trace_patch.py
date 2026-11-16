"""Diagnostic only (not part of the engine): writes mentorship/strategy_traced.py, a copy of strategy.py where every
silent `continue` of the day loop and every `return None` of _scan_core records (day, minute, session, side, label) for
the days in TRACE_DAYS.  Labels are D<line> / S<line> of the ORIGINAL strategy.py, so each one can be read in the source.
why_miss.py swaps the module in and prints, per ICT trade, the reasons seen inside his entry window."""
import re, sys
src = open("mentorship/strategy.py").read().split("\n")
def find(s, start=0):
    return next(k for k in range(start, len(src)) if src[k].startswith(s))
d0 = find("    for i in range(ctx.start, len(ctx.t)):")
s_loop = max(k for k in range(d0, len(src)) if src[k] == "        for sd in sides:" and k < find("def _no_draw", d0))
d1 = find("def _no_draw", d0)
c0, c1 = find("def _scan_core("), find("def _vi_alive(")
out = []
for k, ln in enumerate(src):
    n = k + 1
    m = re.match(r"^(\s+)(continue|return None|return order)\b", ln)
    if m and d0 < k < d1 and m.group(2) == "continue":
        out.append(f'{m.group(1)}_tr(ctx, i, locals(), "D{n}", {1 if k > s_loop else 0})')
    elif m and c0 < k < c1 and m.group(2) != "continue":
        out.append(f'{m.group(1)}_tr(ctx, i, locals(), "S{n}", 1)')
    out.append(ln)
    if k == d0:
        out.append("        _CUR[:] = [str(ctx.day), int(ctx.t[i]), None, 0]")
    if d0 < k < d1 and ln == "        ctx.cur_session = session":
        out.append("        _CUR[2] = session")
    if k == s_loop:
        out.append("            _CUR[3] = sd.sign")
    if ln.startswith("def _f(key):"):
        out.append("    _trf(key)")
out.append('''

TRACE, TRACE_DAYS, _CUR = [], set(), [None, None, None, 0]


def _tr(ctx, i, loc, label, side):
    d = str(ctx.day)
    if d not in TRACE_DAYS:
        return
    sd = loc.get("sd") if side else None
    _CUR[:] = [d, int(ctx.t[i]), loc.get("session"), sd.sign if sd is not None else 0]
    TRACE.append((d, int(ctx.t[i]), loc.get("session"), sd.sign if sd is not None else 0, label))


def _trf(key):
    if _CUR[0] in TRACE_DAYS:
        TRACE.append((_CUR[0], _CUR[1], _CUR[2], _CUR[3], "f:" + key))
''')
open("mentorship/strategy_traced.py", "w").write("\n".join(out))
print("traced lines:", sum(1 for x in out if "_tr(ctx, i, locals()" in x))
