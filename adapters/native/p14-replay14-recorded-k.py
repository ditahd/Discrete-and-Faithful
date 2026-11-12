"""Replay of the stored certificates of a finished box of engine 8, 8b or 8c (smallest order 14).  No optimizer is used and no stored result is trusted:
  1. both Taylor source banks (old sources, new sources) are rebuilt from scratch and their hashes must equal the recorded ones;
  2. support18 rows (S, H, R): for every stored certificate cell the residual is re-assembled from the bank with the STORED
     multipliers on the cell given by the stored address and the acceptance test is run again; every support of a rescued row is
     re-tested for exact coherence with the first target (newcat);
  3. extended rows: three-term certificates (tm_bank.full_pair, the test that accepted them), supported orientations, tail charts
     against new sources (five controls, de Casteljau subdivision of the tail interval), time caps and positive sums of the new
     sources are replayed in the same way; the path controls of the new sources are recomputed;
  4. every pair recorded as coherent is re-tested, and every alias record (class of another name) is re-derived: the canonical name and the
     power of B must be reproduced by newcat.canonical_old, and the class it names must have a record of its own.
Run in a scratch copy of the engine directory:  python -I -O driver.py replay14.py RECORDED_DIR"""
import json, sys, time
from pathlib import Path
import numpy as np
from iv import I, stack
from tm_bank import restrict, full_pair, to_model
from tm_positive import hermitian
from ext_sources import merged, NORMS
from support18 import accept
from tail_tm64 import split_controls
from tm_geometry import time_form, tail_bernstein
from rect_model import Model
from tm_sources64 import domain
from boxspec import degree, zeta
import newcat
ROOT = Path(__file__).resolve().parent
def coh(u, s, allow_K=False):
    w = newcat.coherent(int(u), int(s)); assert w is not None and (allow_K or w[0] != 'K'), ('coherence not reproduced', u, s)
