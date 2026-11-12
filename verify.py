#!/usr/bin/env python3
"""Single entry point for preliminary release integrity and numerical verification."""
import argparse,collections,hashlib,importlib.metadata,json,os,platform,shutil,subprocess,sys,tempfile,time
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
THREADS=('BLIS_NUM_THREADS','FLINT_NUM_THREADS','MKL_NUM_THREADS','NUMBA_NUM_THREADS','NUMEXPR_NUM_THREADS','OMP_NUM_THREADS','OMP_THREAD_LIMIT','OPENBLAS_NUM_THREADS','VECLIB_MAXIMUM_THREADS')
for name in THREADS:os.environ[name]='1'
for name in ('PYTHONOPTIMIZE','PYTHONPATH','PYTHONHOME','PYTHONPYCACHEPREFIX'):os.environ.pop(name,None)
os.environ['PYTHONDONTWRITEBYTECODE']='1';os.environ['PYTHONNOUSERSITE']='1'
def read(p):return json.loads(p.read_bytes())
def need(ok,msg):
 if not ok:raise RuntimeError(msg)
def sha(p):
 with p.open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def dependencies():
 need(platform.python_version()=='3.11.15','Use pinned CPython 3.11.15')
 for line in (HERE/'requirements.lock').read_text().splitlines():
  if not line or line.startswith('#'):continue
  name,version=line.split('==');need(importlib.metadata.version(name)==version,'Dependency pin mismatch: '+name)

def resources(path):
 disk=shutil.disk_usage(path).free
 if sys.platform=='darwin':
  import re
  text=subprocess.check_output(['vm_stat'],text=True);page=int(re.search(r'page size of (\d+)',text).group(1))
  values={k:int(v.strip().rstrip('.'))for k,v in re.findall(r'^(Pages [^:]+):\s+(\d+\.)',text,re.M)}
  available=page*sum(values.get(k,0)for k in ('Pages free','Pages inactive','Pages speculative'))
 elif sys.platform=='linux':
  import re
  meminfo=Path('/proc/meminfo').read_text()
  match=re.search(r'^MemAvailable:\s+(\d+)\s+kB$',meminfo,re.M)
  need(match is not None,'Linux /proc/meminfo has no MemAvailable value')
  available=int(match.group(1))*1024
 else:
  raise RuntimeError('Numerical verification supports Linux and macOS; Windows is not supported')
 need(disk>=8*2**30,'Less than 8 GiB disk reserve before next numerical process')
 need(available>=int(3.5*2**30),'Less than 3.5 GiB estimated available RAM before next numerical process')
 return {'free_disk_bytes':disk,'estimated_available_RAM_bytes':available,'one_numerical_process':True}

