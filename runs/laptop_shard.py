import os
os.environ["MENTORSHIP_SRC"] = "databento"
from mentorship import study as S
if __name__ == "__main__":
    allv = list(S.DECISIONS)
    prio = [x for x in allv if x in ("current", "defaults") or x.startswith(("CG", "TT-", "NEWS-", "DXY"))]
    first_half = allv[: len(allv) // 2]
    variants = prio + [v for v in first_half if v not in prio]
    print(len(prio), len(variants), flush=True)
    S.main_decisions(out="runs/mentorship/shard_laptop", workers=4, tfs=(5,), variants=variants, tag="dec")
