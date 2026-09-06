# Archived external benchmark source

Upstream: https://github.com/ryojitanabe/reproblems

Exact commit: `7876b4e465eac381a256e461d1310b8bb2b92846`

Files are unchanged copies of `reproblem_python_ver/reproblem.py`,
`LICENSE.txt`, and `README.md` (the last renamed `UPSTREAM_README.md`).
Retrieved 2026-09-06. Python source SHA-256:
`d55bf2007fd210de01793b655514d9d533f6c4fbc1b3bea5d993e5b18979ed12`.

Ryoji Tanabe and Hisao Ishibuchi, *An easy-to-use real-world multi-objective
optimization problem suite*, Applied Soft Computing 89, 106078 (2020).
https://doi.org/10.1016/j.asoc.2020.106078

Only RE21 and RE22 are invoked. Their objective functions and discretization
are used exactly as archived, not reimplemented or repaired here. This
evaluation concerns finite objective tables and does not validate the
physical accuracy of the benchmark's engineering equations. RE22's second
objective is constraint violation, not a claim that all sampled designs are
feasible. The upstream MIT license and attribution apply to these files.
