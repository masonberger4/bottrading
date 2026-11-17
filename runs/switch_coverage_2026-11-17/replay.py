"""Independent 1-minute replay of engine trades: limit fill after the arming bar, then stop vs +kR target (stop first on ties)."""
import pandas as pd, numpy as np, sys, glob, warnings
warnings.filterwarnings('ignore')
D='/mnt/project-files/mentorship/data/fixed_roll_2026-11-10/'
_b={}
def bars(sym):
    if sym not in _b:
        b=pd.read_parquet(D+f'{sym}_1min_db.parquet')
        if not isinstance(b.index,pd.DatetimeIndex):
            b=b.set_index(b.columns[0])
        b.index=pd.to_datetime(b.index,utc=True).tz_convert('America/New_York'); _b[sym]=b.sort_index()
    return _b[sym]
def replay(t,sym,tf=5):
    b=bars(sym); out=[]
    for r in t.itertuples():
        A=pd.Timestamp(r.armed).tz_convert('America/New_York') if pd.notna(r.armed) else None
        ET=pd.Timestamp(r.entry_time).tz_convert('America/New_York')
        if A is None: out.append({}); continue
        s=1 if r.side=='long' else -1
        a=float(r.adj) if pd.notna(r.adj) else 0.0; E,X=float(r.entry)+a,float(r.stop)+a; risk=s*(E-X)
        if risk<=0: out.append({}); continue
        end=ET.normalize()+pd.Timedelta(hours=16) if ET.hour<16 else ET+pd.Timedelta(hours=4)
        w=b.loc[A+pd.Timedelta(minutes=tf):end]
        if not len(w): out.append({}); continue
        lo,hi,op,cl=w.low.values,w.high.values,w.open.values,w.close.values
        touch=(lo<=E) if s>0 else (hi>=E)
        if not touch.any(): out.append(dict(filled=False)); continue
        k=int(np.argmax(touch))
        mkt=bool(s*(op[0]-E)<0)                    # limit already through the market at arming -> a real fill is at the open (better); E used here
        res={'filled':True,'fill_t':w.index[k],'marketable':mkt,'fill_lag_min':k,'risk_pts':risk}
        for kR in (1,2,3):
            T=E+s*kR*risk; o=None
            for j in range(k,len(w)):
                stop_hit=(lo[j]<=X) if s>0 else (hi[j]>=X)
                tgt_hit=(hi[j]>=T) if s>0 else (lo[j]<=T)
                if j==k:                           # fill minute: only count the target if price went there AFTER a fill; conservative: no target in the fill minute
                    tgt_hit=False
                if stop_hit: o=-1.0; break
                if tgt_hit: o=float(kR); break
            if o is None: o=s*(cl[-1]-E)/risk
            res[f'r{kR}']=o
        res['stop_in_fill_min']=bool((lo[k]<=X) if s>0 else (hi[k]>=X))
        out.append(res)
    return pd.concat([t.reset_index(drop=True),pd.DataFrame(out)],axis=1)
if __name__=='__main__':
    pat,sym=sys.argv[1],sys.argv[2]
    t=pd.concat([pd.read_csv(f) for f in sorted(glob.glob(pat))]); t=t[t.armed.notna()]
    r=replay(t,sym); f=r[r.filled==True]
    print(sym,'trades',len(t),'filled in replay',len(f),'marketable at arming',round(f.marketable.mean(),2),'stop in fill minute',round(f.stop_in_fill_min.mean(),2))
    for k in (1,2,3):
        x=f[f'r{k}']; print(f' {k}R: avg {x.mean():+.3f} t {x.mean()/x.std()*len(x)**.5:+.1f} target-first {(x>=k).mean():.0%}')
    print(' engine R avg',round(f.R.mean(),3),' by entry_kind:'); print(f.groupby('entry_kind')[['r1','r2','R']].agg(['count','mean']).round(2).to_string())
