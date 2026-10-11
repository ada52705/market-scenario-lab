# 市场情景研究工作台

[在线访问](https://ada52705.github.io/market-scenario-lab/) · [研究口径](docs/研究说明.md) · [长期账户规则](docs/长期策略账户说明.md)

研究“自然月急跌后买入，持有三个月”的历史表现，并把单次事件研究与同一笔资金的长期回测分开呈现。界面、图表和研究说明使用简体中文。

![中证500默认案例的长期账户曲线](artifacts/中证500月跌20%_长期账户曲线.png)

## 当前功能

- 10个指数：上证综指、沪深300、中证500、中证1000、中证2000、上证50、深证成指、创业板指、中证红利、科创50。
- 四档月跌幅：严格超过10%、15%、20%、25%，不是从历史高点计算的动态回撤。
- 全历史含回溯、发布后完整月份、近十年、共同发布后区间；起始月份支持大窗口年月选择与常用起点。
- 单次事件胜率、平均收益、中位数、盈亏比、持有期最大回撤、月收益热图和持有路径。
- 单一资金账户的连续净值、累计盈亏、回撤、持仓区间、实际交易和现金空仓区间。
- 支持初始资金、单边成本、指数买入持有对照、逐日账户及事件CSV导出。

## 在另一台电脑继续开发

只需Git和Python 3.10以上；构建网站、重算研究均使用Python标准库，无需数据库服务或密钥。

```bash
git clone https://github.com/ada52705/market-scenario-lab.git
cd market-scenario-lab
python3 scripts/build_site.py
python3 -m http.server 8000 --directory public
```

浏览器打开 `http://localhost:8000`。Windows可以用 `python` 替代 `python3`。

| 想改什么 | 对应位置 |
|---|---|
| 页面结构、文案、按钮 | `src/index.html` |
| 页面样式、手机布局 | `src/styles.css` |
| 事件研究、筛选、热图 | `src/app.js` |
| 长期账户执行和曲线 | `src/account.js` |
| Python账户引擎、资金规则 | `scripts/backtest_account.py` |
| 日行情清洗、月份、事件指标 | `scripts/analyze_multi_indices.py` |
| 核验后的数据和数据库 | `data/` |
| 原始行情响应与来源 | `data/raw/` |
| 研究规则与覆盖区间 | `docs/` |

修改后重新运行构建，再提交并推送到 `main`。GitHub Actions会检查账户规则和320组参考结果，再自动发布GitHub Pages。无需手动上传网页。

```bash
python3 scripts/test_account.py
python3 scripts/check_snapshot.py
python3 scripts/build_site.py
git add .
git commit -m "改进工作台"
git push
```

## 重算与界面检查

从仓库保留的原始快照重算全部研究：

```bash
python3 scripts/rebuild_research.py
```

该操作更新事件底稿、SQLite和账户参考结果，再生成网站；Excel和曲线图片为已归档的快照，不会由这个命令重新生成。

界面验证是可选开发依赖，需要Node.js 22以上：

```bash
npm ci
npx playwright install chromium
python3 scripts/build_site.py
npm run test:events
npm run test:account
npm run test:month-picker
```

环境变量 `BROWSER_EXECUTABLE` 可指定本机已有Chrome路径。Python账户执行规则、320组参考结果和浏览器账户结果已分别核对。

## 数据与数据库

这是**固定行情快照**，不是实时行情。日行情截至2026-10-09，完整自然月截至2026-09。52,804条日行情来自中证指数公开接口、搜狐及腾讯；有效官方OHLC优先，来源差异和原始数据保留。

`data/research.sqlite` 为真实SQLite数据库，包含指数目录、日行情、月收益、事件与路径、情景汇总和研究元数据。`account_summary`保存160组零成本账户场景，`account_daily`和`account_trades`保存默认中证500案例；其他账户场景在页面即时重算并可导出。

新增指数或刷新行情时，应保留新的原始批次、核验OHLC及交易日、更新指数目录与研究日期，再重算。`fetch_multi_indices.py`保留了早期第三方抓取流程，但正式刷新还需补充官方行情及质量核验。网站自动发布只更新代码与已提交快照，不自动抓取行情。

指数发布前数据明确标为回溯，不视为当时可交易表现。科创50不足十年；中证2000实际发布后的历史较短。价格指数不含股息；默认未扣费用，不等同于ETF或私募实盘表现。

## 账户执行规则

空仓时，月末确认信号，次月首个交易日开盘全仓买入；实际买入日加三个日历月后首个交易日开盘卖出。持仓期间忽略新信号，同日开盘允许先卖再买；退出后保持现金，不计息。未平仓按最新收盘估值。阈值严格比较，不四舍五入后判断。

单次事件可能重叠，四档条件也相互包含；账户净值使用同一笔资金滚动复投。历史胜率、单次平均收益和长期账户收益回答不同问题。

## 发布说明

仓库及GitHub Pages均公开，朋友访问网站不需要登录。仅`public/`构建结果部署到网站，原始数据、脚本及数据库供仓库中的研究与开发使用。页面不包含客户资料或账号凭据。源码未设置开放源代码许可证，第三方行情数据权利仍归原提供方；正式商业再分发应落实相应授权。
