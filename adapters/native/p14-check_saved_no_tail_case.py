"""One-case check of original p14 time multipliers and saved path groups."""
import json
import math
import time
import sys
from fractions import Fraction as Q
from pathlib import Path

import numpy as np
from iv import I, C, stack
from tm_bank import Bank, full_pair, to_model
from tm_sources64 import load, domain
from tm_positive import hermitian, tensor_bernstein
from tm_geometry import time_form, path_bernstein, scalar_positive
from rect_model import Model
from boxspec import degree, zeta
from catalogue import short_labels, coset, red, bw, baseword
from path_tm64 import controls, scalar_bounds, SPLIT

ROOT = Path.cwd()
REC = Path(sys.argv[1]).resolve()


def main():
    started = time.monotonic()
    bank, manifest = load(0)
    saved_time = json.loads((REC / 'time_tm64_s0.json').read_text())
    saved_path = json.loads((REC / 'path_tm64_s0.json').read_text())
    assert saved_time['source_bank_sha256'] == saved_path['source_bank_sha256'] == manifest['bank_sha256']
    assert all(zeta(i) is None for i in range(3)), 'this one-case check expects no tails'
    assert saved_time['rows'] == [['short', i, sign] for i in range(147) for sign in (0, 1)]
    m = Model(domain(0), degree())
    L, branch = time_form(m)
    forms = [4 * m.J - L, 4 * m.J + L]
    short_ids = np.arange(147) * 15 + 7
    P = stack([bank.P[:, int(i)] for i in short_ids] + [hermitian(f.coefficients()) for f in forms], axis=1)
    E = stack([bank.E[int(i)] for i in short_ids] + [hermitian(f.remainder()) for f in forms])
    tb = Bank(m.ctx, P, E, bank.H, bank.HE, list(map(int, short_ids)) + [3000, 3001])
    mass = [Q(0)] * 294
    addresses = [[] for _ in range(294)]
    time_cells, time_min = 0, math.inf
    for node in saved_time['nodes']:
        path = tuple(map(tuple, node['path']))
        assert all(type(axis) is int and 0 <= axis < m.ctx.d and side in (0, 1) for axis, side in path)
        bk = tb
        for axis, side in path:
            bk = bk.restrict(axis, side)
        for c in node['certificates']:
            row = c['row']
            assert row in node['input'] and row not in node['remaining']
            _, i, sign = saved_time['rows'][row]
            alpha, gamma = float.fromhex(c['alpha']), float.fromhex(c['gamma'])
            assert math.isfinite(alpha) and math.isfinite(gamma) and alpha > 0 and gamma >= 0
            aa, bb = np.array([3000 + sign]), np.array([15 * i + 7])
            wa, wb, gg = np.ones(1), np.array([alpha]), np.array([gamma])
            good, det = full_pair(bk, aa, bb, wa, wb, gg)
            low = float(det.l[0])
            if not bool(good[0]) and len(node['input']) <= 32:
                pp, ee = bk.residual(aa, bb, wa, wb, gg)
                ok, low, _ = tensor_bernstein(to_model(bk.ctx, pp[:, 0], ee[0]))
                good[0] = ok
            assert bool(good[0]) and math.isfinite(low) and low > 0, ('saved time failed', row, path)
            assert not any(path[:len(other)] == other or other[:len(path)] == path for other in addresses[row])
            addresses[row].append(path)
            mass[row] += Q(1, 2 ** len(path))
            time_min = min(time_min, low)
            time_cells += 1
    assert all(v == 1 for v in mass), 'time cells must cover every row exactly'
    print('Original time cells passed:', time_cells, flush=True)

    labels = short_labels()
    own, path_count, path_min = [], 0, math.inf
    assert [r['generator'] for r in saved_path['records']] == [0, 1, 2]
    for record in saved_path['records']:
        s = record['generator']
        expected = []
        for i in range(2205):
            nu, k, e = labels[i // 15]
            if coset(red(bw(i % 15 - 7) + baseword(nu, k, e))) == coset('SRC'[s]):
                own.append([s, i])
            else:
                expected.append(i)
        assert record['kind'] == 'short'
        assert [i for b in record['batches'] for i in b['indices']] == expected
        for b in record['batches']:
            ids = b['indices']
            cs = controls(m, to_model(m.ctx, bank.P[:, ids], bank.E[ids]), s)
            lows = np.min(np.stack([scalar_bounds(f) for f in cs]), axis=0)
            refined = b['tensor_refinements']
            assert len(refined) == len(set(refined)) and set(refined) <= set(ids)
            for source in refined:
                i = ids.index(source)
                results = [scalar_positive(f[i]) for f in cs]
                assert all(ok and math.isfinite(float(v)) and v > 0 for ok, v, _ in results)
                lows[i] = min(r[1] for r in results)
            assert np.all(np.isfinite(lows)) and np.all(lows > 0), ('saved path failed', s, ids)
            path_min = min(path_min, float(np.min(lows)))
            path_count += len(ids)
        print('Original path group passed:', s, flush=True)
    assert own == saved_path['own_aliases'] and len(own) == 10 and path_count == 6605

    geometry = []
    mu = 40 / (m.kap * I(15).sqrt())
    for s in range(3):
        families = [('negative_norm', -m.H, Q(0), Q(5)),
                    ('time_minus', 4 * m.J - L, Q(0), SPLIT[s]),
                    ('time_plus', 4 * m.J + L, Q(0), SPLIT[s]),
                    ('strict_core', -(m.J + m.H * mu / 2), SPLIT[s], Q(5))]
        for kind, A, lo, hi in families:
            results = [scalar_positive(f) for f in path_bernstein(m, A, s, lo, hi)]
            assert all(ok and math.isfinite(float(v)) and v > 0 for ok, v, _ in results)
            geometry.append((s, kind))
        i = labels.index((s, 0, 1)) * 15 + 7
        ok, low, _ = scalar_positive(m.short(i)[0, 0].r)
        assert ok and math.isfinite(float(low)) and low > 0
        geometry.append((s, 'own_leading_value'))
    assert geometry == [(r['generator'], r['kind']) for r in saved_path['geometric_paths']]
    result = {'status': 'ORIGINAL_SAVED_TIME_AND_PATH_CHECKS_PASSED',
              'time_cells': time_cells, 'time_rows': 294, 'time_minimum': time_min,
              'short_path_rows': path_count, 'path_minimum': path_min,
              'own_aliases_rederived': len(own), 'geometric_path_groups': len(geometry),
              'tail_rows': 0, 'stored_time_multipliers_and_paths_used': True,
              'stored_path_indices_and_refinements_used': True,
              'assertions_enabled': __debug__, 'optimizer_used': False,
              'basic_saved_multipliers': 'NOT_SAVED_IN_ORIGINAL_RUN',
              'formal_verified': False, 'seconds': time.monotonic() - started}
    (ROOT / 'saved-time-path-result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result), flush=True)


if __name__ == '__main__':
    assert __debug__, 'assertions must stay enabled'
    main()
