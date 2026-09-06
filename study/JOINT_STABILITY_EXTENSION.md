# Price-region boundary check

Added 2026-09-06 after inspecting the first joint-stability run. The original
72 endpoint certificates became 21 at radius 0.50. The simultaneous sampling
screen retained three baseline portfolios at nominal prices but only two
at radius 0.50: the intermediate profile lost its certificate.

The original monotone absolute-price region permits a segmentation or
backup upgrade to become free when adjacent ladder prices coincide.
This is allowed by the recorded design, but it raises a substantive
question about whether the results depend on that boundary.

Add a second, nested tariff region. Retain the original absolute-price box
and also require each adjacent modeled ladder gap to be at least
(1-radius) times its nominal gap. At radius 0.50, an upgrade must retain
at least half its original incremental price. Apply this separately to cost
and burden. These are analyst-chosen bounds, not measured price uncertainty.

Run every original radius, bootstrap seed and alpha in both regions.
Use the same resamples for both regions. Extend the support function by
intersecting each two-price rectangle with y-x >= minimum gap. Check its
vertices against an independent linear program. Require the original
region's outputs to reproduce the first run exactly, and require retention
in the nested region to contain that in the original region.

Report the two regions side by side, including negative results. This
amendment is retrospective and must not be described as pre-specified
before the initial joint analysis.
