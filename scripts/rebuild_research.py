import subprocess,sys,pathlib
ROOT=pathlib.Path(__file__).resolve().parents[1]
for script in ['analyze_multi_indices.py','test_account.py','backtest_account.py','build_site.py']:
 subprocess.run([sys.executable,str(ROOT/'scripts'/script)],cwd=ROOT,check=True)
