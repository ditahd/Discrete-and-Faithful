# Preferred interval for complex hyperbolic triangle groups: certificates and verifiers

Preliminary release `0.1.0-prelim`.

This repository holds the verification entry point, adapters, case catalog and
manifests for the computer-assisted parts of a proof of Schwartz's
preferred-interval conjecture for complex hyperbolic triangle groups of finite
orders. The certificates themselves are attached to the GitHub Release as 36
`.tar.gz` archives (42.0 GB compressed, 54.2 GB and 1,730,566 files extracted).
Every extracted file is bound to this repository by size and SHA-256.

**Status.** Preliminary and not refereed. This is not a formal proof: the written
arguments are not part of this release, and a Lean formalization is in progress.

## Statement and coverage

For integers 3 ≤ p ≤ q ≤ n with 1/p + 1/q + 1/n < 1: along the one-parameter
family of complex hyperbolic representations of the (p,q,n) triangle group, the
representation is discrete and faithful at every point of the closed preferred
interval, its parabolic endpoint included. The table lists the computer-checked
parts for each range of the smallest order p; Q(p) = 25, 17, 14, 13 for
p = 10, 11, 12, 13.

| Smallest order | Computer-checked parts | Size |
|---|---|---|
| p ≥ 18 | cusp strip (families `gen30`, `small`); outer interval; peripheral sums; overlap | 80 + 454 boxes; 39 outer obligations |
| p = 16, 17 | cusp strip (`s16`); outer interval; peripheral sums; overlap; main-text constants | 225 boxes; 39 outer obligations |
| p = 15 | cusp strip (`s15`); same global checks | 136 boxes; 39 outer obligations |
| p = 14 | cusp strip (`s14`); same global checks | 172 boxes; 39 outer obligations |
| p = 10–13, q > Q(p) | cusp strip with polar sums (`pB10`–`pB13`); peripheral sums; overlap; main-text checks | 18 + 93 + 139 + 153 boxes |
| p = 10–13, q ≤ Q(p) | canonical cell [N]; Type A strip [S]; Type B cusp [C]; families [F] and [F13] | 116 S, 313 C and 313 branch certificates, 4 F, 1 F13; 895 exact obligations |
| 3 ≤ p ≤ 9 | `A_ref` computations: common premises on a catalogue of domains; low-order boundary families | 129 domains; 5 families |
| (3,3,n), n ≥ 4 | separate exact certificate and geometric-input audit | one certificate |

The verifiers re-check stored certificates of explicit finite statements:
positivity of Hermitian matrix polynomials on parameter boxes (validated Taylor
models with outward-rounded ball or interval arithmetic), exact rational and
integer polynomial inequalities, identities in Coxeter groups, and coverage of
each parameter domain by the certified boxes. That these statements imply the
theorem is the content of the written arguments. The written argument for
3 ≤ p ≤ 9 uses Parker–Wang–Xie, Theorem 1.6, as an external premise for (3,3,n);
the separate (3,3,n) certificate checks the computational premises of a direct
argument for that family. Infinite orders are not covered.

## Running the checks

Requirements: Linux or macOS; CPython **3.11.15** exactly (for example via
`uv python install 3.11.15`); about 110 GB of free disk for the archives
(42 GB, removable after extraction), the payload (54 GB) and scratch space; and
at least 3.5 GiB of free RAM. The verifier checks 3.5 GiB of available RAM and
8 GiB of free disk before every process.

```sh
python3.11 -m venv .venv
.venv/bin/python -m pip install --require-hashes -r requirements-hashed.lock
```

Download the Release archives into `assets/` (or pass `--base-url` with the
Release download URL), then verify and extract them. Every archive, member size
and member hash is checked against the manifests in `manifests/`:

```sh
.venv/bin/python -I -B tools/fetch_assets.py --assets-dir assets --destination .
```

A subset can be fetched with `--group` (for example `--group originals --group s14`);
[docs/verification.md](docs/verification.md) lists the groups each check needs.

Run one case, one suite, or everything:

```sh
.venv/bin/python -I -B verify.py --suite cusp --family s14 --case b0073 --output verification-output/s14-b0073
.venv/bin/python -I -B verify.py --suite outer --output verification-output/outer
.venv/bin/python -I -B verify.py --suite all --smoke --output verification-output/smoke
.venv/bin/python -I -B verify.py --suite all --output verification-output/full
```

Suites: `integrity`, `cusp`, `small`, `exact`, `outer`, `globals`, `audits`,
`three-three-n`, `all`. Only the unfiltered `--suite all` run reports
`ALL_RELEASE_NUMERICAL_CHECKS_PASSED`; anything narrower reports
`REQUESTED_SUBSET_PASSED`. Each run writes `result.json`, one log per check and
the native reports into a fresh output directory. Do not use `python -O`: the
checks are assertions.

## Contents

- `verify.py` — the single entry point; it runs one numerical process at a time
  with one thread, assertions enabled, in fresh scratch directories.
- `adapters/` — launches the native verifiers from the payload unchanged and
  replays retained BASIC multipliers, saved outer leaves and polar traces;
  `adapters/native/` holds the checkers of the saved tail, time and path stages
  for p ≥ 14 and the support replay for p = 14.
- `tools/` — download and extraction (`fetch_assets.py`), suite dispatch,
  whole-family audits, smoke selection, and byte-identical re-packing of the
  archives (`repack_assets.py`).
- `manifests/` — `release-v1.json` (archives, sizes, hashes, corpus counts),
  `cases-v1.json` (the 1,470 cusp cases and their payload paths), and one
  per-file manifest per archive.
- `docs/verification.md` — what each suite checks, the inputs it needs, run times.
- `docs/formats.md` — payload layout and data formats.
- `SHA256SUMS.assets`, `SHA256SUMS.repository` — checksums of the archives and of
  this repository's files.
