import assert from 'node:assert/strict';
import {execFileSync} from 'node:child_process';
import fs from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import {chromium} from 'playwright';

const root=fileURLToPath(new URL('../',import.meta.url));
const output=name=>fileURLToPath(new URL(`../data/${name}`,import.meta.url));
const cases=JSON.parse(execFileSync(process.env.PYTHON_EXECUTABLE||'python',['-X','utf8','scripts/test_holding.py','--json','--rolling-only'],{cwd:root,encoding:'utf8',maxBuffer:64*1024*1024}));
const close=(actual,expected,label)=>{
 if(typeof expected==='number')assert.ok(typeof actual==='number'&&Math.abs(actual-expected)<=1e-8*Math.max(1,Math.abs(expected)),`${label}: ${actual} / ${expected}`);
 else assert.equal(actual,expected,label);
};
const browser=await chromium.launch({headless:true,...(process.env.BROWSER_EXECUTABLE?{executablePath:process.env.BROWSER_EXECUTABLE}:{})});
try{
 const page=await browser.newPage({viewport:{width:1440,height:1050}}),errors=[];
 page.on('pageerror',error=>errors.push(error.message));
 await page.goto(process.env.PREVIEW_URL||new URL('../public/index.html',import.meta.url).href);
 const baseline=await page.evaluate(()=>window.accountQA.summary());
 for(let begin=0;begin<cases.length;begin+=40){
  const batch=cases.slice(begin,begin+40);
  const actual=await page.evaluate(batch=>batch.map(config=>{
   for(const [id,value] of Object.entries({basis:config.basis,'window-days':config.window||25,threshold:config.threshold,cost:config.cost_bps,start:'1991-01',capital:100,'holding-months':config.holding_months}))document.getElementById(id).value=String(value);
   const account=window.rollingQA.compute(config.index_id),events=window.researchQA.rawEvents(config.index_id);
   const fields=['signal_date','entry_date','target_exit_date','exit_date','status','return','max_drawdown','worst_intraday_return','holding_trading_days'];
   return {summary:account.summary,trades:account.trades.map(trade=>[trade.entry_date,trade.target_exit_date,trade.exit_date,trade.net_return]),events:config.cost_bps===0?events.map(event=>fields.map(field=>event[field]??null)):null};
  }),batch);
  for(let index=0;index<batch.length;index++){
   const expected=batch[index],result=actual[index],label=[expected.index_id,expected.basis,expected.window,expected.threshold,expected.cost_bps,expected.holding_months].join('/');
   if(expected.summary===null)assert.equal(result.summary,null,label);
   else for(const key of Object.keys(result.summary))close(result.summary[key],expected.summary[key],`${label}/${key}`);
   for(const type of ['trades','events']){
    if(expected[type]===null){assert.equal(result[type],null);continue}
    assert.equal(result[type].length,expected[type].length,`${label}/${type}/count`);
    for(let row=0;row<expected[type].length;row++)expected[type][row].forEach((value,col)=>close(result[type][row][col],value,`${label}/${type}/${row}/${col}`));
   }
  }
 }
 console.log(`四档持有期独立核对通过：${cases.length}组账户、交易与事件日期/回撤/收益`);
 await page.click('#reset');await page.click('#generate');
 assert.deepEqual(await page.evaluate(()=>window.accountQA.summary()),baseline,'默认滚动结果改变');
 const oldTitle=await page.locator('h1').textContent(),oldRows=await page.locator('#eventrows').innerHTML();
 await page.selectOption('#asset','sh000300');await page.selectOption('#window-days','10');
 await page.selectOption('#holding-months','12');await page.selectOption('#threshold','15');
 await page.selectOption('#basis','full');await page.fill('#cost','10');await page.fill('#capital','50');
 assert.equal(await page.locator('#generation-status').textContent(),'参数已修改，结果尚未更新');
 assert.deepEqual(await page.evaluate(()=>window.accountQA.summary()),baseline);
 assert.equal(await page.locator('h1').textContent(),oldTitle);
 assert.equal(await page.locator('#eventrows').innerHTML(),oldRows);
 await page.selectOption('#account-view','pnl');await page.uncheck('#account-benchmark-hide');
 await page.setViewportSize({width:1280,height:900});await page.waitForTimeout(100);
 await page.click('#present');await page.click('#present');await page.waitForTimeout(100);
 assert.deepEqual(await page.evaluate(()=>window.accountQA.summary()),baseline,'重绘应用了尚未生成的参数');
 const [oldDownload]=await Promise.all([page.waitForEvent('download'),page.click('#account-export')]);
 assert.ok(oldDownload.suggestedFilename().includes('25日窗口_持有1月'));
 await oldDownload.saveAs(output('holding-pending-export-qa.csv'));
 const csv=await fs.readFile(output('holding-pending-export-qa.csv'),'utf8');
 assert.ok(csv.includes('2007-01-15')&&csv.includes('1000000'),'导出未保留已生成的本金及范围');
 await page.click('#generate');
 const generated=await page.evaluate(()=>window.accountQA.summary());
 const expected=cases.find(config=>config.index_id==='sh000300'&&config.window===10&&config.holding_months===12&&config.basis==='full'&&config.threshold===15&&config.cost_bps===10);
 close(generated.final_nav,expected.summary.final_nav,'生成一年账户');
 close(generated.pnl,expected.summary.pnl/2,'初始资金缩放');
 assert.equal(generated.holding_months,12);
 assert.ok((await page.locator('h1').textContent()).includes('持有1年'));
 assert.equal(await page.locator('#generation-status').textContent(),'结果已生成');
 const [download]=await Promise.all([page.waitForEvent('download'),page.click('#export')]);
 assert.ok(download.suggestedFilename().includes('10日窗口_持有12月_15%'));
 // Reset is a parameter action, not an implicit new backtest.
 await page.click('#reset');assert.deepEqual(await page.evaluate(()=>window.accountQA.summary()),generated);
 await page.click('#generate');assert.deepEqual(await page.evaluate(()=>window.accountQA.summary()),baseline);
 for(const months of [1,3,6,12]){
  await page.selectOption('#holding-months',String(months));await page.click('#generate');
  const event=(await page.evaluate(()=>window.rollingQA.events())).find(event=>event.signal_date==='2015-06-26');
  const ref=cases.find(config=>config.index_id==='sh000905'&&config.window===25&&config.holding_months===months&&config.basis==='published'&&config.threshold===20&&config.cost_bps===0);
  assert.deepEqual([event.entry_date,event.target_exit_date,event.exit_date],ref.events.find(row=>row[0]==='2015-06-26').slice(1,4));
  assert.ok((await page.locator('#account-rule').textContent()).includes(`${months}个日历月`));
 }
 await page.screenshot({path:output('holding-desktop-qa.png')});
 for(const [width,height] of [[390,844],[320,640],[844,390]]){
  await page.setViewportSize({width,height});await page.waitForTimeout(100);
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,'持有期界面横向溢出');
  const boxes=await page.locator('#generate, #reset, #holding-months').evaluateAll(nodes=>nodes.map(node=>{const rect=node.getBoundingClientRect();return {left:rect.left,right:rect.right,width:rect.width,height:rect.height}}));
  assert.ok(boxes.every(box=>box.left>=0&&box.right<=width&&box.height>=40));
  if(width===390)await page.screenshot({path:output('holding-mobile-qa.png')});
 }
 await page.click('#reset');await page.click('#generate');
 await page.fill('#cost','101');await page.click('#generate');
 assert.deepEqual(await page.evaluate(()=>window.accountQA.summary()),baseline,'无效参数被应用');
 await page.fill('#cost','0');await page.fill('#capital','-1');await page.click('#generate');
 assert.deepEqual(await page.evaluate(()=>window.accountQA.summary()),baseline);
 assert.deepEqual(errors,[]);
 console.log('生成结果界面通过：四档持有期、参数暂存、重绘与导出一致、生成更新、重置与输入校验、桌面和手机布局');
}finally{await browser.close()}
