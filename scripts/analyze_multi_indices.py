import json,csv,pathlib,datetime as dt,calendar,statistics,sqlite3,hashlib,bisect
ROOT=pathlib.Path(__file__).resolve().parents[1];OUT=ROOT/'data';RAW=OUT/'raw';ASOF='2026-10-11'
registry=json.loads((OUT/'index_registry.json').read_text())
for i in registry:
 if i['code']=='000688':i['release']='2020-07-23'
def addmonths(d,n):
 y=d.year+(d.month-1+n)//12;m=(d.month-1+n)%12+1
 return dt.date(y,m,min(d.day,calendar.monthrange(y,m)[1]))
def avg(a):return statistics.mean(a) if a else None
def metrics(es):
 done=[e for e in es if e['return'] is not None];rs=[e['return'] for e in done];wins=[r for r in rs if r>0];losses=[r for r in rs if r<0]
 return {'event_count':len(es),'completed_count':len(done),'pending_count':len(es)-len(done),'win_count':len(wins),'win_rate':len(wins)/len(rs) if rs else None,'mean_return':avg(rs),'median_return':statistics.median(rs) if rs else None,'best_return':max(rs) if rs else None,'worst_return':min(rs) if rs else None,'mean_max_drawdown':avg([e['max_drawdown'] for e in done]),'worst_max_drawdown':min([e['max_drawdown'] for e in done],default=None),'payoff_ratio':avg(wins)/abs(avg(losses)) if wins and losses else None,'overlap_count':sum(any(not p['exit_date'] or p['exit_date']>e['entry_date'] for p in es[:n]) for n,e in enumerate(es))}
