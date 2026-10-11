import json,pathlib,math
from backtest_account import run
ROOT=pathlib.Path(__file__).resolve().parents[1];p=json.loads((ROOT/'data/research.json').read_text());assets={a['id']:a for a in p['assets']};qa=json.loads((ROOT/'data/account-validation.json').read_text())
for case in qa:
 actual=run(assets[case['index_id']],case['threshold'],case['basis'],cost_bps=case['cost_bps'])['summary'];expected=case['summary']
 for key in ['final_nav','total_return','pnl','cagr','max_drawdown','accepted_signals','closed_trades','open_trades','ignored_signals','win_rate','exposure','held_days','cash_days','benchmark_return']:
  if actual[key] is None and expected[key] is None:continue
  assert math.isclose(actual[key],expected[key],rel_tol=1e-11,abs_tol=1e-11),(case['index_id'],key)
print('Validated',len(qa),'account scenarios')
