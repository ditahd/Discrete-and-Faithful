# Verification

```
verify.py --suite SUITE [--family FAMILY [--case bNNNN]] [--smoke] --output DIR [--data-root DIR]
```

`--data-root` is the directory that contains the extracted `payload/` (default:
the repository root).

## Guarantees of every run

- CPython 3.11.15 and the exact versions in `requirements.lock` are required.
- Assertions stay enabled: `python -O` and `PYTHONOPTIMIZE` are refused, and
  `adapters/execute.py` compiles every native source with `optimize=0`.
- One numerical process at a time, with BLAS, OpenMP, FLINT and Numba limited to
  one thread. Before every process at least 3.5 GiB of available RAM and 8 GiB
  of free disk are required.
- Native programs run in fresh scratch directories under the output directory,
  on copies of their inputs (hard links where the programs only read them).
- Only stored certificates are checked. No search, optimizer, linear program,
  multiplier proposal or new subdivision is run. Taylor-model banks are loaded
  under the engines' own source-hash and bank-hash guards, not regenerated.
- The output directory receives `result.json` (status; for every check its exit
  code, time, SHA-256 of the executed source and of the launcher, and the
  resources available before it), one log per check, and the native reports under
  `native/`. Use a fresh output directory for every run.
- Status `ALL_RELEASE_NUMERICAL_CHECKS_PASSED` is reported only by the unfiltered
  `--suite all` run, which first checks every extracted file against the
  manifests. Any narrower run reports `REQUESTED_SUBSET_PASSED`.

## Suites

Asset groups are the values of `--group` in `tools/fetch_assets.py`. Times are
rough single-process figures on a recent laptop.

| Suite | Checks | Asset groups | Time |
|---|---|---|---|
| `integrity` | size and SHA-256 of every extracted file against the per-file manifests | all | under an hour |
| `cusp` | the 1,470 cusp cases, three stages each and a fourth for pB (below) | `originals` + the family's group; pB also `inputs` | 0.5–60 min per case |
| `small` | p = 10–13, q ≤ Q(p): 116 [S] certificates, 312 [C] certificates and the order-30 one, 313 branch supplements, 4 [F] families, [F13] with its lemma programs `t_corner.py` and `t_fail.py`; `A_ref` common and boundary sections (3 ≤ p ≤ 9) | `originals` | about 7 h |
| `exact` | the six native exact programs on their saved covers, one job each: [N] 551, [S] 142, [F13] 60 and [F] on the A1 charts for p = 10, 11, 12: 46 + 47 + 49 obligations (895 in all) | `originals` | about 15 min |
| `outer` | for p ≥ 18, 16–17, 15 and 14: all 39 saved obligations, every saved leaf re-checked with the exact Bernstein predicates of `obl_exact.py` and its digest, then the ordered cover check `cover_check.py` (156 obligations, 447 leaves) | `originals` | about 2 min |
| `globals` | peripheral sums `vpc14/15/16/18`, overlaps `overlap14/15/16/18`, fixed-domain new-reflection sums `newrefl14/15/16` (exact traversal must equal the retained one), main-text constants and family specifications for p = 14, 15, 16, the four outer prose checks, and for p = 10–13 `vpcB`, `overlapB`, `maintextB` | `originals`, `inputs` | many hours (the three `newrefl` runs dominate) |
| `audits` | the whole-family audits `audit14.py`, `audit15.py`, `audit16.py`, `audit18.py` (`small`, `gen30`) and `audit9.py` (pB10–13), after restoring each case's registered engine sources: code hashes, stage reports, identities and domain coverage of every case | `originals`, `inputs` | about 15 min |
| `three-three-n` | the exact (3,3,n) certificate and its geometric-input audit, bound to the hash of the written geometric argument | `originals`, `inputs` | seconds |
| `all` | all of the above, integrity first | all | — |

### The stages of a cusp case

1. `basic` (`adapters/replay_basic.py`): the saved closed subdivision tree and its
   exact dyadic row cover; then every retained BASIC multiplier batch is evaluated
   with the accepting predicate recorded for it (`fast_pair`, `full_pair` or
   `tensor_bernstein` of the case's engine) on its saved cell.
2. `support-extended`: the engine's replay program (`replay18.py`, `replay15.py`,
   `replay16.py`, the pB case's `replay9*.py`, or for p = 14
   `adapters/native/p14-replay14-recorded-k.py`) re-tests every stored support,
   extended and coherence certificate on its stored cell with its stored
   multipliers.
3. `tails-time-path`: tail charts, time caps and path controls from the saved
   choices (`adapters/native/p1*-check_saved_*.py`, or the pB case's own checker).
   Their reports say `basic_saved_multipliers: NOT_SAVED_IN_ORIGINAL_RUN`; the
   BASIC multipliers are checked in stage 1.
4. `polar` (pB only, `adapters/replay_polar.py`): the case's exact polar-sum
   program, which must reproduce the rational ranges, counts and traversal digests
   of the retained trace in `fresh-polar/`.

A case is checked whatever result its original report records. BASIC covers the
rows it accepts; the remaining rows are covered by the support and extended
certificates of stage 2. The whole-family audits (`--suite audits`) check the
bookkeeping that joins the stages of every case.

## Smaller runs

- `--family` and `--case` restrict the `cusp` suite (and `--family` the `audits`
  suite) to one family or one case.
- `--smoke` runs a representative subset: in `cusp`, one case per family, tail
  type, checker variant and weight format; in `small`, one [S], one [C] and one
  branch certificate and one [F] family, besides the order-30 [C], [F13] and
  `A_ref` programs; in `exact`, the [S] program only; in `globals`, all
  checks except `vpc15/16/18` and `newrefl14/15/16`. `outer`, `audits` and
  `three-three-n` always run in full.

## Re-packing the archives

`tools/repack_assets.py --data-root . --output repacked-assets` rebuilds archives
from the extracted payload in manifest order with the normalized metadata and
requires byte identity with the published hashes. It needs space for the
re-packed archives; `--group` and `--asset` select a subset.
