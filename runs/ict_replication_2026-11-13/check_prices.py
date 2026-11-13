import pandas as pd, re, sys
D=(sys.argv[1] if len(sys.argv)>1 else 'data/mentorship')+'/'
RAW={}
def raw(s):
    if s not in RAW:
        m=pd.read_parquet(D+f'{s}_1min_dbmeta.parquet'); r=pd.read_parquet(D+f'{s}_1min_dbraw.parquet')
        RAW[s]=r.join(m[['adj','instrument_id']])
    return RAW[s]
def win(s,d,a,b):
    r=raw(s); return r[(r.index>=pd.Timestamp(f'{d} {a}',tz='America/New_York'))&(r.index<=pd.Timestamp(f'{d} {b}',tz='America/New_York'))]
def touch(s,d,px,a='00:00',b='16:59'):
    w=win(s,d,a,b); h=w[(w.low<=px)&(w.high>=px)]
    return list(h.index.strftime('%H:%M'))
if __name__=='__main__':
    t=pd.read_csv(__file__.rsplit('/',1)[0]+'/ict_trades.csv',sep='|',dtype=str).fillna('')
    for _,x in t.iterrows():
        tt=re.findall(r'\d\d:\d\d',x.t_entry)
        if x.t_entry=='AM': tt=['09:30','12:00']
        if x.t_entry=='PM': tt=['12:00','16:00']
        a=(pd.Timestamp(tt[0])-pd.Timedelta(minutes=3)).strftime('%H:%M') if tt else '00:00'
        b=(pd.Timestamp(tt[-1])+pd.Timedelta(minutes=4)).strftime('%H:%M') if tt else '16:59'
        out=[]
        if x.entry:
            px=float(x.entry); h=touch(x.sym,x.date,px,a,b)
            w=win(x.sym,x.date,a,b)
            out.append(f"entry {px} in window {a}-{b}: {'YES '+h[0]+'..'+h[-1] if h else 'NO (range %.2f-%.2f)'%(w.low.min(),w.high.max())}")
            if not h:
                h2=touch(x.sym,x.date,px); out.append('touched that day at '+(h2[0]+'..'+h2[-1]+f' n={len(h2)}' if h2 else 'never'))
        for e in x.exits.split(';'):
            m=re.match(r'\s*([\d.]+)(?:@(\d\d:\d\d))?',e)
            if m and m.group(2):
                px=float(m.group(1)); tm=m.group(2)
                a2=(pd.Timestamp(tm)-pd.Timedelta(minutes=3)).strftime('%H:%M'); b2=(pd.Timestamp(tm)+pd.Timedelta(minutes=3)).strftime('%H:%M')
                h=touch(x.sym,x.date,px,a2,b2); out.append(f"exit {px}@{tm}: {'ok' if h else 'NO'}")
        print(x.id,x.date,x.sym,' | '.join(out))
