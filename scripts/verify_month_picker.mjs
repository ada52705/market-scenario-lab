import assert from 'node:assert/strict';
import {chromium} from 'playwright';
import fs from 'node:fs/promises';
import {fileURLToPath} from 'node:url';

const output = name => fileURLToPath(new URL(`../data/${name}`, import.meta.url));
const data = JSON.parse(await fs.readFile(output('research.json'), 'utf8'));
const browser = await chromium.launch({headless: true, ...(process.env.BROWSER_EXECUTABLE ? {executablePath: process.env.BROWSER_EXECUTABLE} : {})});
try {
  const page = await browser.newPage({viewport: {width: 1440, height: 1000}});
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.goto(process.env.PREVIEW_URL || new URL('../public/index.html', import.meta.url).href);
  const state = () => page.evaluate(() => ({events: window.researchQA.snapshot(), account: window.accountQA.summary()}));
  const baseline = await state();
  const value = () => page.locator('#start').inputValue();
  const open = () => page.click('#start-trigger');
  const choose = async (year, month) => {
    await page.click(`#year-list [data-year="${year}"]`);
    await page.click(`#month-grid [data-picker-month="${month}"]`);
  };
  const checkBounds = async () => {
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false, '页面横向溢出');
    const box = await page.locator('#month-picker').boundingBox();
    const viewport = page.viewportSize();
    assert.ok(box.x >= 0 && box.y >= 0 && box.x + box.width <= viewport.width && box.y + box.height <= viewport.height, '弹窗超出视口');
    assert.equal(await page.locator('#month-grid button').count(), 12);
    for (const button of await page.locator('#month-grid button, #year-list button').all()) {
      const bounds = await button.boundingBox();
      assert.ok(bounds.height >= 44, '点击区域过小');
    }
  };

  await open();
  await choose(2008, 10);
  assert.deepEqual(await state(), baseline, '未确认时改变了研究结果');
  await page.click('#month-cancel');
  assert.equal(await value(), '1991-01');
  assert.equal(await page.evaluate(() => document.activeElement.id), 'start-trigger');
  await open();
  await choose(2008, 10);
  await checkBounds();
  await page.screenshot({path: output('month-picker-desktop-qa.png')});
  await page.click('#month-apply');await page.click('#generate');
  assert.equal(await value(), '2008-10');
  assert.equal(await page.locator('#start-label').textContent(), '2008年10月');
  const asset = data.assets.find(asset => asset.id === 'sh000905');
  const events = await page.evaluate(() => window.rollingQA.events().filter(event => event.status === '已完成'));
  assert.equal((await state()).events.count, events.length);
  const result = await page.evaluate(() => window.accountQA.data());
  assert.ok(result.summary.start_date >= '2008-10-01');
  assert.ok(result.trades.length > 0 && result.trades.every(trade => trade.signal_month >= '2008-10'));

  await open();
  await page.click('#year-next');
  assert.equal(await page.locator('#picker-year').textContent(), '2009年');
  await page.click('#year-prev');
  assert.equal(await page.locator('#picker-year').textContent(), '2008年');
  await page.keyboard.press('Escape');
  assert.equal(await value(), '2008-10');
  await open();
  await page.click('#month-shortcuts [data-start-shortcut="2016-10"]');
  await page.click('#month-apply');await page.click('#generate');
  assert.ok((await page.evaluate(() => window.rollingQA.events())).every(event => event.window_start >= '2016-10-01'));
  assert.ok((await state()).account.start_date >= '2016-10-01');
  await open();
  await page.click('#month-shortcuts [data-start-shortcut="2026-09"]');
  assert.ok(await page.locator('#year-next').isDisabled());
  for (const month of [10, 11, 12]) assert.ok(await page.locator(`#month-grid [data-picker-month="${month}"]`).isDisabled());
  await page.click('#month-apply');await page.click('#generate');
  assert.equal(await value(), '2026-09');
  await open();
  await page.click('#month-shortcuts [data-start-shortcut="1991-01"]');
  assert.ok(await page.locator('#year-prev').isDisabled());
  await page.click('#month-apply');await page.click('#generate');
  assert.deepEqual(await state(), baseline);

  await open();
  await choose(2016, 9);
  await page.keyboard.press('ArrowRight');
  assert.equal(await page.locator('#month-selection').textContent(), '2016年10月');
  await page.keyboard.press('Tab');
  await page.keyboard.press('Tab');
  assert.equal(await page.evaluate(() => document.activeElement.id), 'month-apply');
  await page.keyboard.press('Enter');await page.click('#generate');
  assert.equal(await value(), '2016-10');
  await page.click('#reset');await page.click('#generate');
  assert.equal(await page.locator('#start-label').textContent(), '1991年1月');
  assert.deepEqual(await state(), baseline);

  for (const [width, height] of [[390, 844], [320, 640], [844, 390]]) {
    await page.setViewportSize({width, height});
    await open();
    await choose(2026, 9);
    await checkBounds();
    if (width === 390) await page.screenshot({path: output('month-picker-mobile-qa.png')});
    await page.click('#month-apply');await page.click('#generate');
    assert.equal(await value(), '2026-09');
    await open();
    await choose(2008, 10);
    await page.keyboard.press('Escape');
    assert.equal(await value(), '2026-09');
    await page.click('#reset');await page.click('#generate');
  }
  await page.setViewportSize({width: 1440, height: 1000});
  await open();
  await page.mouse.click(5, 5);
  assert.equal(await page.locator('#month-picker').isVisible(), false);
  assert.equal(await page.evaluate(() => document.body.style.overflow), '');
  assert.deepEqual(errors, []);
  console.log('月份选择器通过：确认/取消、快捷起点、月份边界、键盘、恢复筛选、事件与账户联动、桌面及手机布局');
} finally {
  await browser.close();
}
