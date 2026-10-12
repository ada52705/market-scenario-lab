"""Rolling close-to-peak signals on the retained snapshot; original monthly data stays intact."""
import argparse
import bisect
import calendar
import datetime as dt
import json
import math
import pathlib

from backtest_account import run as run_account

ROOT = pathlib.Path(__file__).resolve().parents[1]
WINDOWS = (3, 5, 10, 20, 25)


def add_month(date, months=1):
    date = dt.date.fromisoformat(date)
    offset = date.month - 1 + months
    year, month = date.year + offset // 12, offset % 12 + 1
    return dt.date(year, month, min(date.day, calendar.monthrange(year, month)[1])).isoformat()


def scope_rows(asset, basis='published', start='1991-01'):
    beginning = start + '-01'
    if basis in ('published', 'common'):
        beginning = max(beginning, asset['release'])
    if basis == 'recent10':
        beginning = max(beginning, '2016-10-01')
    if basis == 'common':
        beginning = max(beginning, '2023-09-01')
    return [row for row in asset['daily'] if row['date'] >= beginning]


def events(asset, window=25, threshold=20, basis='published', start='1991-01', holding_months=1):
    assert holding_months in (1, 3, 6, 12)
    assert window in WINDOWS and threshold in (10, 15, 20, 25)
    rows = scope_rows(asset, basis, start)
    dates = [row['date'] for row in rows]
    result, was_below = [], False
    for index in range(window - 1, len(rows)):
        observed = rows[index - window + 1:index + 1]
        # On equal peaks, use the most recent date. No future observation enters the window.
        peak = max(observed, key=lambda row: (row['close'], row['date']))
        signal = rows[index]
        change = signal['close'] / peak['close'] - 1
        # Compare prices directly; subtracting a floating ratio can misclassify equality.
        below = signal['close'] * 100 < peak['close'] * (100 - threshold)
        crossing = below and not was_below
        was_below = below
        if not crossing:
            continue
        event = {
            'month': signal['date'][:7], 'signal_date': signal['date'],
            'signal_return': change, 'signal_close': signal['close'],
            'reference_date': peak['date'], 'reference_close': peak['close'],
            'window_start': observed[0]['date'], 'window_end': signal['date'],
            'window_days': window, 'published': observed[0]['date'] >= asset['release'],
            'entry_date': None, 'entry_open': None, 'target_exit_date': None,
            'exit_date': None, 'exit_open': None, 'status': '待买入', 'return': None,
            'holding_calendar_days': None, 'holding_trading_days': 0,
            'max_drawdown': None, 'worst_intraday_return': None,
            'valuation_date': None, 'valuation_close': None, 'unrealized_return': None,
        }
        if index + 1 < len(rows):
            entry = rows[index + 1]
            target = add_month(entry['date'], holding_months)
            exit_index = bisect.bisect_left(dates, target)
            exit_row = rows[exit_index] if exit_index < len(rows) else None
            held = rows[index + 1:exit_index]
            values = [entry['open']] + [row['close'] for row in held]
            if exit_row:
                values.append(exit_row['open'])
            high, drawdown = values[0], 0
            for value in values:
                high = max(high, value)
                drawdown = min(drawdown, value / high - 1)
            lows = [row['low'] for row in held if row.get('low') is not None]
            event.update(
                entry_date=entry['date'], entry_open=entry['open'], target_exit_date=target,
                exit_date=exit_row['date'] if exit_row else None,
                exit_open=exit_row['open'] if exit_row else None,
                status='已完成' if exit_row else '观察中',
                valuation_date=None if exit_row else rows[-1]['date'],
                valuation_close=None if exit_row else rows[-1]['close'],
                unrealized_return=None if exit_row else rows[-1]['close'] / entry['open'] - 1,
                holding_calendar_days=(dt.date.fromisoformat(exit_row['date']) - dt.date.fromisoformat(entry['date'])).days if exit_row else None,
                holding_trading_days=len(held), max_drawdown=drawdown,
                worst_intraday_return=min(lows) / entry['open'] - 1 if lows and len(lows) == len(held) else None,
            )
            event['return'] = exit_row['open'] / entry['open'] - 1 if exit_row else None
        result.append(event)
    return result


