"""Direct p15 tail/TIME/PATH checking with the original saved choices only.

Run through the restored case's driver.py, with the recorded case directory as
the only argument. No weight proposal, subdivision search or optimizer runs.
"""
import hashlib
import json
import math
from fractions import Fraction as Q
from pathlib import Path
import sys
import time

if not __debug__:
    raise RuntimeError('mathematical assertions must stay enabled')

import numpy as np
from iv import I, C
from tm_bank import Bank, fast_pair, full_pair, to_model
from tm_sources64 import load, domain
from tm_positive import hermitian, tensor_bernstein, univariate_weights
from tm_geometry import time_form, tail_bernstein, path_bernstein, scalar_positive, scalar_lower
from tm_engine import stack_t
from rect_model import Model
from boxspec import degree, zeta, zeta_strings
from catalogue import short_labels, coset, red, bw, baseword
from path_tm64 import controls, scalar_bounds
import tail_tm64 as tail

ROOT = Path.cwd()
REC = Path(sys.argv[1]).resolve()


def read(path):
    return json.loads(Path(path).read_text(), parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite JSON')))


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def closed_nodes(nodes, count, dimension):
    """Check the saved whole closed binary tree, not just total leaf mass."""
    assert type(count) is int and count >= 0
    if count == 0:
        assert nodes == []
        return {'nodes': 0, 'certificates': 0, 'vacuous_cells': 0}
    lookup, children = {}, {}
    for node in nodes:
        assert isinstance(node['path'], list)
        path = []
        for step in node['path']:
            assert len(step) == 2
            axis, side = step
            assert type(axis) is int and 0 <= axis < dimension
            assert type(side) is int and side in (0, 1)
            path.append((axis, side))
        path = tuple(path)
        assert path not in lookup, ('duplicate saved node', path)
        lookup[path] = node
        if path:
            children.setdefault(path[:-1], []).append(path)
    assert () in lookup
    assert all(path[:-1] in lookup for path in lookup if path)
    seen, totals = set(), {'nodes': len(nodes), 'certificates': 0, 'vacuous_cells': 0}

    def unique(rows):
        assert isinstance(rows, list) and all(type(row) is int for row in rows)
        assert len(rows) == len(set(rows))
        return rows

    def visit(path, pending):
        assert path not in seen
        seen.add(path)
        node = lookup[path]
        assert unique(node['input']) == pending
        remaining = unique(node['remaining'])
        accepted = unique([c['row'] for c in node['certificates']])
        vacuous = unique([v[0] for v in node.get('vacuous', [])])
        all_rows = accepted + vacuous + remaining
        assert len(all_rows) == len(set(all_rows)) and set(all_rows) == set(pending)
        totals['certificates'] += len(accepted)
        totals['vacuous_cells'] += len(vacuous)
        kids = children.get(path, [])
        if remaining:
            assert len(kids) == 2
            steps = [child[-1] for child in kids]
            assert steps[0][0] == steps[1][0] and {s[1] for s in steps} == {0, 1}
            for child in kids:
                visit(child, remaining)
        else:
            assert not kids

    visit((), list(range(count)))
    assert seen == set(lookup)
    return totals


def coefficient(text, positive):
    assert type(text) is str
    value = float.fromhex(text)
    assert math.isfinite(value) and (value > 0 if positive else value >= 0)
    return value


def positive(answer):
    ok, low, method = answer
    assert isinstance(ok, (bool, np.bool_)) and bool(ok)
    assert isinstance(low, (int, float, np.integer, np.floating)) and not isinstance(low, (bool, np.bool_))
    assert math.isfinite(float(low)) and low > 0, ('nonpositive saved scalar', low, method)
    return float(low)


def fixed_controls(bank, aa, bb, wa, wb, gamma, fast):
    """Original positivity predicates on exactly the supplied stored weights."""
    count = len(aa)
    assert count and all(len(x) == count for x in (bb, wa, wb, gamma))
    assert np.all(np.isfinite(wa)) and np.all(np.isfinite(wb)) and np.all(np.isfinite(gamma))
    assert np.all(wa > 0) and np.all(wb > 0) and np.all(gamma >= 0)
    good, det = (fast_pair if fast else full_pair)(bank, aa, bb, wa, wb, gamma)
    assert good.dtype.kind == 'b' and good.shape == det.l.shape == det.h.shape == (count,)
    assert np.all(np.isfinite(det.l)) and np.all(np.isfinite(det.h)) and np.all(det.l <= det.h)
    good, low = good.copy(), det.l.copy()
    if fast:
        failed = np.flatnonzero(~good)
        if len(failed):
            yes, dd = full_pair(bank, aa[failed], bb[failed], wa[failed], wb[failed], gamma[failed])
            assert yes.dtype.kind == 'b' and yes.shape == dd.l.shape == dd.h.shape == (len(failed),)
            assert np.all(np.isfinite(dd.l)) and np.all(np.isfinite(dd.h)) and np.all(dd.l <= dd.h)
            good[failed], low[failed] = yes, dd.l
    for j in np.flatnonzero(~good):
        pp, ee = bank.residual(aa[j:j+1], bb[j:j+1], wa[j:j+1], wb[j:j+1], gamma[j:j+1])
        answer = tensor_bernstein(to_model(bank.ctx, pp[:, 0], ee[0]))
        low[j] = positive(answer)
        good[j] = True
    assert np.all(good) and np.all(np.isfinite(low)) and np.all(low > 0), 'stored matrix control failed'
    return float(np.min(low))


def check_tail(kind, manifest):
    saved = read(REC / f'tail_{kind}_tm64_s0.json')
    assert saved['status'] == 'ALL_TAIL_COMPARISONS_VERIFIED_ON_SLAB'
    assert saved['P0'] == 15 and saved['slab'] == 0 and saved['kind'] == kind
    # Each original stage started a fresh process. Do not carry the short-stage
    # mutable exclusion list into the following tail-tail catalogue.
    tail.EXCUSED[:] = []
    pairs, original = tail.catalogue(kind)
    assert saved['pairs'] == len(pairs)
    assert saved.get('excused_exact_own_star', []) == list(tail.EXCUSED)
    assert saved.get('excused_k_names', []) == []
    cover = closed_nodes(saved['nodes'], len(pairs), manifest['dimension'] + (1 if kind == 'short' else 2))
    if not len(pairs):
        return {'rows': 0, 'controls_checked': 0, 'minimum': None, **cover}
    assert saved['box'] == [[str(a), str(b)] for a, b in domain(0)]
    assert saved['tail_intervals'] == zeta_strings()
    assert saved['pairs_sha256'] == hashlib.sha256(pairs.tobytes()).hexdigest()
    assert saved['original_pairs_sha256'] == hashlib.sha256(original.tobytes()).hexdigest()
    assert saved['source_bank_sha256'] == manifest['bank_sha256']
    bank, fresh = tail.initial(0, kind, pairs)
    assert fresh['bank_sha256'] == manifest['bank_sha256']
    count, minimum, vacuous_count = 0, math.inf, 0
    for node in saved['nodes']:
        bk = bank
        for axis, side in node['path']:
            bk = bk.restrict(axis, side) if axis < bank.ctx.d else tail.restrict_z(bk, axis - bank.ctx.d, side)
        # Original p15 tail.run has no generic-angle vacuity branch.
        fresh_vacuous = []
        assert fresh_vacuous == node.get('vacuous', []), ('saved exact tail vacuity differs', kind, node['path'])
        vacuous_count += len(fresh_vacuous)
        for start in range(0, len(node['certificates']), 32):
            certs = node['certificates'][start:start+32]
            rows = [c['row'] for c in certs]
            weights = np.array([[coefficient(c['weights'][0], True), coefficient(c['weights'][1], True),
                                 coefficient(c['weights'][2], False)] for c in certs])
            assert all(len(c['weights']) == 3 for c in certs)
            aa, bb = tail.slots(pairs[rows], kind)
            n = 5 if kind == 'short' else 25
            assert aa.shape == bb.shape == (len(certs), n)
            wa, wb, gamma = [np.repeat(weights[:, j], n) for j in range(3)]
            low = fixed_controls(bk, aa.ravel(), bb.ravel(), wa, wb, gamma, True)
            minimum = min(minimum, low)
            count += n * len(certs)
        print('Original tail cells passed:', kind, node['path'], len(node['certificates']), 'vacuous', len(fresh_vacuous), flush=True)
    assert count == cover['certificates'] * (5 if kind == 'short' else 25)
    assert vacuous_count == cover['vacuous_cells']
    return {'rows': len(pairs), 'controls_checked': count,
            'minimum': minimum if count else None, **cover}


def check_time(allbank, manifest, m):
    saved = read(REC / 'time_tm64_s0.json')
    assert saved['status'] == 'ALL_SHORT_AND_TAIL_TIME_CAPS_VERIFIED_ON_SLAB'
    assert saved['P0'] == 15 and saved['slab'] == 0 and saved['source_bank_sha256'] == manifest['bank_sha256']
    assert saved['box'] == [[str(a), str(b)] for a, b in domain(0)] and saved.get('k_names', []) == []
    L, branch = time_form(m)
    assert all(math.isfinite(float(v)) and v > 0 for v in branch.values())
    assert set(branch) == set(saved['branch'])
    assert all(math.isfinite(float(v)) and v > 0 for v in saved['branch'].values())
    tails = [no for no in range(6) if zeta(no // 2) is not None]
    short_ids, tail_ids, extra = np.arange(147) * 15 + 7, [], []
    for no in tails:
        for j, form in enumerate(tail_bernstein(m, 15 * no + 7)):
            tail_ids.append(2205 + 5 * no + j)
            extra.append(form)
    extra.extend([4 * m.J - L, 4 * m.J + L])
    arrays, errors = [], []
    for part, end in [('r', 'l'), ('r', 'h'), ('i', 'l'), ('i', 'h')]:
        arrays.append(np.concatenate([getattr(getattr(allbank.P, part), end)[:, short_ids],
            np.stack([getattr(getattr(hermitian(f.coefficients()), part), end) for f in extra], axis=1)], axis=1))
        errors.append(np.concatenate([getattr(getattr(allbank.E, part), end)[short_ids],
            np.stack([getattr(getattr(hermitian(f.remainder()), part), end) for f in extra])], axis=0))
    ids = np.concatenate([short_ids, np.array(tail_ids, int), [3000, 3001]])
    bank = Bank(m.ctx, C(I(arrays[0], arrays[1]), I(arrays[2], arrays[3])),
                C(I(errors[0], errors[1]), I(errors[2], errors[3])), allbank.H, allbank.HE, ids)
    rows = [['short', i, sign] for i in range(147) for sign in (0, 1)]
    rows += [['tail', i, sign] for i in tails for sign in (0, 1)]
    assert saved['rows'] == rows and saved['short_rows'] == 147 and saved['tail_rows'] == len(tails) and saved['signs'] == 2
    cover = closed_nodes(saved['nodes'], len(rows), m.ctx.d)
    assert cover['vacuous_cells'] == 0
    minimum, count, tail_count = math.inf, 0, 0
    for node in saved['nodes']:
        bk = bank
        for axis, side in node['path']:
            bk = bk.restrict(axis, side)
        for cert in node['certificates']:
            kind, index, sign = rows[cert['row']]
            alpha, gamma = coefficient(cert['alpha'], True), coefficient(cert['gamma'], False)
            sources = [15 * index + 7] if kind == 'short' else list(range(2205 + 5 * index, 2210 + 5 * index))
            n = len(sources)
            low = fixed_controls(bk, np.full(n, 3000 + sign, int), np.array(sources, int),
                                 np.ones(n), np.full(n, alpha), np.full(n, gamma), False)
            minimum = min(minimum, low)
            count += n
            tail_count += n if kind == 'tail' else 0
        print('Original time cells passed:', node['path'], len(node['certificates']), flush=True)
    return {'rows': len(rows), 'cells': cover['certificates'], 'controls_checked': count,
            'tail_signed_rows': 2 * len(tails), 'tail_controls_checked': tail_count,
            'minimum': minimum, 'nodes': cover['nodes']}


def check_path_batch(m, forms, generator, ids, refinements, local):
    assert all(type(i) is int for i in ids + refinements)
    assert len(ids) == len(set(ids)) and len(refinements) == len(set(refinements))
    assert all(0 <= i < len(ids) for i in refinements) if local else set(refinements) <= set(ids)
    positions = refinements if local else [ids.index(i) for i in refinements]
    cs = controls(m, forms, generator)
    assert len(cs) == 3
    lows = np.stack([np.atleast_1d(scalar_bounds(f)) for f in cs])
    assert lows.shape == (3, len(ids)) and np.all(np.isfinite(lows))
    for i in positions:
        for j, form in enumerate(cs):
            lows[j, i] = positive(scalar_positive(form[i]))
    assert np.all(np.isfinite(lows)) and np.all(lows > 0), ('stored path failed', generator, ids, refinements)
    return float(np.min(lows))


def saved_scalar(form, choice):
    assert len(choice) == 3 and choice[0] is True
    assert type(choice[1]) in (int, float) and math.isfinite(choice[1]) and choice[1] > 0
    if choice[2] == 'power_range':
        low = scalar_lower(form)
        return positive((low > 0, low, 'power_range'))
    assert choice[2] == 'tensor_Bernstein'
    # Verbatim original scalar_positive tensor branch, without replacing the
    # recorded tensor choice with an early power-range return.
    ctx = form.ctx; N = ctx.N; shape = (N + 1,) * ctx.d + form.shape
    lo = np.zeros(shape); hi = lo.copy()
    for k, p in enumerate(ctx.exponents):
        lo[p] = form.lo[k]; hi[p] = form.hi[k]
    coeff = I(lo, hi); weights = univariate_weights(N)
    from iv import stack
    for axis in range(ctx.d):
        out = []
        for j in range(N + 1):
            terms = []
            for e in range(N + 1):
                sl = [slice(None)] * len(shape); sl[axis] = e
                terms.append(coeff[tuple(sl)] * I(weights[j][e]))
            out.append(sum(terms, I(np.zeros((N + 1,) * (ctx.d - 1) + form.shape))))
        coeff = stack(out, axis)
    result = coeff + form.rem; low = float(np.min(result.l))
    return positive((low > 0, low, 'tensor_Bernstein'))


def check_paths(bank, manifest, m):
    saved = read(REC / 'path_tm64_s0.json')
    assert saved['status'] == 'ALL_GENERATOR_PATH_PREMISES_VERIFIED_ON_SLAB'
    assert saved['P0'] == 15 and saved['slab'] == 0 and saved['source_bank_sha256'] == manifest['bank_sha256']
    assert saved['box'] == [[str(a), str(b)] for a, b in domain(0)]
    labels = short_labels(); own, expected = [], []
    for s in range(3):
        ids = []
        for i in range(2205):
            nu, k, e = labels[i // 15]
            if coset(red(bw(i % 15 - 7) + baseword(nu, k, e))) == coset('SRC'[s]):
                own.append([s, i])
            else:
                ids.append(i)
        expected.append(ids)
    active = [i for i in range(90) if zeta(i // 30) is not None]
    wanted = [('short', s, None) for s in range(3)] + [('tail', s, i) for s in range(3) for i in active]
    assert [(r['kind'], r['generator'], r.get('index')) for r in saved['records']] == wanted
    assert saved['own_aliases'] == own and len(own) == 10
    assert saved['short_rows'] == sum(map(len, expected)) == 6605 and saved['tail_rows'] == 3 * len(active)
    short_count, tail_count, minimum = 0, 0, math.inf
    for s, record in enumerate(saved['records'][:3]):
        assert [i for b in record['batches'] for i in b['indices']] == expected[s]
        for batch in record['batches']:
            ids = batch['indices']; assert ids
            forms = to_model(m.ctx, bank.P[:, ids], bank.E[ids])
            minimum = min(minimum, check_path_batch(m, forms, s, ids, batch['tensor_refinements'], False))
            short_count += len(ids)
        print('Original short path group passed:', s, flush=True)
    for record in saved['records'][3:]:
        forms = stack_t(tail_bernstein(m, record['index']))
        minimum = min(minimum, check_path_batch(m, forms, record['generator'], list(range(5)), record['tensor_refinements'], True))
        tail_count += 1
    assert short_count == 6605 and tail_count == 3 * len(active)
    print('Original tail path groups passed:', tail_count, flush=True)
    L, branch = time_form(m); mu = 40 / (m.kap * I(15).sqrt())
    assert all(math.isfinite(float(v)) and v > 0 for v in branch.values())
    wanted_geometry = [(s, kind) for s in range(3) for kind in
        ('negative_norm', 'time_minus', 'time_plus', 'strict_core', 'own_leading_value')]
    assert [(r['generator'], r['kind']) for r in saved['geometric_paths']] == wanted_geometry
    scalar_count, geometry_minimum = 0, math.inf
    for s in range(3):
        families = [('negative_norm', -m.H, Q(0), Q(5)),
                    ('time_minus', 4 * m.J - L, Q(0), Q(3)),
                    ('time_plus', 4 * m.J + L, Q(0), Q(3)),
                    ('strict_core', -(m.J + m.H * mu / 2), Q(3), Q(5))]
        for slot, (kind, form, lo, hi) in enumerate(families):
            record = saved['geometric_paths'][5 * s + slot]
            fs = path_bernstein(m, form, s, lo, hi)
            assert record['t_interval'] == [str(lo), str(hi)] and len(record['results']) == len(fs) == 3
            for f, choice in zip(fs, record['results']):
                geometry_minimum = min(geometry_minimum, saved_scalar(f, choice)); scalar_count += 1
        own_id = labels.index((s, 0, 1)) * 15 + 7
        geometry_minimum = min(geometry_minimum, saved_scalar(m.short(own_id)[0, 0].r,
            saved['geometric_paths'][5 * s + 4]['result']))
        scalar_count += 1
    assert scalar_count == 39
    return {'short_rows': short_count, 'tail_rows': tail_count, 'short_controls_checked': 3 * short_count,
            'tail_controls_checked': 15 * tail_count, 'minimum': minimum, 'own_aliases_rederived': len(own),
            'geometric_groups': 15, 'geometric_scalar_controls_checked': scalar_count, 'geometric_minimum': geometry_minimum}


def main():
    started = time.monotonic()
    assert REC != ROOT.resolve() and sha(ROOT / 'box.json') == sha(REC / 'box.json')
    code = {p.name: sha(p) for p in sorted(ROOT.glob('*.py'))}
    assert hashlib.sha256(json.dumps(code, sort_keys=True).encode()).hexdigest() == read(REC / 'box_report.json')['code_sha256']
    assert any(zeta(i) is not None for i in range(3)), 'use the existing no-tail checker for a no-tail case'
    bank, manifest = load(0)
    assert manifest['bank_sha256'] == read(REC / 'tm_sources64_s0.json')['bank_sha256']
    m = Model(domain(0), degree())
    assert bank.ctx.d == m.ctx.d and bank.ctx.N == m.ctx.N and bank.ctx.exponents == m.ctx.exponents
    tail_results = {kind: check_tail(kind, manifest) for kind in ('short', 'tail')}
    time_result = check_time(bank, manifest, m)
    path_result = check_paths(bank, manifest, m)
    result = {'status': 'ORIGINAL_SAVED_TIME_AND_PATH_CHECKS_PASSED',
        'tail_comparisons': tail_results, 'time': time_result, 'paths': path_result,
        'time_cells': time_result['cells'], 'time_rows': time_result['rows'], 'time_minimum': time_result['minimum'],
        'short_path_rows': path_result['short_rows'], 'tail_rows': path_result['tail_rows'],
        'path_minimum': path_result['minimum'], 'own_aliases_rederived': path_result['own_aliases_rederived'],
        'geometric_path_groups': path_result['geometric_groups'],
        'all_tail_comparisons_TIME_PATH_checked': True,
        'stored_tail_weights_and_closed_cell_trees_used': True,
        'stored_time_multipliers_and_paths_used': True, 'stored_path_indices_and_refinements_used': True,
        'assertions_enabled': __debug__, 'optimizer_used': False, 'new_subdivision_tree_used': False,
        'basic_saved_multipliers': 'NOT_SAVED_IN_ORIGINAL_RUN', 'formal_verified': False,
        'source_bank_sha256': manifest['bank_sha256'], 'seconds': time.monotonic() - started}
    with (ROOT / 'saved-time-path-result.json').open('x') as stream:
        json.dump(result, stream, indent=2, allow_nan=False); stream.write('\n')
    print(json.dumps(result, allow_nan=False), flush=True)


if __name__ == '__main__':
    main()
