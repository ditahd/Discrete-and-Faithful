"""Replay the exact polar traversal of a pB case and require equality with its retained trace."""
import hashlib,json,runpy,sys
from pathlib import Path
from fractions import Fraction as Q
original=Path(sys.argv[1]);retained=Path(sys.argv[2]);work=Path.cwd()
old=json.loads((original/'newrefl.json').read_bytes());reference=json.loads((retained/'newrefl.json').read_bytes());box=json.loads((original/'box.json').read_bytes())
sources=retained/'original-source';scripts=list(sources.glob('newreflB*.py'));assert len(scripts)==1
source=scripts[0];assert hashlib.sha256(source.read_bytes()).hexdigest()==reference['script_sha256']==old['script_sha256']
for name,key in [('vpcB.py','vpcB_sha256'),('dom.py','dom_sha256')]:assert hashlib.sha256((sources/name).read_bytes()).hexdigest()==reference[key]==old[key]
output=work/'replayed-polar.json';assert not output.exists()and not output.with_suffix('.ckpt').exists()
sys.argv=[str(source),str(reference['p']),str(output),'--b',','.join(box['box'][1][:2]),'--c',','.join(box['box'][2][:2]),'--tag',reference['tag'],*reference['classes']]
runpy.run_path(str(source),run_name='__main__');actual=json.loads(output.read_bytes())
for key in ('status','p','classes','tag','domain','thresholds','base_grid','boxes','adaptive_bisections','maximum_depth','certified_ranges','eigenvalue_lower_bound','rational_bound_stream_sha256','base_cell_stream_sha256','script_sha256','vpcB_sha256','dom_sha256'):
 assert actual[key]==reference[key],('retained exact traversal differs',key)
assert actual['status']=='NEW_REFLECTION_POSITIVE_SUMS_VERIFIED'and Q(actual['eigenvalue_lower_bound'])>Q(1,2**34)
for key in ('p','classes','tag','domain','thresholds','base_grid'):assert actual[key]==old[key]
print(json.dumps({'status':'RETAINED_POLAR_TRAVERSAL_REPLAYED','base_cell_trace_digest':actual['rational_bound_stream_sha256'],'bisections':actual['adaptive_bisections'],'new_certificate_tree_accepted':False}),flush=True)
