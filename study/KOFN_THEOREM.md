# A closed-form sharp k-of-n outage bound (statement, proof, verification)

**Status.** A correct, formally proved, machine-verified theorem. It is of
classical Fréchet/Boole / Rüschendorf ("m-of-n" reliability) lineage — the
distribution-free extremal-coupling family — not a claim of complete originality.
Its value here is concrete: it replaces the catastrophic certificate's linear
program over `2**n` outcome atoms with an exact `O(n log n)` closed form, and its
monotonicity corollary *proves*, rather than asserts, that the certificate's
worst case sits at an interval corner.

Date: 2026-09-20. Kernel: `src/grrc/joint_bounds.py`. Tests:
`tests/test_joint_bounds.py`.

## 1. Setup

Let `X_1, ..., X_n` be Bernoulli random variables with fixed marginals
`p_i = P(X_i = 1) in [0, 1]`. Write the **order statistics** of the marginals as
`p_(1) >= p_(2) >= ... >= p_(n)`. A *coupling* is any joint distribution of
`(X_1, ..., X_n)` with those marginals; nothing is assumed about dependence. Let
`S = X_1 + ... + X_n` be the number of events that occur. For a threshold
`1 <= k <= n` define the sharp worst case

    M(p, k) = sup over couplings of  P(S >= k).

Because the set of couplings with fixed marginals is a compact polytope (the
`2**n` atom masses under the marginal and total-mass equalities) and `P(S >= k)`
is linear in those masses, the supremum is attained and equals a linear program.

## 2. Theorem

> **Theorem (closed-form sharp k-of-n bound).**
> For every `1 <= k <= n`,
>
>     M(p, k) = min( 1,  min_{0 <= j <= k-1}  (1 / (k - j)) * SUM_{i = j+1}^{n} p_(i) ),
>
> and the maximum is attained by an explicit coupling. The inner minimand at
> index `j` is the sum of the `n - j` **smallest** marginals divided by `k - j`.

Write `S_j = SUM_{i > j} p_(i)` for that suffix sum and `M_raw = min_{0<=j<=k-1}
S_j/(k-j)`, so `M(p,k) = min(1, M_raw)`.

**Special cases.**
- `k = 1`: only `j = 0`, giving `M = min(1, SUM_i p_i)` — the **union bound**.
- `k = n`: the minimand at `j` is the mean of the `n - j` smallest marginals; the
  mean of a set is at least its minimum, so the min over `j` is achieved at
  `j = n-1`, giving `M = p_(n) = min_i p_i`.

## 3. Validity proof ( `<=`, elementary and pointwise )

Fix any coupling and any `j in {0, ..., k-1}`. Condition on the event `{S >= k}`.
Among the `n` variables, the `j` largest-marginal ones (a fixed index set `T`
with `|T| = j`) contribute at most `j` to `S`. Hence on `{S >= k}` the remaining
`n - j` variables (index set `B`, the `n - j` smallest marginals) satisfy
`SUM_{i in B} X_i >= k - j >= 1`. Dividing by `k - j`,

    1[S >= k]  <=  (1 / (k - j)) * SUM_{i in B} X_i      (pointwise, every outcome).

Indeed: if `S >= k` the right side is `>= 1`; if `S < k` the left side is `0` and
the right side is `>= 0`. Taking expectations (this is Markov's inequality
applied to the nonnegative variable `SUM_B X_i / (k-j)`),

    P(S >= k)  <=  (1 / (k - j)) * SUM_{i in B} p_i  =  S_j / (k - j).

This holds for **every** coupling and every `j`, so `P(S >= k) <= min_j S_j/(k-j)`;
intersecting with the trivial `P(S >= k) <= 1` gives `P(S >= k) <= M(p, k)`. ∎

This is exactly a **dual certificate**: put `lambda_0 = 0` and `lambda_i =
1/(k-j*)` on the `n - j*` smallest marginals (0 on the rest). For any subset `A`
with `|A| >= k`, `A` meets `B` in at least `k - j*` indices, so
`SUM_{i in A} lambda_i >= 1`; the dual objective `SUM_i lambda_i p_i` equals
`S_{j*}/(k-j*) = M_raw`. Weak LP duality then reproduces `M(p,k) <= min(1, M_raw)`.
`dual_certificate` returns these multipliers; the tests check dual feasibility on
all subsets and `objective == LP` when uncapped.

## 4. The minimizer's structure

Let `j*` be the **largest** minimizer of `S_j/(k-j)` over `j in {0,...,k-1}`, and
`M_raw = S_{j*}/(k - j*)`. Then

    p_(j* + 1)  <=  M_raw  <=  p_(j*).

*Proof.* Note `S_{j-1} = S_j + p_(j)`, so a short rearrangement gives the identity

    S_{j-1}/(k-j+1) <= S_j/(k-j)   iff   p_(j) <= S_j/(k-j).           (*)

If `p_(j*+1) > M_raw`, then removing the term `p_(j*+1) > M_raw` from the average
`M_raw` lowers it: `S_{j*+1}/(k-j*-1) < S_{j*}/(k-j*) = M_raw`, contradicting that
`j*` minimizes. Hence `p_(j*+1) <= M_raw` (vacuous if `j* = k-1` and `k > n`... but
`j*+1 <= k <= n`, and `p_(k) <= S_{k-1} = M_raw` holds trivially anyway). For the
upper bound, `j*` being the *largest* minimizer means `S_{j*-1}/(k-j*+1) > M_raw`
(strictly, else `j*-1` would also minimize); by (*) with `j = j*` this is
equivalent to `p_(j*) > M_raw`. (When `j* = 0` there is no `p_(0)` constraint and
the top block is empty.) ∎

