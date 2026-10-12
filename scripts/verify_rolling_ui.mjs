import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import {chromium} from 'playwright';

const dataPath=name=>fileURLToPath(new URL(`../data/${name}`,import.meta.url));
const cases=JSON.parse(await fs.readFile(dataPath('rolling-validation.json'),'utf8'));
const browser=await chromium.launch({headless:true,...(process.env.BROWSER_EXECUTABLE?{executablePath:process.env.BROWSER_EXECUTABLE}:{})});
const close=(actual,expected,label)=>{
  if(typeof expected==='number')assert.ok(Math.abs(actual-expected)<=1e-8*Math.max(1,Math.abs(expected)),`${label}: ${actual} / ${expected}`);
  else assert.equal(actual,expected,label);
};
try{
 const page=await browser.newPage({viewport:{width:1440,height:1050}}),errors=[];
 page.on('pageerror',error=>errors.push(error.message));
 await page.goto(process.env.PREVIEW_URL||new URL('../public/index.html',import.meta.url).href);
 const oldSummary=await page.evaluate(()=>window.accountQA.summary());
 for(let begin=0;begin<cases.length;begin+=40){
  const batch=cases.slice(begin,begin+40);
  const actual=await page.evaluate(batch=>batch.map(config=>{
   for(const [id,value] of Object.entries({basis:config.basis,'window-days':config.window,threshold:config.threshold,cost:config.cost_bps,start:'1991-01',capital:'100','holding-months':'1'}))document.getElementById(id).value=String(value);
   const events=window.rollingQA.rawEvents(config.index_id),account=window.rollingQA.compute(config.index_id),finished=events.filter(event=>event.status==='已完成'),cost=config.cost_bps/10000,returns=finished.map(event=>(1+event.return)*(1-cost)/(1+cost)-1);
   return {summary:account.summary,event_count:events.length,completed_count:finished.length,win_rate:returns.length?returns.filter(value=>value>0).length/returns.length:null,mean_return:returns.length?returns.reduce((sum,value)=>sum+value,0)/returns.length:null,signals:config.cost_bps===0?events.map(event=>[event.signal_date,event.reference_date,event.entry_date,event.exit_date]):null};
  }),batch);
  for(let index=0;index<batch.length;index++){
   const expected=batch[index],result=actual[index],label=[expected.index_id,expected.basis,expected.window,expected.threshold,expected.cost_bps].join('/');
   if(expected.summary===null)assert.equal(result.summary,null,label);
   else for(const key of ['start_date','end_date','signal_mode','window_days','holding_months','waiting_signals','final_nav','total_return','pnl','cagr','max_drawdown','accepted_signals','closed_trades','open_trades','ignored_signals','win_rate','exposure','held_days','cash_days','benchmark_return'])close(result.summary[key],expected.summary[key],`${label}/${key}`);
   for(const key of ['event_count','completed_count','win_rate','mean_return'])close(result[key],expected[key],`${label}/${key}`);
   assert.deepEqual(result.signals,expected.signals,`${label}/signals`);
  }
 }
 console.log('浏览器逐组核对通过：1600组滚动账户与事件，800组高点、信号和买卖日期');
 await page.click('#reset');await page.click('#generate');
 assert.deepEqual(await page.evaluate(()=>window.accountQA.summary()),oldSummary,'默认滚动结果变化');

 assert.equal(await page.locator('#holding-months').inputValue(),'1');
 assert.ok(await page.locator('#window-field').isVisible());
 const events=await page.evaluate(()=>window.rollingQA.events()),account=await page.evaluate(()=>window.accountQA.data());
 const signal=events.find(event=>event.signal_date==='2015-06-26');
 assert.equal(signal.reference_date,'2015-06-12');
 assert.equal(signal.entry_date,'2015-06-29');
 assert.equal(signal.exit_date,'2015-07-29');
 assert.ok(account.trades.some(trade=>trade.signal_date==='2015-06-26'));
 assert.ok(account.ignored.some(event=>event.signal_date==='2015-07-27'));
 await page.selectOption('#event','2015-06-26');
 assert.equal((await page.evaluate(()=>window.researchQA.snapshot())).chosen,'2015-06-26');
 assert.ok((await page.locator('#pathstats').textContent()).includes('2015-06-12'));
 assert.ok((await page.locator('#account-signal-legend').textContent()).includes('25日窗口'));
 assert.equal(await page.locator('.account-holding-band').count(),account.trades.length);
 assert.equal(await page.locator('.account-signal-band').count(),events.length);
 assert.equal(await page.locator('.heat .trigger').count(),0,'自然月热图混用了滚动信号');
 await page.screenshot({path:dataPath('rolling-desktop-qa.png')});
 await page.locator('#events').screenshot({path:dataPath('rolling-events-qa.png')});
 const [download]=await Promise.all([page.waitForEvent('download'),page.click('#export')]);
 await download.saveAs(dataPath('界面导出_滚动事件.csv'));
 const csv=await fs.readFile(dataPath('界面导出_滚动事件.csv'),'utf8');
 assert.ok(csv.includes('参考高点日期')&&csv.includes('2015-06-26')&&csv.includes('2015-06-12'));
 await page.click('#start-trigger');await page.click('[data-year="2026"]');await page.click('[data-picker-month="9"]');await page.click('#month-apply');await page.click('#generate');
 assert.ok((await page.evaluate(()=>window.rollingQA.events())).every(event=>event.window_start>='2026-09-01'));
 for(const window of [3,5,10,20,25]){
  await page.selectOption('#window-days',String(window));await page.click('#generate');
  assert.equal((await page.evaluate(()=>window.accountQA.summary())).window_days,window);
  assert.ok((await page.locator('#rule-text').textContent()).includes(`${window}个交易日`));
 }
 await page.click('#reset');await page.click('#generate');
 await page.selectOption('#threshold','10');
 await page.click('#matrixrows [data-asset="sh000300"][data-t="15"]');await page.click('#generate');
 const matrixCase=cases.find(config=>config.index_id==='sh000300'&&config.basis==='published'&&config.window===25&&config.threshold===15&&config.cost_bps===0);
 assert.equal((await page.evaluate(()=>window.researchQA.snapshot())).count,matrixCase.completed_count);
 await page.selectOption('#account-view','pnl');await page.uncheck('#account-benchmark-hide');
 assert.ok((await page.locator('#account-chart').textContent()).includes('累计盈亏'));
 for(const [width,height] of [[390,844],[320,640],[844,390]]){
  await page.setViewportSize({width,height});
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,'滚动模式横向溢出');
  if(width===390)await page.screenshot({path:dataPath('rolling-mobile-qa.png')});
 }
 await page.click('#reset');await page.click('#generate');
 assert.ok(await page.locator('#window-field').isVisible());
 assert.deepEqual(await page.evaluate(()=>window.accountQA.summary()),oldSummary);
 assert.deepEqual(errors,[]);
 console.log('滚动界面通过：2015年高点与入场、持仓忽略、持有一个月、移除自然月入口、窗口切换、日期范围、矩阵、成本、事件导出、盈亏对照与手机布局');
}finally{await browser.close()}
