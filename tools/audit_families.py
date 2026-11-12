"""Restore exact registered engine sources beside original reports for native audits."""
import hashlib,json,os,shutil
from pathlib import Path
from tools.filesystem import link_or_copy

def read(p):return json.loads(p.read_bytes())
def digest(d):
 code={p.name:hashlib.sha256(p.read_bytes()).hexdigest()for p in sorted(d.glob('*.py'))}
 return hashlib.sha256(json.dumps(code,sort_keys=True).encode()).hexdigest()
def audits(a,scratch,catalog,run):
 original=a.data_root/'payload/originals/Q3_P0_18_proof';work=scratch/'audit-native'
 # Links are confined to temporary extracted data. Release tar members are regular files.
 shutil.copytree(original,work,copy_function=link_or_copy)
 for engine in (a.data_root/'payload/engines/pB').iterdir():
  if engine.is_dir():shutil.copytree(engine,work/'pB/cusp'/engine.name,copy_function=link_or_copy,dirs_exist_ok=True)
 engines={}
 for parent,dirs,files in os.walk(work):
  p=Path(parent)
  if p.name.startswith('eng')and any(n.endswith('.py')for n in files):engines.setdefault(digest(p),p)
 for c in catalog:
  rel=Path(c['id']).relative_to('Q3_P0_18_proof');case=work/rel;report=read(case/'box_report.json');code=report['code_sha256']
  if code not in engines:raise ValueError('No original registered engine with code '+code)
  engine=engines[code]
  for p in engine.iterdir():
   if p.is_file()and p.suffix=='.py':
    dst=case/p.name
    if dst.exists():dst.unlink()
    link_or_copy(p,dst)
  # The original auditors hash these shared JSON inputs beside every case.
  for name in ('support_discovery.json','support64_proposals.json','higher_bernstein_report.json','centered_base.json','normalizers64.json'):
   src=engine/name;dst=case/name
   if not src.is_file():raise ValueError('Missing registered engine input '+str(src))
   if dst.exists():
    if hashlib.sha256(dst.read_bytes()).digest()!=hashlib.sha256(src.read_bytes()).digest():raise ValueError('Existing original shared input differs '+c['id']+'/'+name)
   else:link_or_copy(src,dst)
  if digest(case)!=code:raise ValueError('Restored original case code mismatch '+c['id'])
 for fam,source,relative in [('s14','p14/cusp/audit14.py','p14/cusp/s14.json'),('s15','p15/cusp/audit15.py','p15/cusp/s15.json'),('s16','p16/cusp/audit16.py','p16/cusp/s16.json'),('small','cusp/audit18.py','cusp/small.json'),('gen30','cusp/audit18.py','cusp/gen30.json'),*[(f'pB{p}','pB/cusp/audit9.py',f'pB/cusp/pB{p}.json')for p in (10,11,12,13)]]:
  if a.family and fam!=a.family:continue
  args=[work/relative,'--quiet']
  if fam.startswith('pB'):args+=['--json',a.output/('audit-'+fam+'.json')]
  run('audit-'+fam,work/source,args,(work/source).parent)
