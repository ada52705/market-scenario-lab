"""Single-capital, full-allocation account; signals during an existing position are ignored."""
import json,pathlib,datetime as dt,csv,sqlite3,hashlib,math
ROOT=pathlib.Path(__file__).resolve().parents[1];OUT=ROOT/'data'
def eligible(e,basis,start):
 return e['month']>=start and (basis!='published' or e['published']) and (basis!='recent10' or e['month']>='2016-10') and (basis!='common' or (e['published'] and e['month']>='2023-09'))
def run(a,threshold=20,basis='published',start='1991-01',cost_bps=0,capital=1000000):
 months=[m for m in a['monthly'] if m['complete'] and m['monthly_return'] is not None and eligible(m,basis,start)]
 if not months:return {'summary':None,'daily':[],'points':[],'trades':[],'ignored':[]}
 beginning=months[0]['first_date'];rows=[r for r in a['daily'] if r['date']>=beginning];c=cost_bps/10000
 assert 0<=c<1 and capital>0
 signals={e['entry_date']:e for e in a['all_month_events'] if eligible(e,basis,start) and e['monthly_return']<-threshold/100}
 cash=1.;units=0.;position=None;trades=[];ignored=[];daily=[];points=[];peak=1.;mdd=0.;peakdate=beginning;worstpeak=beginning;worsttrough=beginning;held=0
 baseunits=1/(rows[0]['open']*(1+c))
 def point(date,kind,nav,benchmark):
  nonlocal peak,mdd,peakdate,worstpeak,worsttrough
  if nav>peak:peak=nav;peakdate=date
  dd=nav/peak-1
  if dd<mdd:mdd=dd;worstpeak=peakdate;worsttrough=date
  points.append({'date':date,'type':kind,'nav':nav,'benchmark':benchmark,'drawdown':dd,'pnl':capital*(nav-1)})
 point(beginning,'起始开盘',1.,1.)
 for r in rows:
  action=[];benchmark=baseunits*r['close']
  if position and position['target_exit_date']<=r['date']:
   point(r['date'],'卖出前开盘',units*r['open'],baseunits*r['open'])
   cash=units*r['open']*(1-c);units=0
   position.update(exit_date=r['date'],exit_open=r['open'],nav_after_exit=cash,net_return=cash/position['nav_before_entry']-1,status='已平仓')
   point(r['date'],'卖出后现金',cash,baseunits*r['open']);position=None;action.append('卖出')
  e=signals.get(r['date'])
  if e:
   if position:ignored.append({'signal_month':e['month'],'entry_date':r['date'],'reason':'已有持仓，忽略新信号'})
   else:
    nav_before=cash;units=cash/(r['open']*(1+c));cash=0
    position={'signal_month':e['month'],'signal_date':e['signal_date'],'monthly_return':e['monthly_return'],'entry_date':r['date'],'entry_open':r['open'],'target_exit_date':e['target_exit_date'],'exit_date':None,'exit_open':None,'nav_before_entry':nav_before,'nav_after_exit':None,'net_return':None,'status':'持仓中'};trades.append(position)
    point(r['date'],'买入后开盘',units*r['open'],baseunits*r['open']);action.append('买入')
  nav=cash+units*r['close'];held+=bool(position)
  point(r['date'],'每日收盘',nav,benchmark)
  daily.append({'date':r['date'],'nav':nav,'equity':nav*capital,'pnl':(nav-1)*capital,'cash':cash*capital,'position_value':units*r['close']*capital,'in_position':bool(position),'benchmark_nav':benchmark,'drawdown':nav/peak-1,'action':'、'.join(action) or ('持有' if position else '空仓')})
 final=daily[-1]['nav'];days=(dt.date.fromisoformat(rows[-1]['date'])-dt.date.fromisoformat(beginning)).days;done=[t for t in trades if t['status']=='已平仓']
 summary={'index_id':a['id'],'name':a['name'],'basis':basis,'threshold':threshold,'cost_bps':cost_bps,'capital':capital,'start_date':beginning,'end_date':rows[-1]['date'],'final_nav':final,'total_return':final-1,'pnl':capital*(final-1),'cagr':final**(365.25/days)-1 if days>0 else None,'max_drawdown':mdd,'drawdown_peak_date':worstpeak,'drawdown_trough_date':worsttrough,'accepted_signals':len(trades),'closed_trades':len(done),'open_trades':int(position is not None),'ignored_signals':len(ignored),'win_rate':sum(t['net_return']>0 for t in done)/len(done) if done else None,'exposure':held/len(rows),'held_days':held,'cash_days':len(rows)-held,'benchmark_return':daily[-1]['benchmark_nav']-1,'cash_interest':0}
 for x,y in zip(daily,daily[1:]):
  if not y['in_position'] and y['action']=='空仓':assert abs(y['nav']-x['nav'])<1e-12
 for n,t in enumerate(trades):
  if n:assert trades[n-1]['exit_date'] is not None and trades[n-1]['exit_date']<=t['entry_date']
 assert len(trades)+len(ignored)==len(signals) and all(math.isfinite(q['nav']) and q['nav']>0 for q in daily)
 return {'summary':summary,'daily':daily,'points':points,'trades':trades,'ignored':ignored}
