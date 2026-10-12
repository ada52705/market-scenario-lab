import assert from 'node:assert/strict';
import {execFileSync} from 'node:child_process';
import fs from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import {chromium} from 'playwright';

const root=fileURLToPath(new URL('../',import.meta.url)),output=name=>fileURLToPath(new URL(`../data/${name}`,import.meta.url));
const cases=JSON.parse(execFileSync(process.env.PYTHON_EXECUTABLE||'python',['-X','utf8','scripts/test_unrealized.py','--json'],{cwd:root,encoding:'utf8',maxBuffer:32*1024*1024}));
function compare(actual,expected,label){
 if(typeof expected==='number')assert.ok(typeof actual==='number'&&Math.abs(actual-expected)<=1e-8*Math.max(1,Math.abs(expected)),`${label}: ${actual} / ${expected}`);
 else if(expected===null)assert.equal(actual,null,label);
 else if(Array.isArray(expected)){assert.equal(actual.length,expected.length,label);expected.forEach((value,index)=>compare(actual[index],value,`${label}/${index}`))}
 else if(typeof expected==='object')for(const [key,value] of Object.entries(expected))compare(actual[key],value,`${label}/${key}`);
 else assert.equal(actual,expected,label);
}
const browser=await chromium.launch({headless:true,...(process.env.BROWSER_EXECUTABLE?{executablePath:process.env.BROWSER_EXECUTABLE}:{})});
try{
 const page=await browser.newPage({viewport:{width:1440,height:1050}}),errors=[];
 page.on('pageerror',error=>errors.push(error.message));
 await page.goto(process.env.PREVIEW_URL||new URL('../public/index.html',import.meta.url).href);
 for(let begin=0;begin<cases.length;begin+=40){
  const batch=cases.slice(begin,begin+40),actual=await page.evaluate(batch=>batch.map(config=>{
   for(const [id,value] of Object.entries({basis:config.basis,'window-days':config.window,'holding-months':config.holding_months,threshold:config.threshold,cost:config.cost_bps,start:'1991-01',capital:100}))document.getElementById(id).value=String(value);
   const account=window.rollingQA.compute(config.index_id),signals=window.rollingQA.rawEvents(config.index_id);
   return {valuation:account.valuation,event_marks:signals.filter(event=>event.status!=='已完成').map(event=>[event.signal_date,event.valuation_date??null,event.valuation_close??null,event.unrealized_return??null]),pnl:account.summary.pnl,win:account.summary.win_rate};
  }),batch);
  for(let index=0;index<batch.length;index++){
   const expected=batch[index],result=actual[index];compare(result.valuation,expected.valuation,'valuation');compare(result.event_marks,expected.event_marks,'events');
   compare(result.pnl,result.valuation.realized_pnl+result.valuation.unrealized_pnl,'总盈亏=已实现+浮动');
   compare(result.win,expected.summary.win_rate,'浮动收益未进入胜率');
  }
 }
 const config=cases.find(config=>config.cost_bps===10&&config.holding_months===12&&config.valuation.position&&config.valuation.realized_pnl!==0);
 assert.ok(config,'没有找到已实现与浮动混合场景');
 for(const [id,value] of Object.entries({asset:config.index_id,basis:config.basis,'window-days':config.window,'holding-months':config.holding_months,threshold:config.threshold}))await page.selectOption('#'+id,String(value));
 await page.fill('#cost','10');await page.click('#generate');
 const result=await page.evaluate(()=>window.accountQA.data()),position=result.valuation.position,pct=value=>(value*100).toFixed(2)+'%';
 assert.equal(position.net_return,null);assert.equal(position.exit_date,null);
 assert.ok((await page.locator('#account-position').textContent()).includes('浮动收益 '+pct(position.unrealized_return)));
 assert.ok((await page.locator('#account-position').textContent()).includes(position.valuation_date));
 assert.ok((await page.locator('#account-pnl-breakdown').textContent()).includes('浮动 '+(position.unrealized_pnl/10000).toFixed(2)+'万'));
 assert.ok((await page.locator('#account-trades').textContent()).includes(pct(position.unrealized_return)));
 assert.ok((await page.locator('#trade-samples').textContent()).startsWith(result.summary.closed_trades+'个完整样本'));
 const events=await page.evaluate(()=>window.rollingQA.events()),pending=events.find(event=>event.signal_date===position.signal_date);
 assert.equal(pending.return,null);
 const net=pending.valuation_close/pending.entry_open/1.001-1;
 const cell=page.locator(`[data-event="${pending.signal_date}"]`).locator('..').locator('..');
 assert.ok((await cell.textContent()).includes(pct(net))&&(await cell.textContent()).includes('浮动'));
 await page.selectOption('#event',pending.signal_date);
 assert.ok((await page.locator('#pathstats').textContent()).includes('浮动收益 '+pct(net)));
 const [tradeDownload]=await Promise.all([page.waitForEvent('download'),page.click('#trades-export')]);
 await tradeDownload.saveAs(output('界面导出_浮动交易.csv'));
 const tradeCsv=await fs.readFile(output('界面导出_浮动交易.csv'),'utf8');
 assert.ok(tradeCsv.includes('unrealized_return')&&tradeCsv.includes('valuation_date')&&tradeCsv.includes(position.valuation_date));
 const [eventDownload]=await Promise.all([page.waitForEvent('download'),page.click('#export')]);
 await eventDownload.saveAs(output('界面导出_浮动事件.csv'));
 const eventCsv=await fs.readFile(output('界面导出_浮动事件.csv'),'utf8');
 assert.ok(eventCsv.includes('浮动收益')&&eventCsv.includes('估值日期')&&eventCsv.includes(pending.valuation_date));
 assert.ok((await page.locator('#source-summary').textContent()).includes('2026-10-09'));
 await page.locator('#account').screenshot({path:output('unrealized-desktop-qa.png')});
 const before=await page.locator('#account-position').textContent();await page.fill('#cost','0');
 assert.equal(await page.locator('#account-position').textContent(),before,'尚未生成参数改变了估值展示');
 for(const [width,height] of [[390,844],[320,640],[844,390]]){
  await page.setViewportSize({width,height});await page.waitForTimeout(100);
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,'浮动估值界面横向溢出');
  if(width===390)await page.locator('#account-position').screenshot({path:output('unrealized-mobile-qa.png')});
 }
 await page.click('#reset');await page.click('#generate');
 assert.ok((await page.locator('#account-position').textContent()).includes('当前空仓'));
 assert.ok((await page.locator('#account-pnl-breakdown').textContent()).includes('浮动 0.00万'));
 assert.deepEqual(errors,[]);
 console.log(`浮动估值核对通过：${cases.length}组Python独立参考，整体盈亏拆分、收益/日期/成本、未平仓不进入胜率赔率、导出、参数暂存与手机布局`);
}finally{await browser.close()}
