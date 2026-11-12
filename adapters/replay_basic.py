"""Replay the retained BASIC multipliers of one cusp case.

First the saved closed cell tree and its exact dyadic row cover are checked
(closed_cover). Then every retained coefficient batch is evaluated with the
accepting predicate recorded for it: fast_pair, full_pair or tensor_bernstein
of the case's own engine, on the bank restricted to the saved cell.
This adapter never calls proposal(), hopeless(), run(), Bank.build() or generate().
"""
import hashlib,json,math,sys,time
from pathlib import Path
import numpy as np

def need(value,message):
 if not value:raise ValueError(message)
def sha(p):
 with p.open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(p):return json.loads(p.read_bytes())


def closed_cover(saved, np, dimension):
    count = saved['canonical_pairs']
    need(type(count) is int and count > 0, 'canonical census')
    unresolved = saved['unresolved']
    need(unresolved == sorted(set(unresolved)), 'unique unresolved IDs')
    nodes, children = {}, {}
    def ids(values):
        need(type(values) is list and values == sorted(set(values))
             and all(type(i) is int and 0 <= i < count for i in values), 'exact sorted global row IDs')
        return set(values)
    ids(unresolved)
    for node in saved['nodes']:
        path = tuple(map(tuple, node['path']))
        need(path not in nodes and all(type(a) is int and 0 <= a < dimension and type(s) is int and s in (0, 1)
                                      for a, s in path), 'exact unique original saved path')
        accepted, remaining = ids(node['accepted']), ids(node['remaining'])
        need(not accepted & remaining and len(accepted) + len(remaining) == node['input'], 'saved row partition')
        nodes[path] = node
    need(() in nodes, 'saved root')
    omitted = set(range(count)) - ids(sorted(nodes[()]['accepted'] + nodes[()]['remaining']))
    need(omitted <= set(unresolved) and len(omitted) == saved['float_prefilter_unresolved'], 'root omitted rows')
    for path, node in nodes.items():
        if path:
            need(path[:-1] in nodes, 'orphan saved cell')
        kids = sorted(p for p in nodes if len(p) == len(path) + 1 and p[:-1] == path)
        children[path] = kids
        if kids:
            need(len(kids) == 2 and kids[0][-1][0] == kids[1][-1][0] and {child[-1][1] for child in kids} == {0, 1}, 'both closed saved siblings on one original axis required')
            for child in kids:
                need(sorted(nodes[child]['accepted'] + nodes[child]['remaining']) == node['remaining'],
                     'exact inherited remaining-row assignment')
        else:
            need(set(node['remaining']) <= set(unresolved), 'terminal unassigned row')
    order = []
    def visit(path):
        order.append(path)
        for child in children[path]:
            visit(child)
    visit(())
    need(order == [tuple(map(tuple, n['path'])) for n in saved['nodes']], 'original DFS order')
    depth = max(map(len, nodes)); denominator = 2 ** depth
    mass = np.zeros(count, dtype=np.int64)
    for path, node in nodes.items():
        mass[np.asarray(node['accepted'], dtype=np.int64)] += 2 ** (depth - len(path))
    un = np.zeros(count, dtype=bool); un[unresolved] = True
    need(bool(np.all(mass[~un] == denominator)) and bool(np.all(mass[un] < denominator)),
         'exact row-specific dyadic cover')
    return children, {'nodes': len(nodes), 'closed_splits': sum(bool(x) for x in children.values()),
                      'canonical_rows': count, 'resolved_rows': int((~un).sum()),
                      'unresolved_rows': len(unresolved), 'accepted_cell_occurrences': sum(len(n['accepted']) for n in nodes.values()),
                      'dyadic_denominator': denominator, 'row_mass_sha256': hashlib.sha256(mass.tobytes()).hexdigest(),
                      'both_closed_children_and_exact_inherited_rows_checked': True}


