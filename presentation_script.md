# Three-Minute Finalist Presentation Script

*Target: ~3 minutes (~420 words spoken). Plain language for a non-
cybersecurity judge. Numbers in [brackets] are read from the generated
results in `report/research_brief.md` — confirm the current values
before presenting; do not memorize stale numbers.*

---

**[0:00 — The problem]**

Imagine a hospital where the computers suddenly stop working. Doctors
can't open patient records, the lab can't return results, the pharmacy
can't dispense medicine. That's what ransomware does to hospitals — and
it's happening more and more. In one study, attacks on U.S. healthcare
organizations more than *doubled* in five years. When WannaCry hit the
UK's health service, nearly nineteen thousand appointments and
operations were cancelled.

**[0:30 — Why unequal resources matter]**

Here's the part people forget: hospitals don't all have the same money
or the same expert staff. A large, well-funded hospital can buy every
defense. A small clinic can't. So the real question isn't "what's the
best defense?" — it's *"if you can't afford everything, what should you
buy first?"*

**[0:55 — Research question and approach]**

That's our project. We asked: across hospitals of different sizes and
different security budgets, which defenses give the most protection for
the least cost? We couldn't experiment on real hospitals — that would be
dangerous and unethical — so we built a **computer simulation**. It's
completely safe: there's no real virus, no real hospital, just an
abstract model where a "compromise" is a colored dot spreading across a
network diagram.

**[1:30 — What we built and tested]**

We generated synthetic hospital networks — from 40-node clinics to
1,000-node hospitals — with all the real parts: records, labs, pharmacy,
imaging, backups. Then we simulated a ransomware-style spread and
measured what matters: not "how many computers got infected," but "how
many hours of patient services were lost." We tested five defenses —
segmentation, patching, fast detection, access controls, and isolated
backups — alone and combined, across **[N_TOTAL] simulated attacks**.

**[2:05 — Results]**

Three findings. First, **combinations win**: the full defense set cut
lost service-hours by about **[REL_RED_FULL_IC]** compared to an
undefended network. Second, **the cheapest controls do the heavy
lifting** — fast detection-and-isolation was the single most
cost-effective defense, and isolated backups cut the chance of losing
your backups from about half to nearly zero. Third — and this is the
important one for fairness — under a tight budget, the smartest move
wasn't the *most expensive* tool; it was the right *combination* of
cheap ones.

**[2:40 — Limitation and impact]**

Now, this is a model, not a crystal ball — it shows tradeoffs under our
assumptions, not exactly what any real hospital would experience, and we
make no claims about specific countries. But the message is hopeful: a
hospital that can't afford everything can still protect most of what
matters by choosing well. And because our whole study reruns from a
single command, anyone can check our work. Thank you.
