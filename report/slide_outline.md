# Grand Finale Slide-Deck Outline

*Suggested 10–12 slides for a longer finale talk. Keep one idea per
slide, big visuals, minimal text. Figures come from `outputs/figures/`.
Bracketed numbers are pulled from `report/research_brief.md` — refresh
before presenting.*

1. **Title.** "When Hospitals Cannot Afford Every Defense: Finding the
   Most Cost-Effective Protection Against Ransomware." Team names,
   NSRI 2026, Engineering & Technology. One-line safety note: *"A safe,
   fully simulated study — no real systems, no malware."*

2. **The stakes.** Photo-free, text-light: what a hospital loses when
   systems go down (records, lab, pharmacy, imaging). Cite doubling of
   attacks (Neprash 2022) and WannaCry's ~19,000 cancellations (NAO).

3. **The inequality.** Not all hospitals can afford the same defenses;
   the global "cybercapacity gap" (ITU 2024). This reframes the
   question from "best defense" to "best defense *per budget*."

4. **Research question.** One sentence, big type. The five defenses and
   the three neutral capacity profiles.

5. **How the simulation works.** Figure 1 (example synthetic network).
   Explain nodes/zones/edges and the safe state machine
   (healthy → compromised → detected → isolated → restored). Emphasize:
   we measure *lost service-hours*, not infected machines.

6. **What we tested.** The factorial design and trial counts
   ([N_TOTAL] simulations). Show the defense list and that we test them
   alone and combined.

7. **Result 1 — defenses work, combinations best.** Figure 2
   (disruption by strategy). Headline: full defense cut lost
   service-hours ~[REL_RED_FULL_IC] vs. baseline.

8. **Result 2 — the patch vs. detection tradeoff.** Figure 3 (heat
   map). Fast detection compensates for low patching; show the gradient.

9. **Result 3 — protect the backups.** Figure 6 (controlled backup
   experiment). Isolated backups drop compromise from [PBAK_CONNECTED]
   to [PBAK_ISOLATED].

10. **The budget answer.** Figure 4 (Pareto frontier) + Figure 7
    (cost-effectiveness). Headline: under tight budgets, the smartest
    portfolio combines cheap controls; detection improvement is the most
    consistently chosen control across all cost scenarios.

11. **Validation & reproducibility.** 12/12 validation checks pass;
    whole study reruns from one command with fixed seeds. This is our
    integrity guarantee.

12. **Limitations, ethics, and impact.** It's a model, not a prediction;
    no country claims; costs are relative. Closing message: *well-chosen,
    inexpensive combinations can deliver most of the achievable
    resilience — good news for under-resourced hospitals.* Thank-you +
    repo/QR.

---
*Design tips:* use the figure PDFs (vector, crisp on projectors); keep
the validated color palette consistent with the figures; never put a
number on a slide that isn't traceable to a generated CSV.