def build():
 p=json.loads((OUT/'research.json').read_text());summaries=[];qa=[];details={}
 for a in p['assets']:
  for basis in ['published','full','recent10','common']:
   for t in [10,15,20,25]:
    for cost in [0,10]:
     b=run(a,t,basis,cost_bps=cost);qa.append({'index_id':a['id'],'basis':basis,'threshold':t,'cost_bps':cost,'summary':b['summary']})
     if cost==0:
      summaries.append(b['summary']);details[(a['id'],basis,t)]=b
 sample=details[('sh000905','published',20)]
 assert [t['signal_month'] for t in sample['trades']]==['2008-03','2008-06','2008-10','2016-01']
 compound=math.prod(t['exit_open']/t['entry_open'] for t in sample['trades'])
 assert abs(sample['summary']['final_nav']-compound)<1e-12 and sample['summary']['ignored_signals']==1
 # Latest marks of pending positions enter total PnL; no fictitious sale is created.
 for a in p['assets']:
  b=run(a,0,'published');assert b['summary'] and b['summary']['open_trades'] in [0,1]
  if b['summary']['open_trades']:assert b['trades'][-1]['exit_date'] is None
 (OUT/'account-validation.json').write_text(json.dumps(qa,ensure_ascii=False,separators=(',',':')))
 def write(name,rs):
  with (OUT/name).open('w',encoding='utf-8-sig',newline='') as f:
   w=csv.DictWriter(f,fieldnames=list(rs[0]));w.writeheader();w.writerows(rs)
 write('策略账户情景汇总.csv',summaries);write('中证500跌超20%_逐日账户.csv',sample['daily']);write('中证500跌超20%_交易记录.csv',sample['trades']);write('中证500跌超20%_净值全路径.csv',sample['points'])
 db=sqlite3.connect(OUT/'research.sqlite')
 for table,records in [('account_summary',summaries),('account_daily',sample['daily']),('account_trades',sample['trades'])]:
  db.execute('DROP TABLE IF EXISTS '+table);keys=list(records[0]);db.execute('CREATE TABLE '+table+' ('+','.join('"'+k+'" '+('REAL' if isinstance(records[0][k],(float,int)) else 'TEXT') for k in keys)+')');db.executemany('INSERT INTO '+table+' VALUES ('+','.join('?' for _ in keys)+')',[[r[k] for k in keys] for r in records])
 db.execute('INSERT OR REPLACE INTO research_metadata VALUES (?,?)',('account_rule',json.dumps({'allocation':'全仓，单一资金账户','overlap':'已有持仓时忽略新信号；同日开盘先卖后买','cash_interest':0,'mark':'daily_close_and_execution_open','pending':'latest_close_mark_to_market','benchmark':'same_start_open_buy_and_hold_cost_in_entry_no_terminal_sale','account_daily_scope':'sh000905/published/20/cost0/capital1000000','code_hash':hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest()},ensure_ascii=False)))
 db.commit();db.close();print(json.dumps(sample['summary'],ensure_ascii=False,indent=2));return sample
if __name__=='__main__':build()