assets=[];all_daily=[];all_monthly=[];all_cases=[];all_paths=[];matrix=[]
for asset in registry:
 ident=asset['id'];rows={};diffs=[];invalid=[];anchors={};overlap=0
 def ingest(rs,source):
  nonlocal_dummy=None
  global overlap
  for r in rs:
   if r['date']>ASOF:continue
   if r['date'] in rows:
    overlap+=1
    for k in ['open','high','low','close']:
     if rows[r['date']][k] is not None and abs(rows[r['date']][k]-r[k])>.011:diffs.append({'date':r['date'],'field':k,'first':rows[r['date']][k],'second':r[k]})
   if not (r['low']<=min(r['open'],r['close'])+.011 and r['high']>=max(r['open'],r['close'])-.011):
    invalid.append(dict(r,source=source))
    if r['date'] not in rows:rows[r['date']]=dict(r,source=source,high=None,low=None)
    continue
   rows[r['date']]=dict(r,source=source)
 for p in sorted(RAW.glob(ident+'_tencent_*.json')):
  x=json.loads(p.read_text()).get('data',{}).get(ident,{})
  ingest([{'date':r[0],'open':float(r[1]),'close':float(r[2]),'high':float(r[3]),'low':float(r[4])} for r in x.get('day',x.get('qfqday',[]))],'tencent')
 for name in [ident+'_sohu.json',asset['code']+'_sohu_retry.json','sohu2000small.json' if asset['code']=='932000' else 'none']:
  p=RAW/name
  if p.exists():
   x=json.loads(p.read_bytes().decode('utf-8',errors='replace'));rs=x[0].get('hq',[]) if isinstance(x,list) and x else []
   ingest([{'date':r[0],'open':float(r[1]),'close':float(r[2]),'low':float(r[5]),'high':float(r[6])} for r in rs],'sohu')
 # Supplemental provider responses, when a valid daily OHLC array is available.
 if asset['code']=='932000':
  for name in ['qqcsi2000.json','qqs_sh2000.json']:
   p=RAW/name
   if p.exists():
    ob=json.loads(p.read_text())
    for x in (ob.get('data',{}) or {}).values() if isinstance(ob.get('data'),dict) else []:
     rs=x.get('day',x.get('qfqday',[])) if isinstance(x,dict) else []
     ingest([{'date':r[0],'open':float(r[1]),'close':float(r[2]),'high':float(r[3]),'low':float(r[4])} for r in rs],'tencent')
  p=RAW/'csindex2000.json'
  if p.exists():
   x=json.loads(p.read_text())
   if isinstance(x,dict):
    rs=x.get('data',[])
    (OUT/'中证2000官方返回字段.json').write_text(json.dumps(rs[:2],ensure_ascii=False,indent=2))
 p=RAW/(ident+'_official.json')
 if p.exists():
  x=json.loads(p.read_text());rs=[r for r in (x.get('data',[]) or []) if str(r['tradeDate'])!='19901201']
  for r in rs:
   if r.get('close') and r['close']>0:
    date=str(r['tradeDate'])[:4]+'-'+str(r['tradeDate'])[4:6]+'-'+str(r['tradeDate'])[6:8]
    anchors[date[:7]]={'date':date,'close':float(r['close'])} if date>anchors.get(date[:7],{}).get('date','') else anchors[date[:7]]
  valid=[r for r in rs if all(r.get(k) is not None and r[k]>0 for k in ['open','close','high','low'])]
  ingest([{'date':str(r['tradeDate'])[:4]+'-'+str(r['tradeDate'])[4:6]+'-'+str(r['tradeDate'])[6:8],'open':float(r['open']),'close':float(r['close']),'high':float(r['high']),'low':float(r['low'])} for r in valid],'csindex_official')
 daily=sorted(rows.values(),key=lambda r:r['date']);dates=[r['date'] for r in daily]
 if not daily:
  assets.append(dict(asset,available=False,summary={},validation={'note':'公开接口尚未取得符合开盘买卖口径的日行情，暂不输出胜率。'},monthly=[],all_month_events=[],daily=[]));continue
 groups={}
 for r in daily:groups.setdefault(r['date'][:7],[]).append(r)
 monthly=[];prev=None;prevmonth=None
 for month,rs in groups.items():
  d=dt.date.fromisoformat(month+'-01');adjacent=prevmonth==addmonths(d,-1).strftime('%Y-%m')
  if not adjacent and addmonths(d,-1).strftime('%Y-%m') in anchors:
   prev=anchors[addmonths(d,-1).strftime('%Y-%m')];adjacent=True
  monthly.append({'month':month,'first_date':rs[0]['date'],'last_date':rs[-1]['date'],'prev_last_date':prev['date'] if prev and adjacent else None,'prev_close':prev['close'] if prev and adjacent else None,'close':rs[-1]['close'],'monthly_return':rs[-1]['close']/prev['close']-1 if prev and adjacent else None,'complete':month<ASOF[:7],'published':rs[0]['date']>=asset['release']})
  prev=rs[-1];prevmonth=month
 cases=[];paths=[]
 for m in monthly:
  if not m['complete'] or m['monthly_return'] is None:continue
  ei=bisect.bisect_right(dates,m['last_date'])
  if ei==len(daily):continue
  entry=daily[ei];target=addmonths(dt.date.fromisoformat(entry['date']),3).isoformat();xi=bisect.bisect_left(dates,target);exit=daily[xi] if xi<len(daily) else None
  hold=daily[ei:xi];vals=[entry['open']]+[r['close'] for r in hold]+([exit['open']] if exit else []);vdates=[entry['date']]+[r['date'] for r in hold]+([exit['date']] if exit else [])
  peak=vals[0];mdd=0;peakdate=entry['date'];peak_of_worst=peakdate;trough=peakdate;path=[]
  for n,(date,v) in enumerate(zip(vdates,vals)):
   if v>peak:peak=v;peakdate=date
   dd=v/peak-1
   if dd<mdd:mdd=dd;peak_of_worst=peakdate;trough=date
   path.append({'index_id':ident,'event':m['month'],'date':date,'point_type':'买入开盘' if n==0 else ('卖出开盘' if exit and n==len(vals)-1 else '每日收盘'),'price':v,'return':v/entry['open']-1,'drawdown':dd})
  validlows=[r for r in hold if r['low'] is not None];worst=min(validlows,key=lambda r:r['low']) if validlows else None
  e={'month':m['month'],'signal_date':m['last_date'],'monthly_return':m['monthly_return'],'published':m['published'],'entry_date':entry['date'],'entry_open':entry['open'],'target_exit_date':target,'exit_date':exit['date'] if exit else None,'exit_open':exit['open'] if exit else None,'status':'已完成' if exit else '观察中','return':exit['open']/entry['open']-1 if exit else None,'holding_calendar_days':(dt.date.fromisoformat(exit['date'])-dt.date.fromisoformat(entry['date'])).days if exit else None,'holding_trading_days':len(hold),'max_drawdown':mdd,'drawdown_peak_date':peak_of_worst,'drawdown_trough_date':trough,'worst_intraday_return':worst['low']/entry['open']-1 if worst and len(validlows)==len(hold) else None,'worst_intraday_date':worst['date'] if worst and len(validlows)==len(hold) else None}
  assert entry['date']>m['last_date'] and (not exit or (exit['date']>=target and dates[xi-1]<target))
  assert mdd<=0
  cases.append(e)
  if m['monthly_return']<-.10:paths.extend(path)
 availablemonths=[m for m in monthly if m['complete'] and m['monthly_return'] is not None]
 summary={'data_start':dates[0],'data_end':dates[-1],'daily_rows':len(daily),'monthly_start':availablemonths[0]['month'],'monthly_end':availablemonths[-1]['month'],'complete_months':len(availablemonths),'published_monthly_start':next((m['month'] for m in availablemonths if m['published']),None)}
 validation={'cross_source_days':overlap,'original_ohlc_differences_over_0_011':len(diffs),'original_invalid_ohlc_count':len(invalid),'differences':diffs,'invalid_original_rows':invalid,'calendar_large_gaps':[{'prev':a,'next':b,'days':(dt.date.fromisoformat(b)-dt.date.fromisoformat(a)).days} for a,b in zip(dates,dates[1:]) if (dt.date.fromisoformat(b)-dt.date.fromisoformat(a)).days>12],'source_policy':'有效指数公司官方OHLC优先，其次搜狐，再其次腾讯；空开盘价不以收盘替代。差异保留原始响应。'}
 for basis in ['full','published','recent10']:
  for t in [10,15,20,25]:
   es=[e for e in cases if e['monthly_return']<-t/100 and (basis!='published' or e['published']) and (basis!='recent10' or e['month']>='2016-10')]
   matrix.append(dict(index_id=ident,name=asset['name'],basis=basis,threshold=t,**metrics(es)))
 assets.append(dict(asset,available=True,summary=summary,validation=validation,monthly=monthly,all_month_events=cases,daily=daily))
 all_daily.extend(dict(index_id=ident,**r) for r in daily);all_monthly.extend(dict(index_id=ident,**r) for r in monthly);all_cases.extend(dict(index_id=ident,**e) for e in cases);all_paths.extend(paths)