def main():
 ap=argparse.ArgumentParser(description=__doc__)
 ap.add_argument('--data-root',type=Path,default=HERE,help='Directory containing extracted payload/')
 ap.add_argument('--output',type=Path,default=HERE/'verification-output')
 ap.add_argument('--suite',choices=['all','cusp','small','exact','outer','globals','audits','three-three-n','integrity'],default='all')
 ap.add_argument('--family',choices=['s14','s15','s16','small','gen30','pB10','pB11','pB12','pB13'])
 ap.add_argument('--case',help='Case basename, for example b0073 (requires --family)')
 ap.add_argument('--smoke',action='store_true',help='Representative subset only; never a full acceptance result')
 a=ap.parse_args();need(sys.platform in ('linux','darwin'),'verify.py supports Linux and macOS; Windows is not supported');need(__debug__ and sys.flags.optimize==0,'Do not use -O');need(not a.case or a.family,'--case requires --family')
 a.data_root=a.data_root.resolve();a.output=a.output.resolve();a.output.mkdir(parents=True,exist_ok=True)
 need(not (a.output/'result.json').exists(),'Use a fresh --output directory; existing results are preserved')
 need(not (a.output/'RUNNING').exists(),'Output contains a running or interrupted verification; use a fresh --output directory')
 (a.output/'RUNNING').write_text(str(os.getpid())+'\n')
 result={'schema':'preferred-interval-verification-v1','status':'RUNNING','suite':a.suite,'smoke':a.smoke,'full_Lean_formalization':'in progress','checks':[],'verifier_sha256':sha(Path(__file__)),'started_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}
 def save(): (a.output/'result.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
 save()
 def run(label,source,args=(),cwd=None,mode='script',envextra=None):
  number=len(result['checks']);log=a.output/f'{number:04d}-{label}.log';started=time.monotonic();source_digest=sha(source);launcher_digest=sha(HERE/'adapters/execute.py')
  resource_snapshot=resources(a.output)
  env=os.environ.copy();env['NUMBA_CACHE_DIR']=str(a.output/'numba-cache');env.update(envextra or {})
  command=[sys.executable,'-I','-B',str(HERE/'adapters/execute.py'),str(source),mode,*map(str,args)]
  with log.open('x')as f:
   p=subprocess.run(command,cwd=cwd,env=env,stdout=f,stderr=subprocess.STDOUT)
  row={'label':label,'exit_code':p.returncode,'seconds':time.monotonic()-started,'log':log.name,'source_sha256':source_digest,'launcher_sha256':launcher_digest,'source_unchanged_during_execution':sha(source)==source_digest,'assertions_enabled':True,'threads':1,'resources_before':resource_snapshot}
  if p.returncode==0:
   from tools.native_reports import EXACT_LABELS,validate_exact_report
   if label in EXACT_LABELS:
    try:row['native_report_validation']=validate_exact_report(a.output/(label+'.json'),label)
    except Exception as e:row['native_report_error']=repr(e)
  result['checks'].append(row)
  if p.returncode==0 and cwd is not None and source.stem in ('vpc14','vpc15','vpc16','vpc18','overlap14','overlap15','overlap16','overlap18'):
   report=Path(cwd)/(source.stem+'.json')
   if report.is_file():
    native=a.output/'native';native.mkdir(exist_ok=True);shutil.copyfile(report,native/(label+'.json'))
  if p.returncode==0 and cwd is not None and label in('newrefl14','newrefl15','newrefl16'):
   report=Path(cwd)/(label+'.json');need(report.is_file(),'Missing fresh fixed-domain polar report')
   native=a.output/'native';native.mkdir(exist_ok=True);shutil.copyfile(report,native/report.name)
  save();print(label,'PASS'if p.returncode==0 else'FAIL',round(row['seconds'],2),flush=True);need(p.returncode==0 and row['source_unchanged_during_execution']and 'native_report_error'not in row,'Failed '+label+'; inspect '+str(log))
 try:
  if a.suite=='integrity':
   import tools.fetch_assets as fa
   result['integrity']=fa.verify_payload(HERE,a.data_root)
  else:
   dependencies()
   if a.suite=='all' and not(a.smoke or a.family or a.case):
    from tools.fetch_assets import verify_payload
    result['integrity']=verify_payload(HERE,a.data_root);save()
   catalog=read(HERE/'manifests/cases-v1.json')['cases']
   with tempfile.TemporaryDirectory(prefix='release-replay-',dir=a.output)as temp:
    scratch=Path(temp)
    if a.suite in ('all','cusp'):
     selected=[c for c in catalog if(not a.family or c['family']==a.family)and(not a.case or c['box']==a.case)]
     need(selected,'No matching cases')
     if a.smoke:
      from tools.selection import representatives
      selected=representatives(selected,a.data_root)
     result['selected_cases']=[c['id']for c in selected];save()
     for c in selected:
      fam,box=c['family'],c['box'];case=scratch/fam/box;work=case/'run';shutil.copytree(a.data_root/c['run'],work)
      original=a.data_root/c['original'];weights=a.data_root/c['weights']
      shared=a.data_root/'payload/originals/Q3_P0_18_proof/cusp/v4'
      for name in ('support_discovery.json','support64_proposals.json','higher_bernstein_report.json'):
       if not(work/name).exists():shutil.copyfile(shared/name,work/name)
      if c.get('fresh_bank_mapping'):shutil.copyfile(a.data_root/c['fresh_bank_mapping'],case/'fresh-bank-mapping.json')
      run(f'{fam}-{box}-basic',HERE/'adapters/replay_basic.py',[original,weights],work,'basic')
      if fam.startswith('pB'):
       order=int(fam[2:]);registry=read(a.data_root/f'payload/originals/Q3_P0_18_proof/pB/cusp/engines_{order}.json')
       code=read(original/'box_report.json')['code_sha256']
       levels=[level for level,row in registry.items()if row['code']==code];need(len(levels)==1,'One original registered engine required')
       engine=a.data_root/f'payload/engines/pB/eng9_{order}_{levels[0]}'
       (scratch/'restored-engines.json').write_text(json.dumps({'engines':[{'order':order,'level':levels[0],'code_sha256':code,'engine':str(engine)}]})+'\n')
       choices=['replay9-freshbank-pB-v2.py','replay9-freshbank-v1.py','replay9-SK-v2.py','replay9-SK-v1.py','replay9.py']
       replay=next((work/n for n in choices if(work/n).exists()),None);need(replay is not None,'Missing pB replay')
       checks=['check_saved_tail_time_path_pB_v2.py','check_saved_no_tail_freshbank_v1.py','check_saved_no_tail_pB13_v1.py']
       helper=next((work/n for n in checks if(work/n).exists()),None);need(helper is not None,'Missing pB time/path replay')
      else:
       tag={'s14':'p14','s15':'p15','s16':'p16','small':'p18','gen30':'p18'}[fam]
       number=tag[1:];cusp=original.parent.parent
       replay=(HERE/'adapters/native/p14-replay14-recorded-k.py') if fam=='s14' else cusp/'replay'/f'replay{number}.py'
       spec=read(work/'box.json');tails=any(z is not None for z in spec.get('zeta',[['-1/13','1/13']]*3))
       name='check_saved_tail_case.py'if tails else'check_saved_no_tail_case.py'
       # p15 has a separate original multivariate tail checker.
       if fam=='s15'and tails and read(work/'tm_sources64_s0.json')['dimension']>1:name='check_saved_nd_tail_case.py'
       helper=HERE/'adapters/native'/(tag+'-'+name)
      # Keep the engine's complete .py census unchanged. execute.py redirects
      # only the replay output ROOT after compiling its unchanged source bytes.
      run(f'{fam}-{box}-support-extended',replay,[original],work,'replay')
      run(f'{fam}-{box}-tails-time-path',helper,[original],work)
      if fam.startswith('pB'):run(f'{fam}-{box}-polar',HERE/'adapters/replay_polar.py',[original,a.data_root/f'payload/cusp/{fam}/{box}/fresh-polar'],work)
      native=a.output/'native'/(fam+'-'+box);native.mkdir(parents=True,exist_ok=True)
      for pattern in ('replay*.json','saved-time-path-result.json','replayed-polar.ckpt'):
       for report in work.glob(pattern):shutil.copyfile(report,native/report.name)
      shutil.rmtree(case)
    if a.suite in ('all','small','exact','outer','globals','audits','three-three-n'):
     from tools.suites import dispatch
     dispatch(a,scratch,catalog,run)
  if a.suite in ('all','exact'):
   from tools.native_reports import validate_exact_suite
   result['native_exact_reports']=validate_exact_suite(a.output,a.smoke)
  result['status']='REQUESTED_SUBSET_PASSED'if a.smoke or a.family or a.case or a.suite!='all'else'ALL_RELEASE_NUMERICAL_CHECKS_PASSED'
 except BaseException as e:
  result['status']='FAILED';result['error']=repr(e);raise
 finally:
  result['completed_utc']=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime());save();(a.output/'RUNNING').unlink()
if __name__=='__main__':main()
