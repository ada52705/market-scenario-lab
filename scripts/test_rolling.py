"""Boundary and execution fixtures for close-to-peak rolling drawdowns."""
import datetime as dt
import math

from backtest_rolling import add_month, events, run


def asset(closes, start='2020-01-27', release='2020-01-01'):
    date = dt.date.fromisoformat(start)
    rows = []
    for close in closes:
        while date.weekday() >= 5:
            date += dt.timedelta(days=1)
        rows.append({'date': date.isoformat(), 'open': close, 'close': close,
                     'high': close * 3, 'low': close * .9})
        date += dt.timedelta(days=1)
    return {'id': 'fixture', 'name': '测试', 'release': release, 'daily': rows}


a = asset([100, 100, 75, 74, 73, 100, 74, 73] + [73] * 30)
signals = events(a, 3, 25)
assert [event['signal_date'] for event in signals] == ['2020-01-30', '2020-02-04']
assert signals[0]['reference_date'] == '2020-01-28'  # Latest equal closing peak, not high.
assert signals[0]['window_start'] == '2020-01-28'
assert signals[0]['entry_date'] == '2020-01-31'
assert signals[0]['target_exit_date'] == '2020-02-29'
assert signals[0]['exit_date'] == '2020-03-02'
account = run(a, 3, 25)
assert account['summary']['accepted_signals'] == 1 and account['summary']['ignored_signals'] == 1
assert account['trades'][0]['exit_date'] == '2020-03-02'
assert account['daily'][0]['nav'] == 1
assert not events(asset([100, 100, 75]), 3, 25)  # Equal threshold never triggers.
for threshold in (10, 15, 20, 25):
    assert not events(asset([100, 100, 100 - threshold]), 3, threshold)
waiting = run(asset([100, 100, 70]), 3, 25)
assert waiting['summary']['waiting_signals'] == 1 and waiting['summary']['accepted_signals'] == 0
pending = run(asset([100, 100, 70, 80]), 3, 25, cost_bps=10)
assert pending['summary']['open_trades'] == 1 and pending['trades'][0]['exit_date'] is None
assert math.isclose(pending['summary']['final_nav'], 1 / 1.001)
assert add_month('2021-01-31') == '2021-02-28' and add_month('2020-12-31') == '2021-01-31'

prefix = asset([100, 100, 75, 74, 73, 100, 74, 73])
extended = asset([100, 100, 75, 74, 73, 100, 74, 73, 10000, 10])
fields = ('signal_date', 'signal_return', 'reference_date', 'reference_close', 'window_start')
before = [[event[field] for field in fields] for event in events(prefix, 3, 25)]
after = [[event[field] for field in fields] for event in events(extended, 3, 25)
         if event['signal_date'] <= prefix['daily'][-1]['date']]
assert before == after  # Future prices must not change earlier signals.
post_release = asset([1000, 1000, 100, 90, 80], release='2020-01-29')
assert not events(post_release, 3, 25, 'published')
assert events(post_release, 3, 25, 'full')
assert not events(post_release, 3, 25, 'full', '2020-02')

same_day = asset([100, 100, 70] + [80] * 48)
first = events(same_day, 3, 25)[0]
second = {**first, 'month': '2020-02', 'signal_date': '2020-02-28',
          'entry_date': first['exit_date'], 'target_exit_date': add_month(first['exit_date'])}
reentry = run(same_day, 3, 25, signals=[first, second])
assert reentry['summary']['accepted_signals'] == 2
assert reentry['trades'][0]['exit_date'] == reentry['trades'][1]['entry_date']
assert next(row for row in reentry['daily'] if row['date'] == first['exit_date'])['action'] == '卖出、买入'
print('滚动窗口边界通过：交易日计数、收盘高点、严格阈值、重新触发、无未来数据、发布范围、次日买入、一个日历月、忽略信号、同日再入场、未平仓与待买入')
