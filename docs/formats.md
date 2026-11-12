# Payload layout and formats

## Archives

The Release carries 36 independent `.tar.gz` archives. Extract all of them into
the same directory to obtain `payload/`; `tools/fetch_assets.py` does this and
checks every member. Each archive is below 1.9 × 10⁹ bytes.

| Group | Archives | Files | Extracted | Compressed |
|---|---:|---:|---:|---:|
| `originals` | 6 | 18,129 | 9.62 GB | 2.99 GB |
| `inputs` | 1 | 1,228 | 0.02 GB | 0.01 GB |
| `gen30` | 5 | 87,915 | 8.21 GB | 7.96 GB |
| `small` | 8 | 704,828 | 14.01 GB | 11.89 GB |
| `s14` | 3 | 165,243 | 5.34 GB | 4.63 GB |
| `s15` | 2 | 164,938 | 3.49 GB | 2.93 GB |
| `s16` | 4 | 246,754 | 5.51 GB | 4.68 GB |
| `pB10` | 1 | 26,500 | 0.64 GB | 0.57 GB |
| `pB11` | 2 | 80,739 | 1.90 GB | 1.65 GB |
| `pB12` | 2 | 110,221 | 2.63 GB | 2.28 GB |
| `pB13` | 2 | 124,071 | 2.82 GB | 2.42 GB |
| total | 36 | 1,730,566 | 54.19 GB | 42.03 GB |

The archives are deterministic: PAX tar of regular files only, in manifest order,
mode 0644, mtime 0, uid and gid 0, empty user and group names; gzip level 1 with
mtime 0 and no file name. `tools/repack_assets.py` rebuilds them byte for byte
from the extracted payload; the compressed bytes depend on the zlib version
(1.3.2 reproduces them).

## Manifests

- `manifests/release-v1.json`: version, corpus counts, normalization, and for every
  archive its name, group, size, SHA-256, file count, payload size, uncompressed
  tar size and SHA-256, and the SHA-256 of its per-file manifest.
- `manifests/<archive>.files.jsonl.gz`: one JSON line per member, in tar order,
  with `path`, `bytes` and `sha256`.
- `manifests/cases-v1.json`: the 1,470 cusp cases. Each record has `id`, `family`,
  `box`, `original` (the case's directory in the original packages), `run` and
  `weights` (its runtime and multiplier directories), `weight_format`,
  `fresh_bank_mapping` (pB only) and `recorded_bank_sha256` (bank hashes recorded
  in the original report).
- `SHA256SUMS.assets`: SHA-256 of the 36 archives. `SHA256SUMS.repository`:
  SHA-256 of every other file of this repository.

## Payload tree

```
payload/
  originals/Q3_P0_18_proof/          smallest order p ≥ 18 and the supplements
    cusp/{gen30,small}/bNNNN/          p ≥ 18 cusp cases
    cusp/eng2 eng3 eng4 v4 replay/     engines, shared catalogue inputs, replay programs
    outer/ appB/                       outer interval (39 obligations), peripheral sums and overlap
    p16/ p15/ p14/                     p = 16–17, 15, 14: cusp/sNN/bNNNN/, outer/, appB/, maintext/
    pB/                                p = 10–13, q > Q(p): cusp/pBNN/bNNNN/, cusp/engines_P.json, common/, maintext/
  originals/Q3_small_P0_p10_13/      p = 10–13, q ≤ Q(p)
    N_canonical/ S_strip_typeA/ CF_cusp_and_families/ F13_family13/   certificates, covers and verifiers
    A_ref/                             3 ≤ p ≤ 9 computations
  cusp/FAMILY/bNNNN/
    run/                               the case's engine sources, inputs and Taylor banks
    weights/                           BASIC multipliers
    fresh-polar/                       pB: retained polar trace (newrefl.json) and the program that produced it
    fresh-bank-mapping.json            pB: bank bindings (below)
  engines/pB/eng9_P_LEVEL/           the 33 registered pB engines
  inputs/33n-geometric-proof.tex     written argument bound by the (3,3,n) checker
  three-three-n/                     the (3,3,n) certificate and its checkers
```

A cusp case directory in the original packages holds its domain (`box.json`), its
report (`box_report.json`, with the engine code hash), `stages_done.json` and the
stage reports with the stored certificates: `basic_tm64_s0.json`,
`support18_s0.json`, `ext_rows_s0.json` (where present), `tail_short_tm64_s0.json`,
`tail_tail_tm64_s0.json`, `time_tm64_s0.json`, `path_tm64_s0.json`, the bank
manifests `tm_sources64_s0.json` and (where present) `tm_ext_s0.json`, and for pB
the polar report `newrefl.json`.

## Native formats

| Content | Representation |
|---|---|
| cusp domains, rows, trees | JSON with exact rational strings, hexadecimal binary64 multipliers, row and source identifiers and closed subdivision addresses |
| Taylor banks | compressed NumPy `.npz` (interval endpoint arrays, source indices, Hermitian data) with a JSON manifest that binds the bank hash and the hashes of the sources that generated it |
| BASIC multipliers | `weights/basic-weights.jsonl` index and `basic-weights-NNNNNN.npz` batches (below) |
| [S], [C], [F], [F13] | `.npz` certificates in their own schemas, read by `pack.py`, `cpack.py` and the family programs |
| exact obligations | JSON saved covers with rational and integer data, checked by the native exact polynomial programs |
| outer obligations | `res_*.json` leaf lists with digests |
| polar sums | JSON rational ranges with per-base-cell and aggregate trace digests |
| (3,3,n) | exact JSON certificate |

### BASIC multipliers

Each line of `basic-weights.jsonl` names one batch: `path`, `sha256`, `rows`,
`cell_path` (the saved cell), `accepted_methods` (one per row) and, where present,
`original_node_index`. Each batch `.npz` holds `row_ids` (int64), `source_pairs`
(int64, rows × 2), `wa`, `wb`, `gamma`, `margin` (float64 vectors) and `exponents`
(int64 basis table). `margin` is informative only: positivity is recomputed from
the bank and the coefficients. `weight_format` is `retained-basic-npz-v1` for
every case except `s14/b0073` (`captured-basic-npz-v1`), whose batches come from
a separate capture; both have the fields above.

The original stage reports record digests of the BASIC multipliers, not the
multipliers. The multipliers in `weights/` were computed on the same saved cells
for the same accepted rows and are checked with the same predicates; bit identity
with the multipliers behind the recorded digests is not claimed.

### pB bank bindings

Some pB banks in `run/` were regenerated from the same native sources and their
bytes differ from the hash recorded in the original report. For each bank,
`fresh-bank-mapping.json` gives both hashes and the hashes of the native sources;
the pB replay programs use it to join the bank to the original report.
