"""GRRC — Global Ransomware Resilience under Constraint.

A fully synthetic, defensive Monte Carlo simulation study of how
cybersecurity defense portfolios affect ransomware-style compromise
propagation and critical-service disruption in modeled healthcare
networks of different sizes and cyber-capacity levels.

SAFETY NOTE: this package contains no malware, exploit code, scanners,
or code that touches real systems. A "compromise" is an abstract state
transition on a synthetic graph (HEALTHY -> COMPROMISED -> DETECTED ->
ISOLATED -> RESTORED). Nothing in this package sends network traffic.
"""

__version__ = "1.0.0"
