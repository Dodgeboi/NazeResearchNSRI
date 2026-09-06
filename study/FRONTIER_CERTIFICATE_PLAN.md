# Frontier certificates and external benchmark evaluation

This extension is motivated by review of the existing hospital results.
Its hospital analysis is retrospective. The external benchmark choices and
checks below are committed before generating their candidate outcomes.
The upstream repository description and published problem definitions have
been consulted; this is not blinded review of another paper.

## Question and transfer rule

Given finite candidates with lower and upper objective bounds, compute the
candidates efficient in every matrix inside the Cartesian box (guaranteed)
and those efficient in at least one matrix (possible). Return a competing
candidate witnessing every exclusion. All objectives are minimized and ties
are retained. Report guaranteed subset, observed frontier, possible superset,
and the unresolved candidates; no probabilistic coverage claim is attached.

The proof uses each candidate's adverse corner against its competitors'
favorable corners, and the reverse configuration for possibility. Necessary
and possible efficiency are established optimization concepts; the paper
contributes their use to distinguish endpoint sensitivity from portfolio
stability, not invention of interval optimization.

## Hospital application

Use unchanged confirmation objective summaries. Hold five objectives fixed;
let the outage-frequency coordinate independently range from its k=4 value
to its k=1 value for each candidate. This box contains every shared k setting
but also allows combinations unattainable under a common k. Guarantees
therefore cover a broader perturbation set than the four observed frontiers.
Do not interpret failure to certify as actual instability. Check each of
the four observed frontiers lies between the certified sets.

## External published engineering problems

Use the upstream Python implementations of RE21 (four-bar truss) and RE22
(reinforced concrete beam), from Tanabe and Ishibuchi's published RE suite.
Archive a fixed Git commit, source-file hashes and MIT license. Do not modify
upstream functions. Generate 128 candidates per problem from uniformly
sampled decision-variable bounds, seed 2026090603, separately per problem.
The sampled finite set is the object of inference, not the continuous design
space. RE22's published violation objective is retained as defined upstream;
do not call every sampled design feasible.

Apply independent objective intervals of plus/minus 1%, 5%, and 10% of each
objective's sampled range, clipping lower bounds to zero for these
nonnegative objectives. The intervals are declared stress bounds, not
measured manufacturing uncertainty. Evaluate 1,000 uniform interior matrices
for each problem/bound combination, seed 2026090604 with successive offsets.
Test that every realized frontier contains the guaranteed set and lies
within the possible set. Report all combinations, including uninformative
certificates. Use a separate two-objective sorting implementation as the
frontier oracle, rather than the certificate routine.

## Exact and adversarial verification

For eight selected benchmark candidates with uncertainty on one objective,
enumerate all 256 endpoint assignments. The intersection and union of the
resulting frontiers must equal the certificate sets. Use the same fixed
selection rule: the first eight candidate rows, 5% bounds. Add hand-verifiable
tie, zero-width, dominated and crossing-interval cases, malformed bounds,
and invariance under a common positive affine change of units.

This evaluates transfer to independently defined engineering problems using
one research workflow. It is not an independently conducted replication,
validation of hospital realism, or held-out natural-language-checker accuracy.
The existing assertion audit remains a finite regression demonstration.
