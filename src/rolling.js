const rollingCache=new Map(),rollingRowCache=new Map();
function eventKey(event){return event.signal_date}
function triggerReturn(event){return event.signal_return}
function rollingRows(asset){
 const basis=param('basis'),start=(param('start')||'1991-01')+'-01',key=[asset.id,basis,start].join('|');
 if(rollingRowCache.has(key))return rollingRowCache.get(key);
 let beginning=start;if(basis==='published'||basis==='common')beginning=beginning>asset.release?beginning:asset.release;
 if(basis==='recent10'&&beginning<'2016-10-01')beginning='2016-10-01';if(basis==='common'&&beginning<'2023-09-01')beginning='2023-09-01';
 const rows=asset.daily.filter(row=>row.date>=beginning);rollingRowCache.set(key,rows);return rows;
}
function addCalendarMonth(date,months=Number(param('holding-months'))){
 const [year,month,day]=date.split('-').map(Number),offset=month-1+months,nextYear=year+Math.floor(offset/12),nextMonth=offset%12+1,lastDay=new Date(Date.UTC(nextYear,nextMonth,0)).getUTCDate();
 return `${nextYear}-${String(nextMonth).padStart(2,'0')}-${String(Math.min(day,lastDay)).padStart(2,'0')}`;
}
function rollingEvents(asset,threshold=Number(param('threshold'))){
 const window=Number(param('window-days')),key=[asset.id,param('basis'),param('start'),window,threshold,param('holding-months')].join('|');
 if(rollingCache.has(key))return rollingCache.get(key);
 const rows=rollingRows(asset),result=[];let wasBelow=false;
 for(let index=window-1;index<rows.length;index++){
  // Direct price comparison preserves strict equality at the configured threshold.
  const observed=rows.slice(index-window+1,index+1),peak=observed.reduce((best,row)=>row.close>=best.close?row:best),signal=rows[index],change=signal.close/peak.close-1,below=signal.close*100<peak.close*(100-threshold),crossing=below&&!wasBelow;wasBelow=below;
  if(!crossing)continue;
  const event={month:signal.date.slice(0,7),signal_date:signal.date,signal_return:change,signal_close:signal.close,reference_date:peak.date,reference_close:peak.close,window_start:observed[0].date,window_end:signal.date,window_days:window,published:observed[0].date>=asset.release,entry_date:null,entry_open:null,target_exit_date:null,exit_date:null,exit_open:null,status:'待买入',return:null,holding_calendar_days:null,holding_trading_days:0,max_drawdown:null,worst_intraday_return:null};
  if(index+1<rows.length)Object.assign(event,holdingEvent(event,rows,index+1));
  result.push(event);
 }
 rollingCache.set(key,result);return result;
}
function holdingEvent(event,rows,entryIndex){
 const entry=rows[entryIndex],target=addCalendarMonth(entry.date);let left=entryIndex,right=rows.length;
 while(left<right){const middle=Math.floor((left+right)/2);if(rows[middle].date<target)left=middle+1;else right=middle}
 const exit=rows[left],held=rows.slice(entryIndex,left);let high=entry.open,drawdown=0;
 for(const value of [entry.open,...held.map(row=>row.close),...(exit?[exit.open]:[])]){high=Math.max(high,value);drawdown=Math.min(drawdown,value/high-1)}
 const lows=held.filter(row=>row.low!=null);
 return {...event,entry_date:entry.date,entry_open:entry.open,target_exit_date:target,exit_date:exit?.date||null,exit_open:exit?.open??null,status:exit?'已完成':'观察中',return:exit?exit.open/entry.open-1:null,holding_calendar_days:exit?(Date.parse(exit.date)-Date.parse(entry.date))/86400000:null,holding_trading_days:held.length,max_drawdown:drawdown,valuation_date:exit?null:rows.at(-1).date,valuation_close:exit?null:rows.at(-1).close,unrealized_return:exit?null:rows.at(-1).close/entry.open-1,worst_intraday_return:lows.length&&lows.length===held.length?Math.min(...lows.map(row=>row.low))/entry.open-1:null};
}
function researchEvents(asset,threshold=Number(param('threshold'))){return rollingEvents(asset,threshold)}
function researchControls(){
 $('rule-text').textContent=`最近${param('window-days')}个交易日（含当日）最高收盘至当日收盘回撤 → 首次严格跌破阈值 → 空仓时下一交易日开盘全仓买入 → 满${param('holding-months')}个日历月后开盘卖出。`;
 $('account-rule').textContent=`全仓买入，持有${param('holding-months')}个日历月，空仓时现金不计息；已有持仓时忽略新信号，同日开盘先卖后买。`;
 $('method-signal').textContent=`最近${param('window-days')}个交易日含当日；回撤＝当日收盘／窗口内最高收盘－1。完整窗口形成后首次严格跌破阈值触发；回到阈值以上（含相等）后重置，持仓期间也照常判断穿越。`;
 $('method-holding').textContent=`收盘确认信号，下一交易日开盘买入；实际买入日加${param('holding-months')}个日历月（${holdingLabel()}），当天或之后首个交易日开盘卖出。目标月份没有同号日期时取该月最后一天；1年按12个日历月计算。`;
 $('method-history').textContent='发布后模式从发布当天或之后的首个行情交易日积累完整窗口；全历史可包含回溯。筛选起点前的数据不进入窗口。自然月热图仅作背景，缺相邻月末点位不计算月收益，2026年10月尚未结束。上证综指2020年编制方法有调整，长历史不能假设制度恒定。';
}
