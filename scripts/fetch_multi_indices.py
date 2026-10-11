import json,pathlib,urllib.request,concurrent.futures,time
ROOT=pathlib.Path(__file__).resolve().parents[1]; OUT=ROOT/'data'; RAW=OUT/'raw';RAW.mkdir(parents=True,exist_ok=True)
INDEXES=[
 {'id':'sh000001','code':'000001','name':'上证综指','release':'1991-07-15','sohu':'zs_000001'},
 {'id':'sh000300','code':'000300','name':'沪深300','release':'2005-04-08','sohu':'zs_000300'},
 {'id':'sh000905','code':'000905','name':'中证500','release':'2007-01-15','sohu':'zs_000905'},
 {'id':'sh000852','code':'000852','name':'中证1000','release':'2014-10-17','sohu':'zs_000852'},
 {'id':'sh932000','code':'932000','name':'中证2000','release':'2023-08-11','sohu':'zs_932000'},
 {'id':'sh000016','code':'000016','name':'上证50','release':'2004-01-02','sohu':'zs_000016'},
 {'id':'sz399001','code':'399001','name':'深证成指','release':'1995-01-23','sohu':'zs_399001'},
 {'id':'sz399006','code':'399006','name':'创业板指','release':'2010-06-01','sohu':'zs_399006'},
 {'id':'sh000922','code':'000922','name':'中证红利','release':'2008-05-26','sohu':'zs_000922'},
 {'id':'sh000688','code':'000688','name':'科创50','release':'2020-07-23','sohu':'zs_000688'}]
(OUT/'index_registry.json').write_text(json.dumps(INDEXES,ensure_ascii=False,indent=2))
def fetch(job):
 i,source,year=job
 if source=='tencent':url=f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={i['id']},day,{year}-01-01,{min(year+4,2026)}-12-31,2000,qfq";name=f"{i['id']}_tencent_{year}.json"
 else:url=f"https://q.stock.sohu.com/hisHq?code={i['sohu']}&start=19900101&end=20261011&stat=1&order=A&period=d&rt=json";name=f"{i['id']}_sohu.json"
 dest=RAW/name
 try:
  if dest.exists():data=dest.read_bytes()
  else:
   for attempt in range(3):
    try:
     with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'}),timeout=25) as r:data=r.read()
     dest.write_bytes(data);break
    except Exception:
     if attempt==2:raise
     time.sleep(1)
  x=json.loads(data)
  if source=='tencent':ob=x.get('data',{}).get(i['id'],{});rs=ob.get('day',ob.get('qfqday',[]))
  else:rs=x[0].get('hq',[]) if isinstance(x,list) and x else []
  return {'id':i['id'],'source':source,'file':name,'url':url,'rows':len(rs),'first':rs[0][0] if rs else None,'last':rs[-1][0] if rs else None}
 except Exception as e:return {'id':i['id'],'source':source,'file':name,'url':url,'error':str(e)}
jobs=[(i,'tencent',y) for i in INDEXES for y in range(1990,2027,5)]+[(i,'sohu',None) for i in INDEXES]
with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:manifest=list(pool.map(fetch,jobs))
(RAW/'fetch_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
for i in INDEXES:
 rs=[r for r in manifest if r['id']==i['id'] and r.get('rows',0)>0]
 print(i['name'],[(r['source'],r['rows'],r['first'],r['last']) for r in rs])
print('errors',[r for r in manifest if 'error'in r])
