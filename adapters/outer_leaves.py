"""Portable saved-leaf replay, using the original exact outer predicates."""
import hashlib,json,runpy,sys
from fractions import Fraction as Q
from pathlib import Path
import obl_exact as oe
root=Path.cwd();cat=oe.catalogue();files=sorted(root.glob('res_*.json'))
assert len(files)==39 and {p.stem[4:]for p in files}==set(cat)
leaves=0
for p in files:
 r=json.loads(p.read_bytes());name=r['name'];num,strict,zeta=cat[name]
 assert r['status']=='PROVED'and r['strict']==strict and r['zeta']==zeta and len(r['leaf_list'])==r['leaves']
 Ts,_=oe.prepare(num,zeta)
 for leaf in r['leaf_list']:
  box=tuple((Q(lo),Q(hi))for lo,hi in leaf['box']);Bs=[None if T is None else oe.box_bernstein(T,box)for T in Ts]
  accepted=all(B is None or B.min()>=0 for B in Bs)
  if accepted and strict:accepted=Bs[0]is not None and oe.strict_ok(Bs[0],box)
  h=hashlib.sha256()
  for B in Bs:h.update(repr(None if B is None else(B.shape,int(B.min()),int(B.max()),int(B.sum()))).encode())
  assert accepted and h.hexdigest()[:16]==leaf['digest']and not oe.skip(box),(name,'saved leaf rejected');leaves+=1
coverage=runpy.run_path(str(root/'cover_check.py'),run_name='__main__')
assert coverage['allok']is True and len(coverage['names'])==39 and set(coverage['names'])==set(cat)and coverage['tot_leaves']==leaves
print(json.dumps({'status':'ALL_39_OUTER_SAVED_LEAVES_AND_ORDERED_COVERS_REPLAYED','leaves':leaves,'search':False}),flush=True)
