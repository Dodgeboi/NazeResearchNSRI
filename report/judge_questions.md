# Judge Q&A Preparation Sheet

*Two-minute drill: concise, honest answers. Each has a one-line "short
answer" to say first, then a backup detail if pressed. Never overclaim —
"the model shows…", not "hospitals will…".*

---

**Q: Why a simulation instead of real hospital data?**
Short: Real ransomware experiments on hospitals are impossible and
unethical, and detailed incident data is confidential. A simulation lets
us test dozens of defenses across thousands of scenarios safely and
transparently. Backup: it also lets us change one variable at a time,
which you can't do with messy real-world incidents.

**Q: How did you choose the infection probabilities?**
Short: We picked values that reproduce *qualitative* behaviors from
public reports — fast spread on flat networks, long dwell time without
monitoring — not any single real incident. Backup: every parameter is in
`docs/assumptions.md`, and our patch×detection sweep plus validation
suite test how sensitive results are to them.

**Q: How do you know the model is valid?**
Short: We wrote 12 automated validation tests — for example, with zero
transmission only the entry node is infected; with certain transmission
and no defenses, exactly the reachable network is infected; isolated
backups are never reached. All 12 pass (`docs/model_validation.md`).
Backup: we also show results converge as trials increase (100→1,000).

**Q: Why are costs abstract points, not dollars?**
Short: Real prices vary hugely by country, vendor, and what a hospital
already owns, so any dollar figure would be fake precision. We use
relative "effort points" and then re-test every conclusion with costs
scaled ±50%. Backup: the best-defense rankings stayed stable under
rescaling, so they don't depend on the exact numbers.

**Q: Does this prove what every hospital should do?**
Short: No — and we're careful to say so. It identifies tradeoffs under
our assumptions. A real hospital would need its own assessment. Backup:
we never call any portfolio "universally optimal"; the point is a
*method* for finding cost-effective combinations.

**Q: What makes the project global?**
Short: We compare neutral capacity profiles — resource-constrained,
intermediate, high-capacity — which reflect the real worldwide gap in
cybersecurity resources (ITU documents this). The insight applies
anywhere budgets are limited. Backup: we deliberately avoid naming
countries.

**Q: Why avoid comparing named countries?**
Short: Our model can't support country-level claims — that would need
real national data we don't have, and it risks unfair stereotyping.
Neutral profiles make the *resource* point without pretending to
describe any real place.

**Q: How did AI contribute?**
Short: We used Claude to help design the code structure, write and debug
the implementation, and organize the writing. We reviewed and tested
everything, verified every source by hand, and all results come from
running our program. It's fully disclosed in `report/ai_transparency.md`.
Backup: no result or citation was AI-invented; unfilled values stay
visible as placeholders.

**Q: Did you create ransomware?**
Short: Absolutely not. There is no malware, no exploit, no scanner, no
real system touched anywhere. A "compromise" is just a state label on a
dot in a graph. The whole project is defensive.

**Q: How is this Engineering & Technology, not just cybersecurity?**
Short: We built a working software system — a network generator, a
simulation engine, an optimizer, a statistics and figure pipeline — and
used it to solve a constrained optimization problem (best resilience per
budget). That's systems engineering and computational modeling.

**Q: Which assumption most affects the results?**
Short: The base spread rate and the detection/isolation model matter
most — they set how fast an attack outruns the defenders. That's exactly
why detection speed came out as the most cost-effective control. Backup:
the patch×detection heat map (Figure 3) shows this sensitivity directly.

**Q: What would you add with more time?**
Short: A global sensitivity analysis over all parameters, a data-
extortion outcome (not just service loss), attacker adaptation, and —
if we could obtain it ethically — anonymized real topology statistics to
calibrate the synthetic generator. Backup: also human-factors modeling
of clinical workarounds during outages.

---

### Reset lines if a question goes sideways
* "That's a great question and a real limitation — here's how we bounded
  it…"
* "We can't claim that from our model, but what we *can* say is…"
* "Let me point you to the exact assumption / test that covers that."
