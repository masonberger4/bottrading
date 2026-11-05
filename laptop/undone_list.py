import os, sys
os.environ["MENTORSHIP_SRC"]="databento"
from mentorship import study as S
d=sys.argv[1]; allv=list(S.DECISIONS)
prio=[x for x in allv if x in("current","defaults") or x.startswith(("CG","TT-","NEWS-","DXY"))]
first=prio+[v for v in allv[:len(allv)//2] if v not in prio]
done={f[8:-4] for f in os.listdir(d) if f.startswith("5m_2021_")}
open(sys.argv[2],"w").write("\n".join(v for v in first if v not in done)+"\n")
