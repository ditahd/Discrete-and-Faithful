"""Bind the unchanged fixed-domain polar verifier to its retained exact trace."""
import hashlib,json,runpy,sys
from pathlib import Path
source=Path(sys.argv[1]);reference=json.loads(Path(sys.argv[2]).read_bytes());order=sys.argv[3]
keys=('words','domain','thresholds','certified_ranges','boxes','base_grid','adaptive_bisections','maximum_depth','eigenvalue_lower_bound','rational_bound_stream_sha256','script_sha256')
assert all(key in reference for key in keys)
assert hashlib.sha256(source.read_bytes()).hexdigest()==reference['script_sha256']
vpc_key='vpc'+order+'_sha256';assert hashlib.sha256((source.parent/('vpc'+order+'.py')).read_bytes()).hexdigest()==reference[vpc_key]
sys.argv=[str(source)];runpy.run_path(str(source),run_name='__main__')
actual=json.loads((source.parent/('newrefl'+order+'.json')).read_bytes())
assert actual['status']==reference['status']=='NEW_REFLECTION_POSITIVE_SUMS_VERIFIED'
for key in keys:
 assert actual[key]==reference[key],('retained fixed-domain polar traversal differs',key)
if 'base_cell_stream_sha256' in reference:assert actual['base_cell_stream_sha256']==reference['base_cell_stream_sha256']
assert actual[vpc_key]==reference[vpc_key]
print(json.dumps({'status':'RETAINED_FIXED_DOMAIN_POLAR_TRAVERSAL_REPLAYED','order':order,'rational_bound_stream_sha256':actual['rational_bound_stream_sha256'],'new_certificate_tree_accepted':False}),flush=True)