This is what makes the explicit coupling below well defined: the `j*` largest each
have marginal `>= M_raw` (so they can cover an interval of length `M_raw`), and the
`n - j*` smallest each have marginal `<= M_raw` (so their arcs fit without
self-overlap on a circle of circumference `M_raw`).

## 5. Attainment proof ( `>=`, explicit coupling )

Let `U` be uniform on `[0, 1)`. Split the coordinates by `j*` into the top block
`T = {1,...,j*}` (largest marginals) and the bottom block `B = {j*+1,...,n}`.

**Uncapped case `M_raw < 1`.** Set the circumference `c = M_raw`.
- **Bottom block `B`.** Lay the arcs of lengths `p_(i)`, `i in B`, consecutively
  around the circle `[0, c)`, wrapping. Their total length is `S_{j*} = (k-j*) c`,
  i.e. exactly `k - j*` full turns, and each arc has length `p_(i) <= c` (Section 4)
  so it covers each point at most once. Therefore the covering **depth is exactly
  `k - j*` at every point of `[0, c)`** and `0` on `[c, 1)`. Put `X_i = 1[U in
  arc_i]`; this reproduces each bottom marginal `p_(i)`.
- **Top block `T`.** Each `p_(i) >= c` (Section 4). Let `X_i = 1` on all of
  `[0, c)` (length `c`) plus an extra piece of length `p_(i) - c` placed in
  `[c, 1)`. This reproduces each top marginal `p_(i)` and makes all `j*` top
  variables fire throughout `[0, c)`.

On `[0, c)`: exactly `j*` (top) `+ (k - j*)` (bottom) `= k` events fire, so
`S >= k`. On `[c, 1)`: the bottom block is silent, so `S` equals the number of
top events firing there, which is `<= j* < k` (since `j* <= k-1`), so `S < k`.
Hence `P(S >= k) = P(U in [0, c)) = c = M_raw = M(p, k)`. The bound is attained.

**Capped case `M_raw >= 1`.** Then `M(p,k) = 1`; we exhibit a coupling with
`S >= k` almost surely. Lay **all** `n` arcs (each `p_i <= 1`) consecutively around
the unit circle `[0, 1)`, wrapping. Total length `SUM p_i >= k` (the `j = 0` term
gives `SUM p_i / k >= M_raw >= 1`), and each arc covers a point at most once, so the
depth is `>= k` everywhere; thus `S >= k` a.s. and `P(S >= k) = 1`. `∎`

`attaining_coupling(marginals, k)` builds exactly this joint (as explicit atom
masses in the input coordinate order) for both regimes; the tests confirm it
reproduces the marginals and achieves `M(p,k)` to machine precision over hundreds
of random `(n, k, p)`.

## 6. Corollaries used by the certificate

**Monotonicity.** For fixed `k`, `M(p, k)` is non-decreasing in each `p_i`. Each
suffix sum `S_j` is non-decreasing in every marginal (raising a `p_i` can only
raise or leave the order-statistic suffix sums), each `S_j/(k-j)` is therefore
non-decreasing, and a pointwise minimum of non-decreasing functions (capped at 1)
is non-decreasing. Consequently the worst case of `M` over an interval box
`p_i in [lo_i, hi_i]` is attained at the all-`hi` corner and the best case at the
all-`lo` corner — this is why `certify_catastrophic` evaluates only the two
corners, and the theorem turns that from an assumption into a proof.

**Non-increasing in `k`.** `M(p, k)` is non-increasing in `k` (more services must
fail simultaneously), so the certifiable control burden falls as `k` rises.

**Tightness vs. classical bounds.** `M(p, k) <= min(1, SUM p_i / k)` (Markov, the
`j = 0` term) and `M(p, k) <= min(1, SUM p_i)` (union). For `k >= 2` the `j > 0`
terms make `M` strictly smaller than the union bound whenever the marginals are
not all equal — the sharp bound is genuinely tighter than what the certificate
used before.

## 7. Verification (machine-checked)

`tests/test_joint_bounds.py`:
1. **Closed form == LP** to `< 1e-9` over 1500 random `(n<=7, k, p)` — the
   theorem's numerical certificate (validity *and* attainment, since the LP
   computes the true sup over the coupling polytope), plus a second dense-simplex
   solver cross-check.
2. **Validity** — the bound dominates `P(S>=k)` of the independent coupling, the
   comonotone coupling (exactly `p_(k)`), and the constructed coupling.
3. **Attainment** — `attaining_coupling` reproduces the marginals and achieves the
   bound over 800 random cases, and matches the LP witness on a hand case.
4. **Duality** — `dual_certificate` is feasible on all `2**n` subset constraints,
   weak duality holds, and it is tight (== LP) whenever uncapped, over 400 cases.
5. **Corollaries** — monotonicity in each `p_i`, non-increasing in `k`,
   `<=` Markov/union, strictly `<` union for `k>=2`; boundary identities `k=1`
   (union) and `k=n` (min marginal).
6. **Input validation** on every entry point.

The catastrophic certificate now calls the closed form; its committed CSVs are
**byte-identical** to the LP-generated ones (only speed and exactness change).

## 8. Lineage and scope (stated plainly)

The extremal problem "max `P(S >= k)` over couplings with fixed Bernoulli
marginals" is classical: Fréchet (1935) / Boole bounds, Rüschendorf's (1991) sharp
distribution-free aggregation, and the reliability "`m`-of-`n`" literature all live
here. The contribution of this note is a **clean closed form with a
self-contained elementary proof of both directions and an explicit attaining
coupling**, machine-verified, that replaces a solver inside this repository's
catastrophic certificate and upgrades its corner argument from assertion to
theorem. It is a genuine theorem of classical lineage — not billed as a wholly new
result.
