"""Require affirmative native exact reports, independently of process exit status."""
import hashlib,json
from pathlib import Path
EXACT_LABELS=('N','S-exact','F13-exact','F-A1-10','F-A1-11','F-A1-12')
def need(condition,message):
 if not condition:raise RuntimeError(message)
def validate_exact_report(path,label):
 need(label in EXACT_LABELS,'Unknown native exact report label')
 path=Path(path)
 def nonfinite(value):raise RuntimeError('Nonfinite native report value: '+value)
 content=path.read_bytes();r=json.loads(content,parse_constant=nonfinite)
 expected='ALL_PREMISES_FOR_P_10_TO_13_VERIFIED'if label=='N'else'F13_KERNELS_VERIFIED'if label=='F13-exact'else'STRIP_KERNELS_VERIFIED'
 need(r.get('status')==expected,'Native report did not verify '+label)
 rows=r['certificates'];count=len(rows)
 need(count>0 and len({x['name']for x in rows})==count,'Empty or duplicate native exact census: '+label)
 if label=='N':
  need(r.get('complete')is True,'Partial N report is not complete')
  census=r['census']['scalar_domain_obligations']
 else:
  need(r.get('failed')==[],'Native exact report has failed obligations: '+label)
  need(r['expected_obligations']==count,'Incomplete native exact report: '+label)
  census=r['census']['obligations']
 need(type(census)is int and census==count,'Native exact census mismatch: '+label)
 return {'label':label,'report':path.name,'sha256':hashlib.sha256(content).hexdigest(),'obligations':count,'status':r['status']}
def validate_exact_suite(output,smoke=False):
 labels=('S-exact',)if smoke else EXACT_LABELS
 rows=[validate_exact_report(Path(output)/(label+'.json'),label)for label in labels]
 count=sum(r['obligations']for r in rows)
 need(smoke or count==895,'Full native exact suite must contain 895 obligations')
 return {'status':'ALL_NATIVE_EXACT_REPORTS_AFFIRMATIVE','smoke':smoke,'obligations':count,'reports':rows}
