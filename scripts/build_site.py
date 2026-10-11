"""Build a static site from editable UI source and the verified research snapshot."""
import pathlib,json,shutil
ROOT=pathlib.Path(__file__).resolve().parents[1];target=ROOT/'public';target.mkdir(exist_ok=True)
p=json.loads((ROOT/'data/research.json').read_text())
for asset in p['assets']:
 # Full source differences remain in data/research.json and the raw archive.
 for key in ['differences','invalid_original_rows']:asset['validation'].pop(key,None)
html=(ROOT/'src/index.html').read_text().replace('__RESEARCH_DATA__',json.dumps(p,ensure_ascii=False,separators=(',',':')).replace('</','<\\/'))
js=(ROOT/'src/app.js').read_text();assert js.count('/* __ACCOUNT_MODULE__ */')==1;js=js.replace('/* __ACCOUNT_MODULE__ */',(ROOT/'src/account.js').read_text())
(target/'index.html').write_text(html);(target/'app.js').write_text(js);shutil.copy2(ROOT/'src/styles.css',target/'styles.css');(target/'.nojekyll').write_text('')
(target/'downloads').mkdir(exist_ok=True);shutil.copy2(ROOT/'artifacts/多指数四档急跌情景研究.xlsx',target/'downloads/research.xlsx');shutil.copy2(ROOT/'artifacts/中证500月跌20%_长期账户曲线.png',target/'downloads/account-curve.png')
print('Site built:',target,'snapshot size',len(html.encode('utf8')))