payload={'asof':ASOF,'assets':assets,'matrix':matrix,'thresholds':[10,15,20,25],'rule':{'entry':'next_month_first_trading_day_open','exit':'first_trading_day_on_or_after_entry_plus_3_calendar_months','overlap':'independent_event_cohorts','monthly':'natural_month_close_to_previous_month_close','strict_threshold':True,'cost':0}}
(OUT/'research.json').write_text(json.dumps(payload,ensure_ascii=False,separators=(',',':')))
def savecsv(name,rs):
 if not rs:return
 with (OUT/name).open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rs[0]));w.writeheader();w.writerows(rs)
for name,rs in [('daily.csv',all_daily),('monthly.csv',all_monthly),('all_month_cases.csv',all_cases),('events.csv',[e for e in all_cases if e['monthly_return']<-.10]),('event_paths.csv',all_paths),('summary.csv',matrix)]:savecsv(name,rs)
db=sqlite3.connect(OUT/'research.sqlite')
for name,rs in [('index_registry',registry),('market_daily',all_daily),('monthly_returns',all_monthly),('monthly_cohorts',all_cases),('event_paths',all_paths),('scenario_summary',matrix)]:
 db.execute(f'DROP TABLE IF EXISTS {name}')
 if not rs:continue
 keys=list(rs[0]);db.execute(f'CREATE TABLE {name} ('+','.join('"'+k+'" '+('REAL' if isinstance(rs[0][k],(int,float)) else 'TEXT') for k in keys)+')')
 db.executemany(f'INSERT INTO {name} VALUES ('+','.join('?' for k in keys)+')',[[r[k] for k in keys] for r in rs])
for table,col in [('market_daily','date'),('monthly_returns','month'),('monthly_cohorts','month')]:db.execute(f'CREATE UNIQUE INDEX IF NOT EXISTS {table}_key ON {table}(index_id,{col})')
db.execute('CREATE TABLE IF NOT EXISTS research_metadata (key TEXT PRIMARY KEY,value TEXT)')
for k,v in [('rule',payload['rule']),('asof',ASOF),('source_hashes',{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in RAW.glob('*.json')}),('code_hash',hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest())]:db.execute('INSERT OR REPLACE INTO research_metadata VALUES (?,?)',(k,json.dumps(v,ensure_ascii=False)))
db.commit();db.close()
for a in assets:print(a['name'],a['summary'], '异常',a['validation'].get('original_invalid_ohlc_count'), '长间隔',a['validation'].get('calendar_large_gaps'))
for r in matrix:
 if r['basis']=='published':print(r['name'],r['threshold'],r['completed_count'],r['win_rate'],r['mean_return'],r['worst_max_drawdown'])
