"""Calendar holding options, independent account references, and immutable snapshot checks."""
import argparse
import bisect
import datetime as dt
import hashlib
import json

from backtest_account import eligible, run as monthly_account
from backtest_rolling import ROOT, WINDOWS, add_month, events, run as rolling_account

PERIODS = (1, 3, 6, 12)


def monthly_events(asset, months):
    if months == 3:
        return asset['all_month_events']
    rows = asset['daily']
    dates = [row['date'] for row in rows]
    result = []
    for original in asset['all_month_events']:
        event = dict(original)
        if not event['entry_date']:
            result.append(event)
            continue
        first = bisect.bisect_left(dates, event['entry_date'])
        target = add_month(event['entry_date'], months)
        last = bisect.bisect_left(dates, target)
        exit_row = rows[last] if last < len(rows) else None
        held = rows[first:last]
        values = [event['entry_open']] + [row['close'] for row in held]
        if exit_row:
            values.append(exit_row['open'])
        high, drawdown = values[0], 0
        for value in values:
            high = max(high, value)
            drawdown = min(drawdown, value / high - 1)
        lows = [row['low'] for row in held if row.get('low') is not None]
        event.update(
            target_exit_date=target, exit_date=exit_row['date'] if exit_row else None,
            exit_open=exit_row['open'] if exit_row else None,
            status='已完成' if exit_row else '观察中',
            holding_calendar_days=(dt.date.fromisoformat(exit_row['date']) - dt.date.fromisoformat(event['entry_date'])).days if exit_row else None,
            holding_trading_days=len(held), max_drawdown=drawdown,
            worst_intraday_return=min(lows) / event['entry_open'] - 1 if lows and len(lows) == len(held) else None,
        )
        event['return'] = exit_row['open'] / event['entry_open'] - 1 if exit_row else None
        result.append(event)
    return result


def checks(payload):
    assert add_month('2024-02-29', 12) == '2025-02-28'
    assert add_month('2023-11-30', 3) == '2024-02-29'
    assert add_month('2023-08-31', 6) == '2024-02-29'
    assert add_month('2023-01-31', 1) == '2023-02-28'
    for asset in payload['assets']:
        before = json.dumps(asset, ensure_ascii=False)
        dates = [row['date'] for row in asset['daily']]
        reference_signals = None
        for months in PERIODS:
            monthly = monthly_events(asset, months)
            rolling = events(asset, 25, 20, holding_months=months)
            signal_dates = [(event['signal_date'], event['reference_date']) for event in rolling]
            if reference_signals is None:
                reference_signals = signal_dates
            assert reference_signals == signal_dates, '持有期不得改变信号识别'
            for event in monthly + rolling:
                if not event['entry_date']:
                    continue
                assert event['target_exit_date'] == add_month(event['entry_date'], months)
                index = bisect.bisect_left(dates, event['target_exit_date'])
                assert event['exit_date'] == (dates[index] if index < len(dates) else None)
                assert (event['status'] == '已完成') == (event['exit_date'] is not None)
        assert json.dumps(asset, ensure_ascii=False) == before, '不得修改原始研究数据'


def references(payload):
    result = []
    fields = ('signal_date', 'entry_date', 'target_exit_date', 'exit_date', 'status',
              'return', 'max_drawdown', 'worst_intraday_return', 'holding_trading_days')
    for asset in payload['assets']:
        for months in PERIODS:
            monthly = monthly_events(asset, months)
            for basis in ('published', 'full', 'recent10', 'common'):
                for window in (0, *WINDOWS):
                    for threshold in payload['thresholds']:
                        signals = (events(asset, window, threshold, basis, holding_months=months) if window
                                   else [event for event in monthly if eligible(event, basis, '1991-01') and event['monthly_return'] < -threshold / 100])
                        for cost in (0, 10):
                            account = (rolling_account(asset, window, threshold, basis, cost_bps=cost, signals=signals, holding_months=months) if window
                                       else monthly_account({**asset, 'all_month_events': monthly}, threshold, basis, cost_bps=cost))
                            result.append({
                                'index_id': asset['id'], 'basis': basis, 'window': window,
                                'threshold': threshold, 'cost_bps': cost, 'holding_months': months,
                                'summary': account['summary'],
                                'trades': [[trade['entry_date'], trade['target_exit_date'], trade['exit_date'], trade['net_return']] for trade in account['trades']],
                                'events': [[event.get(field) for field in fields] for event in signals] if cost == 0 else None,
                            })
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--json', action='store_true', help='输出浏览器独立核对参考，不写入数据文件')
    args = parser.parse_args()
    paths = [ROOT / 'data' / name for name in ('research.json', 'research.sqlite')]
    hashes = [hashlib.sha256(path.read_bytes()).hexdigest() for path in paths]
    payload = json.loads(paths[0].read_text(encoding='utf-8'))
    checks(payload)
    if args.json:
        print(json.dumps(references(payload), ensure_ascii=False, separators=(',', ':')))
    else:
        print('四档持有期检查通过：月末、闰年、跨年、首个交易日卖出、信号不变、未完成事件和原始数据不变')
    assert hashes == [hashlib.sha256(path.read_bytes()).hexdigest() for path in paths]
