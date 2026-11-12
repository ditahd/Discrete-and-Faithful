"""Deterministic representative selection by native helper/weight format."""
import json
from pathlib import Path
PB_REPLAYS=['replay9-freshbank-pB-v2.py','replay9-freshbank-v1.py','replay9-SK-v2.py','replay9-SK-v1.py','replay9.py']
PB_CHECKS=['check_saved_tail_time_path_pB_v2.py','check_saved_no_tail_freshbank_v1.py','check_saved_no_tail_pB13_v1.py']
def choose(work,names):return next((work/n for n in names if(work/n).exists()),None)
def representatives(cases,data):
 picked={}
 for c in cases:
  work=data/c['run'];spec=json.loads((work/'box.json').read_bytes());tails=any(z is not None for z in spec.get('zeta',[['-1/13','1/13']]*3))
  if c['family'].startswith('pB'):
   replay=choose(work,PB_REPLAYS);helper=choose(work,PB_CHECKS);key=(c['family'],tails,replay.name,helper.name)
  else:
   dimension=json.loads((work/'tm_sources64_s0.json').read_bytes())['dimension']
   key=(c['family'],tails,'p15-ND-tail'if c['family']=='s15'and tails and dimension>1 else'standard')
   if c['family']=='s14' and tails and 'def node_intervals(' not in(work/'tail_tm64.py').read_text():key=(*key,'tail-engine-without-vacuity-api')
  if c['weight_format']!='retained-basic-npz-v1':key=(*key,c['weight_format'])
  picked.setdefault(key,c)
 return list(picked.values())