def run(asset, window=25, threshold=20, basis='published', start='1991-01', cost_bps=0, capital=1000000, signals=None, holding_months=1):
    rows = scope_rows(asset, basis, start)
    signals = events(asset, window, threshold, basis, start, holding_months) if signals is None else signals
    if not rows:
        return {'summary': None, 'daily': [], 'points': [], 'trades': [], 'ignored': [], 'valuation': None}
    # Adapt the new signal calendar to the established single-capital execution engine.
    adapted = [{**event, 'month': event['signal_date'], 'monthly_return': event['signal_return']}
               for event in signals if event['entry_date']]
    account = run_account({**asset, 'daily': rows, 'monthly': [{
        'month': rows[0]['date'][:7], 'first_date': rows[0]['date'],
        'monthly_return': 0, 'complete': True, 'published': True,
    }], 'all_month_events': adapted}, threshold, 'full', rows[0]['date'][:7], cost_bps, capital)
    account['summary'].update(basis=basis, signal_mode='rolling', window_days=window, holding_months=holding_months,
                              waiting_signals=sum(event['entry_date'] is None for event in signals))
    by_date = {event['signal_date']: event for event in signals}
    for trade in account['trades']:
        event = by_date[trade['signal_date']]
        trade['signal_month'] = trade['signal_date'][:7]
        trade['signal_return'] = trade.pop('monthly_return')
        for field in ('reference_date', 'reference_close', 'signal_close', 'window_start', 'window_days'):
            trade[field] = event[field]
    for ignored in account['ignored']:
        ignored['signal_date'] = ignored['signal_month']
        ignored['signal_month'] = ignored['signal_date'][:7]
    # Open trades are marked after the path calculation, without a hypothetical exit fee.
    latest_nav = account['daily'][-1]['nav']
    position = None
    for trade in account['trades']:
        trade.update(valuation_date=None, valuation_close=None, nav_at_valuation=None,
                     unrealized_return=None, unrealized_pnl=None)
        if trade['status'] == '持仓中':
            position = trade
            trade.update(valuation_date=rows[-1]['date'], valuation_close=rows[-1]['close'],
                         nav_at_valuation=latest_nav,
                         unrealized_return=latest_nav / trade['nav_before_entry'] - 1,
                         unrealized_pnl=(latest_nav - trade['nav_before_entry']) * capital)
    account['valuation'] = {
        'asof': rows[-1]['date'],
        'realized_pnl': sum((trade['nav_after_exit'] - trade['nav_before_entry']) * capital
                            for trade in account['trades'] if trade['status'] == '已平仓'),
        'unrealized_pnl': position['unrealized_pnl'] if position else 0,
        'position': position,
    }
    return account


def references():
    payload = json.loads((ROOT / 'data/research.json').read_text(encoding='utf-8'))
    cases = []
    for asset in payload['assets']:
        for basis in ('published', 'full', 'recent10', 'common'):
            for window in WINDOWS:
                for threshold in payload['thresholds']:
                    signals = events(asset, window, threshold, basis)
                    finished = [event for event in signals if event['status'] == '已完成']
                    for cost in (0, 10):
                        account = run(asset, window, threshold, basis, cost_bps=cost, signals=signals)
                        returns = [(1 + event['return']) * (1 - cost / 10000) / (1 + cost / 10000) - 1 for event in finished]
                        cases.append({
                            'index_id': asset['id'], 'basis': basis, 'window': window,
                            'threshold': threshold, 'cost_bps': cost, 'summary': account['summary'],
                            'event_count': len(signals), 'completed_count': len(finished),
                            'win_rate': sum(value > 0 for value in returns) / len(returns) if returns else None,
                            'mean_return': sum(returns) / len(returns) if returns else None,
                            'signals': [[event['signal_date'], event['reference_date'], event['entry_date'], event['exit_date']] for event in signals] if cost == 0 else None,
                        })
    return cases


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--write-reference', action='store_true')
    args = parser.parse_args()
    cases = references()
    target = ROOT / 'data/rolling-validation.json'
    if args.write_reference:
        target.write_text(json.dumps(cases, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    else:
        expected = json.loads(target.read_text(encoding='utf-8'))
        assert len(expected) == len(cases)
        for actual, reference in zip(cases, expected):
            for field in actual:
                if field == 'summary':
                    if actual[field] is None or reference[field] is None:
                        assert actual[field] == reference[field]
                        continue
                    for key, value in actual[field].items():
                        other = reference[field][key]
                        assert math.isclose(value, other, rel_tol=1e-10, abs_tol=1e-10) if isinstance(value, float) else value == other, (actual['index_id'], field, key)
                elif isinstance(actual[field], float):
                    assert math.isclose(actual[field], reference[field], rel_tol=1e-10, abs_tol=1e-10)
                else:
                    assert actual[field] == reference[field], (actual['index_id'], field)
    print('Validated', len(cases), 'rolling account and event scenarios')