def main(recorded,weights):
 from tm_sources64 import load
 from basic_catalogue64 import canonical_basic
 from tm_bank import fast_pair,full_pair,to_model
 from tm_positive import tensor_bernstein
 saved=read(recorded/'basic_tm64_s0.json');keys,aliases=canonical_basic()
 # Original integer storage is preserved; verify row values against its native digest.
 matches=[]
 for dtype in ('<i4','<i8'):
  if sha_bytes(keys.astype(dtype).tobytes())==saved['canonical_keys_sha256'] and sha_bytes(aliases.astype(dtype).tobytes())==saved['bindings_sha256']:matches.append(dtype)
 need(len(matches)==1,'canonical row/source key digest')
 need(keys[saved['unresolved']].tolist()==saved['unresolved_keys'],'unresolved source identities')
 bank,manifest=load(0)
 need(saved['box']==manifest['box'],'exact saved domain')
 children,cover=closed_cover(saved,np,bank.ctx.d)
 entries=[]
 with (weights/'basic-weights.jsonl').open()as stream:
  for index,line in enumerate(stream):
   entry=json.loads(line);need(entry['path']==f'basic-weights-{index:06d}.npz','original sequential chunk identity');entries.append(entry)
 bypath={}
 for e in entries:bypath.setdefault(tuple(map(tuple,e['cell_path'])),[]).append(e)
 pending={():bank.take(np.unique(keys))};del bank
 count=0;minimum=math.inf;started=time.monotonic()
 for node_index,node in enumerate(saved['nodes']):
  path=tuple(map(tuple,node['path']));bk=pending.pop(path);seen=set();assigned=set(node['accepted'])
  for entry in bypath.pop(path,[]):
   if 'original_node_index' in entry:need(type(entry['original_node_index']) is int and entry['original_node_index']==node_index,'original node-index/path identity')
   p=weights/entry['path'];need(sha(p)==entry['sha256'],'retained NPZ digest')
   with np.load(p,allow_pickle=False)as w:
    need(set(w.files)=={'row_ids','source_pairs','wa','wb','gamma','margin','exponents'},'exact retained fields')
    ids=w['row_ids'];n=len(ids);need(ids.dtype==np.dtype('int64')and ids.shape==(n,)and n==entry['rows'],'integer row dtype/census')
    need(len(set(map(int,ids)))==n and not seen.intersection(map(int,ids))and set(map(int,ids))<=assigned,'unique original accepted row assignment')
    seen.update(map(int,ids));pairs=w['source_pairs']
    need(pairs.dtype==np.dtype('int64')and np.array_equal(pairs,keys[ids]),'exact canonical source pairs')
    need(w['exponents'].dtype==np.dtype('int64')and np.array_equal(w['exponents'],np.asarray(bk.ctx.exponents,dtype=np.int64)),'unchanged basis')
    for name in ('wa','wb','gamma','margin'):
     v=w[name];need(v.dtype==np.dtype('float64')and v.shape==(n,)and np.all(np.isfinite(v)),'finite binary64 '+name)
    need(np.all(w['wa']>0)and np.all(w['wb']>0)and np.all(w['gamma']>=0)and np.all(w['margin']>0),'strict coefficient signs')
    methods=entry['accepted_methods'];need(len(methods)==n and all(m in ('fast','full','quarter_power_full','quarter_power_bernstein','bernstein')for m in methods),'native accepting methods')
    # Replay exactly the accepting predicate with final stored coefficients.
    for method in set(methods):
     allids=np.asarray([j for j,m in enumerate(methods)if m==method],dtype=np.int64)
     for start in range(0,len(allids),512):
      ix=allids[start:start+512];aa,bb=pairs[ix,0],pairs[ix,1];wa,wb,g=w['wa'][ix],w['wb'][ix],w['gamma'][ix]
      if method in ('bernstein','quarter_power_bernstein'):
       for j in range(len(ix)):
        P,E=bk.residual(aa[j:j+1],bb[j:j+1],wa[j:j+1],wb[j:j+1],g[j:j+1]);ok,low,_=tensor_bernstein(to_model(bk.ctx,P[:,0],E[0]));need(bool(ok)and math.isfinite(float(low))and low>0,'native Bernstein predicate');minimum=min(minimum,float(low))
      else:
       good,det=(fast_pair if method=='fast'else full_pair)(bk,aa,bb,wa,wb,g)
       need(good.dtype.kind=='b'and good.shape==det.l.shape==det.h.shape==(len(ix),)and np.all(good)and np.all(np.isfinite(det.l))and np.all(np.isfinite(det.h))and np.all(det.l<=det.h)and np.all(det.l>0),'native fixed-weight matrix predicate');minimum=min(minimum,float(det.l.min()))
    count+=n
  need(seen==assigned,'all original accepted rows replayed')
  print(json.dumps({'basic_node':node_index+1,'nodes':len(saved['nodes']),'accepted_rows':len(seen),'total_replayed_rows':count,'seconds':time.monotonic()-started}),flush=True)
  if children[path]:
   compact=bk.take(np.unique(keys[np.asarray(node['remaining'],dtype=np.int64)]))
   for child in children[path]:pending[child]=compact.restrict(*child[-1])
 need(not pending and not bypath and count==cover['accepted_cell_occurrences'],'complete original tree/weights')
 result={'schema':'preferred-interval-fixed-basic-replay-v1','status':'ALL_RETAINED_BASIC_WEIGHTS_REPLAYED','rows':count,'weight_batches':len(entries),'minimum':minimum,'closed_cover':cover,'seconds':time.monotonic()-started,'integer_storage':matches[0],'fixed_weight_batch_max':512,'original_accepting_predicates':True,'new_search':False,'Lean_verified':False}
 print(json.dumps(result),flush=True);return result

def sha_bytes(b):return hashlib.sha256(b).hexdigest()
if __name__=='__main__':
 need(__debug__ and sys.flags.optimize==0,'assertions must be enabled');main(Path(sys.argv[1]),Path(sys.argv[2]))
