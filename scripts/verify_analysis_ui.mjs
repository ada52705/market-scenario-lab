import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import {chromium} from 'playwright';

const output=name=>fileURLToPath(new URL(`../data/${name}`,import.meta.url));
const data=JSON.parse(await fs.readFile(output('research.json'),'utf8'));
const stats=values=>{
 const wins=values.filter(value=>value>0),losses=values.filter(value=>value<0);
 const mean=xs=>xs.length?xs.reduce((sum,value)=>sum+value,0)/xs.length:null;
 return {win:values.length?wins.length/values.length:null,payoff:wins.length&&losses.length?mean(wins)/Math.abs(mean(losses)):null,mean:mean(values),avgwin:mean(wins),avgloss:mean(losses),count:values.length,wins:wins.length,losses:losses.length};
};
const pct=value=>value==null?'—':(value*100).toFixed(2)+'%';
const browser=await chromium.launch({headless:true,...(process.env.BROWSER_EXECUTABLE?{executablePath:process.env.BROWSER_EXECUTABLE}:{})});
try{
 const page=await browser.newPage({viewport:{width:1440,height:1050}}),errors=[];
 page.on('pageerror',error=>errors.push(error.message));
 await page.goto(process.env.PREVIEW_URL||new URL('../public/index.html',import.meta.url).href);
 assert.equal(await page.locator('[data-mode],#signal-mode').count(),0,'自然月场景仍可选择');
 assert.ok(!(await page.locator('body').textContent()).includes('自然月急跌'));
 assert.equal(await page.locator('.account-benchmark-line').count(),1,'指数未默认展示');
 assert.equal(await page.locator('#account-benchmark-hide').isChecked(),false);
 const original=await page.evaluate(()=>window.accountQA.summary());
 for(const view of ['nav','pnl']){
  await page.selectOption('#account-view',view);await page.check('#account-benchmark-hide');
  assert.equal(await page.locator('.account-benchmark-line').count(),0);
  assert.ok(await page.locator('#benchmark-legend').isHidden());
  await page.setViewportSize({width:1280,height:900});await page.waitForTimeout(100);
  assert.equal(await page.locator('.account-benchmark-line').count(),0,'重绘恢复了隐藏的指数');
  await page.uncheck('#account-benchmark-hide');assert.equal(await page.locator('.account-benchmark-line').count(),1);
  assert.deepEqual(await page.evaluate(()=>window.accountQA.summary()),original,'显示对照改变了账户计算');
 }
 await page.check('#account-benchmark-hide');await page.click('#reset');
 assert.equal(await page.locator('.account-benchmark-line').count(),1,'恢复参数后对照开关与曲线不一致');
 assert.deepEqual(await page.evaluate(()=>window.accountQA.summary()),original);
 for(const values of [[],[0,0],[.2,.1,0],[-.2,-.1,0],[.2,-.1,0]]){
  const expected=stats(values),actual=await page.evaluate(values=>window.researchQA.outcomeStats(values),values);
  assert.equal(actual.count,expected.count);assert.equal(actual.winRate,expected.win);assert.equal(actual.payoff,expected.payoff);
  assert.equal(actual.mean,expected.mean);assert.equal(actual.flat,values.filter(value=>value===0).length);
 }
 let checked=0;
 for(const asset of data.assets)for(const threshold of data.thresholds){
  await page.selectOption('#asset',asset.id);await page.selectOption('#threshold',String(threshold));
  await page.fill('#cost','10');await page.click('#generate');
  const result=await page.evaluate(()=>({events:window.rollingQA.events(),account:window.accountQA.data()}));
  const events=result.events.filter(event=>event.status==='已完成').map(event=>(1+event.return)*.999/1.001-1);
  const trades=result.account.trades.filter(trade=>trade.status==='已平仓').map(trade=>trade.net_return);
  for(const [prefix,values] of [['event',events],['trade',trades]]){
   const expected=stats(values);
   assert.equal(await page.locator('#'+prefix+'-win').textContent(),pct(expected.win));
   assert.equal(await page.locator('#'+prefix+'-payoff').textContent(),expected.payoff==null?'不可估算':expected.payoff.toFixed(2)+' : 1');
   for(const key of ['mean','avgwin','avgloss'])assert.equal(await page.locator('#'+prefix+'-'+key).textContent(),pct(expected[key]));
   assert.ok((await page.locator('#'+prefix+'-samples').textContent()).includes(`${expected.count}个完整样本`));
   if(expected.count<20&&expected.count>0)assert.ok((await page.locator('#'+prefix+'-interpretation').textContent()).includes('样本不足20个'));
  }
  const expected=stats(events),cell=await page.locator(`#matrixrows [data-asset="${asset.id}"][data-t="${threshold}"]`).textContent();
  assert.ok(cell.includes('赔率 '+(expected.payoff==null?'不可估算':expected.payoff.toFixed(2)+' : 1')));
  checked++;
 }
 await page.click('#reset');await page.click('#generate');
 assert.equal(await page.locator('.account-benchmark-line').count(),1);
 assert.equal(await page.locator('#holding-months').inputValue(),'1');
 assert.deepEqual(await page.evaluate(()=>window.accountQA.summary()),original);
 const before=await page.locator('#analysis').textContent();
 await page.fill('#cost','10');assert.equal(await page.locator('#analysis').textContent(),before,'新参数未经生成进入分析');
 await page.click('#generate');await page.locator('#analysis').screenshot({path:output('analysis-desktop-qa.png')});
 await page.screenshot({path:output('comparison-desktop-qa.png')});
 for(const [width,height] of [[390,844],[320,640],[844,390]]){
  await page.setViewportSize({width,height});await page.waitForTimeout(100);
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
  const fits=await page.locator('.outcome-kpis strong,.outcome-details dd').evaluateAll(nodes=>nodes.every(node=>node.scrollWidth<=node.clientWidth));
  assert.ok(fits,'分析指标溢出');
  if(width===390)await page.locator('#analysis').screenshot({path:output('analysis-mobile-qa.png')});
 }
 assert.deepEqual(errors,[]);
 console.log(`分析界面通过：${checked}组事件/账户胜率赔率、零收益边界、缺失样本、成本、矩阵、参数暂存、默认指数对照及隐藏、手机布局`);
}finally{await browser.close()}
