"""Dispatch to native exact/interval family verifiers; no discovery commands."""
import json,os,shutil
from pathlib import Path
from tools.filesystem import link_or_copy
HERE=Path(__file__).resolve().parents[1]
def read(p):return json.loads(p.read_bytes())
def copy_native(src,dst):
 # Source-specific lookup layout is preserved; prior checkpoint caches are omitted.
 shutil.copytree(src,dst,ignore=shutil.ignore_patterns('__pycache__','*.pyc','*ckpt*','*checkpoint*'))
 return dst

def dispatch(a,scratch,catalog,run):
 original=a.data_root/'payload/originals';small=original/'Q3_small_P0_p10_13';large=original/'Q3_P0_18_proof'
 if a.suite in ('all','small'):
  work=copy_native(small,scratch/'small-native');S=work/'S_strip_typeA';C=work/'CF_cusp_and_families';F=work/'F13_family13'
  groups=[('S',S/'verify_strip.py',sorted((S/'certs').glob('*.npz'))),('C',C/'verify_cusp.py',sorted((C/'certs').glob('*.npz'))),('branch',C/'verify_branch.py',sorted((C/'certs').glob('*.npz'))+sorted((C/'certs_ord30').glob('*.npz')))]
  expected={'S':116,'C':312,'branch':313}
  for tag,source,files in groups:
   assert len(files)==expected[tag],(tag,len(files))
   for cert in (files[:1]if a.smoke else files):
    if tag=='branch':run(tag+'-'+cert.stem,HERE/'adapters/replay_branch.py',[source,cert],source.parent)
    else:run(tag+'-'+cert.stem,source,[cert],source.parent)
  ordered=list((C/'certs_ord30').glob('*.npz'));assert len(ordered)==1
  run('C-order30',C/'verify_cusp_ord.py',[ordered[0]],C)
  families=sorted((C/'fam_certs').glob('*.npz'));assert len(families)==4
  run('F-families',C/'fam_replay.py',[a.output/'family-reports',*(families[:1]if a.smoke else families)],C)
  run('F13',F/'fam13.py',['verify',F/'fam_13_13.npz',a.output/'F13.json'],F)
  for name in ('t_corner.py','t_fail.py'):run('F13-'+name[:-3],F/name,[],F)
  for section in ('common','boundary'):run('A-ref-'+section,work/'A_ref/verify.py',['--section',section,'--output',a.output/('A-ref-'+section+'.json')],work/'A_ref')
 if a.suite in ('all','exact'):
  # Native exact verifiers with their saved covers (895 obligations in six reports).
  work=copy_native(small,scratch/'exact-native')
  jobs=[('N',work/'N_canonical/verify_10_13.py',['--jobs','1','--covers',work/'N_canonical/covers_10_13.json']),
        ('S-exact',work/'S_strip_typeA/exact/strip_kernels.py',['--p','10,11,12','--jobs','1','--mode','prop','--covers',work/'S_strip_typeA/exact/covers_prop.json']),
        ('F13-exact',work/'F13_family13/f13_kernels.py',['--jobs','1','--covers',work/'F13_family13/covers_f13.json'])]
  for p in (10,11,12):jobs.append((f'F-A1-{p}',work/'CF_cusp_and_families/exact_A1/strip_kernels.py',['--p',str(p),'--jobs','1','--mode','sliver','--pieces','A1','--covers',work/f'CF_cusp_and_families/exact_A1/covers_sliver_{p}_A1.json']))
  # Smoke runs only the S strip report (exact integer format), not all 895 obligations.
  if a.smoke:jobs=jobs[1:2]
  for label,source,args in jobs:run(label,source,[*args,'--output',a.output/(label+'.json')],source.parent)
 if a.suite in ('all','outer'):
  for family in ('p14','p15','p16','p18'):
   rel='outer'if family=='p18'else family+'/outer'
   # One adapter applies the native exact leaf tests and cover check to all four domains.
   src=large/rel
   work=copy_native(src,scratch/('outer-'+family));run('outer-'+family,HERE/'adapters/outer_leaves.py',[],work)
 if a.suite in ('all','globals'):
  context=scratch/'global-native'
  shutil.copytree(large,context,copy_function=link_or_copy,ignore=shutil.ignore_patterns('__pycache__','*.pyc','*ckpt*','*checkpoint*'))
  # Native global scripts write only in these directories. Break their links
  # before execution so extracted original reports remain immutable.
  writable=[context/'appB',context/'pB/common',context/'pB/maintext']
  for p in (14,15,16):writable += [context/f'p{p}/appB',context/f'p{p}/maintext']
  for directory in writable:
   for path in directory.rglob('*'):
    if path.is_file():
     source=large/path.relative_to(context);path.unlink();shutil.copyfile(source,path)
  for engine in (a.data_root/'payload/engines/pB').iterdir():
   if engine.is_dir():shutil.copytree(engine,context/'pB/cusp'/engine.name,copy_function=link_or_copy,dirs_exist_ok=True)
  for p in (14,15,16,18):
   work=context/('appB'if p==18 else f'p{p}/appB')
   # The smoke scope checks the complete nine-block peripheral verifier on D14;
   # the full suite checks every domain and all fixed-domain polar traces.
   if not a.smoke or p==14:run(f'vpc{p}',work/f'vpc{p}.py',[],work)
   run(f'overlap{p}',work/f'overlap{p}.py',[],work)
   if p!=18 and not a.smoke:
    run(f'newrefl{p}',HERE/'adapters/replay_global_polar.py',[work/f'newrefl{p}.py',large/f'p{p}/appB/newrefl{p}.json',p],work)
  for p in (14,15,16):
   work=context/f'p{p}/maintext'
   for name in ('constants_check.py','family_spec_check.py'):run(f'p{p}-'+name[:-3],work/name,[],work)
  for p in (14,15,16,18):
   work=context/('outer/prose'if p==18 else f'p{p}/outer/prose')
   run(f'outer-prose-{p}',work/'prose_checks.py',[],work)
  work=context/'pB'
  for p in (10,11,12,13):
   run(f'vpcB-{p}',work/'common/vpcB.py',[p,'--output',work/f'common/vpcB_{p}.json'],work)
   run(f'overlapB-{p}',work/'common/overlapB.py',[p,work/f'common/overlapB_{p}.json'],work)
   run(f'maintextB-{p}',work/'maintext/maintextB.py',[p],work,envextra={'PB_P':str(p)})
 if a.suite in ('all','audits'):
  from tools.audit_families import audits
  audits(a,scratch,catalog,run)
 if a.suite in ('all','three-three-n'):
  root=scratch/'three-three-n';work=copy_native(a.data_root/'payload/three-three-n',root/'experiments/33n')
  # verify_certificate.py finds the A_ref verifier and the written geometric
  # argument (whose hash it checks) at these relative paths.
  source=root/'audit/sources/python/small_3_9/verify.py';source.parent.mkdir(parents=True);shutil.copyfile(small/'A_ref/verify.py',source)
  target=root/'proofs/33n-geometric-proof.tex';target.parent.mkdir();shutil.copyfile(a.data_root/'payload/inputs/33n-geometric-proof.tex',target)
  run('three-three-n',work/'verify_certificate.py',[],work)
  shutil.copyfile(work/'verification.json',a.output/'three-three-n.json')
