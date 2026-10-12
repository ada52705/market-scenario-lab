"""Unrealized marks must reconcile to the account without inventing completed trades."""
import argparse
import hashlib
import json
import math

from backtest_rolling import ROOT, events, run


def fixture(dates, closes):
    return {'id': 'fixture', 'name': '估值测试', 'release': '2020-01-01', 'daily': [
        {'date': date, 'open': close, 'close': close, 'high': close * 1.01, 'low': close * .99}
        for date, close in zip(dates, closes)
    ]}


def checks():
    dates = ['2020-01-27', '2020-01-28', '2020-01-29', '2020-01-30', '2020-01-31']
    asset = fixture(dates, [100, 100, 70, 80, 100])
    for cost in (0, 10, 100):
        account = run(asset, 3, 25, cost_bps=cost, capital=500000)
        trade = account['trades'][0]
        expected = 100 / 80 / (1 + cost / 10000) - 1
        assert trade['net_return'] is None and trade['exit_date'] is None
        assert trade['valuation_date'] == '2020-01-31' and trade['valuation_close'] == 100
        assert math.isclose(trade['unrealized_return'], expected, abs_tol=1e-12)
        assert math.isclose(trade['unrealized_pnl'], expected * 500000, abs_tol=1e-8)
        assert account['valuation']['realized_pnl'] == 0
        assert account['summary']['closed_trades'] == 0 and account['summary']['win_rate'] is None
        event = events(asset, 3, 25)[0]
        assert event['return'] is None and event['unrealized_return'] == .25
    mixed = fixture(dates + ['2020-03-02', '2020-03-03', '2020-03-04', '2020-03-05', '2020-03-06'],
                    [100, 100, 70, 80, 100, 90, 150, 100, 90, 110])
    account = run(mixed, 3, 25, cost_bps=10)
    assert account['summary']['closed_trades'] == 1 and account['summary']['open_trades'] == 1
    assert account['trades'][0]['unrealized_return'] is None
    assert math.isclose(account['summary']['pnl'], account['valuation']['realized_pnl'] + account['valuation']['unrealized_pnl'], abs_tol=1e-8)
    waiting = run(fixture(dates[:3], [100, 100, 70]), 3, 25)
    assert waiting['valuation']['position'] is None and waiting['valuation']['unrealized_pnl'] == 0
    assert events(fixture(dates[:3], [100, 100, 70]), 3, 25)[0]['valuation_date'] is None


def references(payload):
    cases = []
    for asset in payload['assets']:
        for basis in ('published', 'full'):
            for window in (3, 25):
                for months in (1, 3, 6, 12):
                    for threshold in payload['thresholds']:
                        signals = events(asset, window, threshold, basis, holding_months=months)
                        for cost in (0, 10):
                            account = run(asset, window, threshold, basis, cost_bps=cost, holding_months=months, signals=signals)
                            cases.append({'index_id': asset['id'], 'basis': basis, 'window': window,
                                          'holding_months': months, 'threshold': threshold, 'cost_bps': cost,
                                          'summary': account['summary'], 'valuation': account['valuation'],
                                          'event_marks': [[event['signal_date'], event['valuation_date'], event['valuation_close'], event['unrealized_return']]
                                                          for event in signals if event['status'] != '已完成']})
    return cases


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args()
    paths = [ROOT / 'data' / name for name in ('research.json', 'research.sqlite')]
    hashes = [hashlib.sha256(path.read_bytes()).hexdigest() for path in paths]
    checks()
    if args.json:
        print(json.dumps(references(json.loads(paths[0].read_text(encoding='utf-8'))), ensure_ascii=False, separators=(',', ':')))
    else:
        print('浮动估值边界通过：最新收盘、只扣买入成本、不虚构平仓、不进入胜率、盈亏拆分、待买入、原数据不变')
    assert hashes == [hashlib.sha256(path.read_bytes()).hexdigest() for path in paths]
