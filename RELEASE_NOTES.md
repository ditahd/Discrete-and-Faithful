# 0.1.0-prelim

Preliminary release of the certificates and verifiers for the computer-assisted
parts of a proof of Schwartz's preferred-interval conjecture for complex
hyperbolic triangle groups of finite orders 3 ≤ p ≤ q ≤ n.

- 36 archives, 42.0 GB compressed, 54.2 GB and 1,730,566 files extracted.
  `SHA256SUMS.assets` lists the archive hashes; the repository's manifests bind
  the size and SHA-256 of every extracted file.
- 1,470 cusp cases: `gen30` 80 and `small` 454 (p ≥ 18), `s16` 225 (p = 16, 17),
  `s15` 136, `s14` 172, `pB10`–`pB13` 18, 93, 139, 153 (p = 10–13, q > Q(p)).
- For p = 10–13 with q ≤ Q(p): 116 [S], 313 [C] and 313 branch certificates,
  4 [F] families and [F13].
- 895 exact and 156 outer obligations; peripheral, overlap and main-text checks;
  the `A_ref` computations for 3 ≤ p ≤ 9; a separate (3,3,n) certificate.
- One entry point, `verify.py` (CPython 3.11.15, hash-locked dependencies).

Not refereed and not a formal proof. The written arguments are not included; a
Lean formalization is in progress. See the README for scope and instructions.
