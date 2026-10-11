import sys,pathlib,math
sys.path.insert(0,str(pathlib.Path(__file__).parent))
from backtest_account import run
def fixture():
 dates=['2020-01-02','2020-01-31','2020-02-03','2020-03-02','2020-05-04','2020-06-01']
 rows=[{'date':d,'open':v,'close':v} for d,v in zip(dates,[100,80,100,110,120,125])]
 months=[{'month':'2020-01','first_date':dates[0],'monthly_return':-.2,'complete':True,'published':True}]
 events=[{'month':m,'entry_date':entry,'target_exit_date':target,'signal_date':signal,'monthly_return':-.21,'published':True} for m,entry,target,signal in [('2020-01','2020-02-03','2020-05-03','2020-01-31'),('2020-02','2020-03-02','2020-06-02','2020-02-28'),('2020-04','2020-05-04','2020-08-04','2020-04-30')]]
 return {'id':'fixture','name':'测试','monthly':months,'all_month_events':events,'daily':rows}
a=fixture();b=run(a,20,cost_bps=10)
assert b['summary']['accepted_signals']==2 and b['summary']['ignored_signals']==1 and b['summary']['open_trades']==1
assert b['trades'][0]['exit_date']=='2020-05-04' and b['trades'][1]['entry_date']=='2020-05-04'
assert b['trades'][1]['exit_date'] is None
expected=(120/100)*.999/1.001*(125/120)/1.001
assert math.isclose(b['summary']['final_nav'],expected,abs_tol=1e-12)
assert b['daily'][0]['nav']==1 and b['daily'][1]['nav']==1
assert b['daily'][-1]['in_position'] and b['trades'][1]['status']=='持仓中'
assert run(a,25)['summary']['final_nav']==1
print('Accounting fixtures passed: cash / costs / overlap / same-day reentry / open mark / strict threshold')