def main(rec):
    t0 = time.time(); rec = Path(rec); bank, manifest, extman = merged(); ctx = bank.ctx; HP, HE = bank.H, bank.HE
    old = json.loads((rec / 'tm_sources64_s0.json').read_text()); oldx = json.loads((rec / 'tm_ext_s0.json').read_text())
    s = json.loads((rec / 'support18_s0.json').read_text()); x = json.loads((rec / 'ext_rows_s0.json').read_text())
    assert manifest['bank_sha256'] == old['bank_sha256'] == s['source_bank_sha256'] == x['source_bank_sha256'], 'bank hash is not reproduced'
    assert extman['bank_sha256'] == oldx['bank_sha256'] == s['ext_bank_sha256'] == x['ext_bank_sha256'], 'new-source bank hash is not reproduced'
    print('bank hashes reproduced', manifest['bank_sha256'][:16], extman['bank_sha256'][:16], flush=True)
    st = {'cells': 0, 'worst': 1e9, 'maxdiff': 0.0}
    def cell(P, E, path, w, g, recorded, tag):
        Pn, HPn = P, HP
        for axis, side in path:
            Pn = restrict(Pn, ctx, axis, side); HPn = restrict(HPn.reshape(ctx.K, 1, 3, 3), ctx, axis, side).reshape(ctx.K, 3, 3)
        ok, margin, method = accept(ctx, Pn, E, HPn, HE, np.array(w), g); assert ok and margin > 0, ('certificate not reproduced', tag, path)
        st['cells'] += 1; st['worst'] = min(st['worst'], margin)
        if recorded is not None: st['maxdiff'] = max(st['maxdiff'], abs(margin - recorded))
    def rows_SR(rows, tag):
        for r in rows:
            if r.get('fallback') or 'failure' in r: continue
            ids = [int(i) for i in r['targets']] + [int(i) for i in r['supports']]; loc = [bank.positions[i] for i in ids]; P = bank.P[:, loc]; E = bank.E[loc]; nt = len(r['targets'])
            if r['kind'] == 'R':
                for y in ids[2:]: coh(ids[0], y)
            for c in r['certificates']:
                w = [float.fromhex(v) for v in c['weights']]; g = float.fromhex(c['gamma'])
                assert len(w) == len(ids) and g >= 0 and all(v <= 0 for v in w[nt:]) and (r['kind'] == 'H' or min(w[:nt]) > 0), 'signs'
                cell(P, E, c['path'], w, g, c['margin'], (tag, r['kind'], r['targets']))
    rows_SR(s['rows'], 'support'); n1 = st['cells']; print('support rows replayed, cells', n1, 'sec', round(time.time() - t0), flush=True)
    for c in s['coherent']: coh(*c['pair'], allow_K=(c['witness'][0] == 'K')); assert list(newcat.coherent(*c['pair'])) == c['witness'], ('saved coherence witness differs', c)
    for c in x['N']['coherent']: coh(*c['pair'], allow_K=(c['witness'][0] == 'K')); assert list(newcat.coherent(*c['pair'])) == c['witness'], ('saved coherence witness differs', c)
    have = {tuple(c['pair']) for c in x['N']['coherent']} | {tuple(r['targets']) for r in x['N']['three_term']} | {tuple(sorted(r['targets'], reverse=True)) for r in x['N']['supported']} | {tuple(r['targets']) for r in x['N']['supported']}
    for c in x['N'].get('alias', []):
        u, h = c['pair']; r_, m_ = newcat.canonical_old(int(h)); assert (r_, m_) == (c['same_element'], c['B_power']) and r_ != h, ('alias record not reproduced', c)
        assert (u, r_) in have, ('the class named by an alias record has no record', c)
    # three-term rows: the accepting test was tm_bank.full_pair on the restricted bank.  Cells are grouped by address; the bank of the
    # sources occurring at an address is restricted once (exact affine pullbacks, in the recorded order of the address).
    n3 = 0; bypath = {}
    for r in x['N']['three_term']:
        u, h = r['targets']
        for c in r['certificates']:
            w = [float.fromhex(v) for v in c['weights']]; g = float.fromhex(c['gamma']); assert min(w) > 0 and g >= 0 and len(w) == 2
            bypath.setdefault(tuple(map(tuple, c['path'])), []).append((u, h, w[0], w[1], g, c['margin']))
    for path, cells in sorted(bypath.items()):
        bk = bank.take(sorted({i for u, h, *_ in cells for i in (u, h)}))
        for axis, side in path: bk = bk.restrict(axis, side)
        for st0 in range(0, len(cells), 512):
            part = cells[st0:st0 + 512]
            yes, det = full_pair(bk, np.array([t[0] for t in part]), np.array([t[1] for t in part]), np.array([t[2] for t in part]), np.array([t[3] for t in part]), np.array([t[4] for t in part]))
            assert bool(np.all(yes)) and float(np.min(det.l)) > 0, ('three-term certificate not reproduced', path)
            n3 += len(part); st['maxdiff'] = max(st['maxdiff'], float(np.max(np.abs(det.l - np.array([t[5] for t in part])))))
    print('three-term cells replayed', n3, 'sec', round(time.time() - t0), flush=True)
    rows_SR(x['N']['supported'], 'new'); print('supported new rows replayed, cells', st['cells'] - n1, 'sec', round(time.time() - t0), flush=True)
    m = Model(domain(0), degree()); nT = 0
    for no in x['T']['charts']:
        assert zeta(no // 2) is not None; fs = tail_bernstein(m, 15 * no + 7)
        TP = stack([hermitian(F.coefficients()) for F in fs], axis=1); TE = stack([hermitian(F.remainder()) for F in fs])
        for r in [r for r in x['T']['rows'] if r['chart'] == no]:
            h = r['targets'][1]; loc = [bank.positions[h]]; FP = bank.P[:, loc]; FE = bank.E[loc]
            for c in r['certificates']:
                TPn, TEn, FPn, HPn = TP, TE, FP, HP
                for axis, side in c['path']:
                    if axis < ctx.d:
                        TPn = restrict(TPn, ctx, axis, side); FPn = restrict(FPn, ctx, axis, side); HPn = restrict(HPn.reshape(ctx.K, 1, 3, 3), ctx, axis, side).reshape(ctx.K, 3, 3)
                    else: assert axis == ctx.d; TPn = split_controls(TPn)[side]; TEn = split_controls(TEn)[side]
                w = [float.fromhex(v) for v in c['weights']]; g = float.fromhex(c['gamma']); assert min(w) > 0 and g >= 0 and len(w) == 2
                for j in range(5):
                    ok, margin, _ = accept(ctx, stack([TPn[:, j], FPn[:, 0]], axis=1), stack([TEn[j], FE[0]]), HPn, HE, w, g)
                    assert ok and margin > 0, ('tail certificate not reproduced', no, h, c['path'], j)
                nT += 1
    print('tail cells replayed', nT, 'sec', round(time.time() - t0), flush=True)
    L, branch = time_form(m)
    for r in x['C']['rows']:
        T = 4 * m.J + r['sign'] * L; loc = [bank.positions[r['targets'][1]]]
        P = stack([hermitian(T.coefficients()), bank.P[:, loc][:, 0]], axis=1); E = stack([hermitian(T.remainder()), bank.E[loc][0]])
        for c in r['certificates']:
            w = [float.fromhex(v) for v in c['weights']]; g = float.fromhex(c['gamma']); assert min(w) > 0 and g >= 0
            cell(P, E, c['path'], w, g, c['margin'], ('time', r['targets']))
    mu = 40 / (m.kap * I(15).sqrt()); T2 = 2 * m.J + m.H * mu
    for cidx, r in enumerate(x['M']['rows']):
        loc = [bank.positions[r['source']]]; P = stack([bank.P[:, loc][:, 0], hermitian(T2.coefficients())], axis=1); E = stack([bank.E[loc][0], hermitian(T2.remainder())])
        assert r['source'] == newcat.nid(cidx, 0) and [float.fromhex(v) for v in r['weights']] == [float(NORMS[cidx]), 1.0], 'positive-sum weights'
        for c in r['certificates']: cell(P, E, c['path'], [float(NORMS[cidx]), 1.0], 0.0, c['margin'], ('positive sum', r['source']))
    from path_tm64 import check_controls
    loc = [bank.positions[h] for h in newcat.NEW_IDS]; F = to_model(m.ctx, bank.P[:, loc], bank.E[loc]); pmin = 1e9
    for sgen in range(3):
        good, low, refined = check_controls(m, F, sgen); assert bool(np.all(good)), 'path controls of the new sources'; pmin = min(pmin, float(np.min(low)))
        assert abs(float(np.min(low)) - x['P']['rows'][sgen]['minimum']) <= 1e-9 * max(1, abs(float(np.min(low)))), 'path minimum differs from the record'
    out = {'status': 'ALL_STORED_CERTIFICATES_REPLAYED', 'bank_sha256': manifest['bank_sha256'], 'ext_bank_sha256': extman['bank_sha256'], 'support_rows': len(s['rows']), 'support_counts': s['counts'],
           'coherent_pairs_retested': len(s['coherent']) + len(x['N']['coherent']), 'alias_records_rederived': len(x['N'].get('alias', [])), 'cells_accept': st['cells'], 'three_term_cells': n3, 'tail_cells': nT, 'min_margin_accept': st['worst'],
           'max_margin_difference_from_record': st['maxdiff'], 'new_path_minimum': pmin, 'seconds': time.time() - t0}
    (ROOT / 'replay14.json').write_text(json.dumps(out)); print(out, flush=True)
if __name__ == '__main__': main(sys.argv[1])
