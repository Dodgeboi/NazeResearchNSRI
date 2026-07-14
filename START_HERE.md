# START HERE — A Plain-Language Guide to This Project

Hi! This guide explains the whole project in normal words, with **no
jargon**, and it points you to the exact files where you can *see* the
real data with your own eyes. Read this first, then open the files it
mentions.

---

## 1. What is this project, in one sentence?

> We built a **safe pretend model of a hospital's computer network** and
> let a **pretend ransomware attack** loose in it thousands of times, to
> figure out **which security protections give hospitals the most safety
> for the least money.**

Nothing here is real malware. There is no real hospital and no real
virus. It's all a simulation — like a flight simulator, but for a
cyber-attack. A "hacked computer" is just a dot on a map that changes
color.

---

## 2. The big idea (an analogy)

Imagine a hospital is a **big house with many rooms**:

- Some rooms are **patient records**, some are the **lab**, some are the
  **pharmacy**, some are **backups** (spare copies of everything), etc.
- **Doors** connect the rooms so people (and data) can move around.

Now imagine a **fire** (the ransomware) starts in one room. It spreads
through open doors to other rooms. If it reaches the important rooms, the
hospital can't treat patients.

The **defenses** we test are like:

| Real defense | House analogy |
|---|---|
| **Segmentation** (separating the network into zones) | Adding **fire doors** so the fire can't spread everywhere |
| **Patching** (fixing software weaknesses) | Using **fireproof materials** in rooms |
| **Detection & isolation** (spotting the attack fast and cutting it off) | **Smoke alarms + sprinklers** that catch the fire early |
| **Isolated backups** (keeping spare copies offline) | Keeping a **spare copy of everything in a fireproof safe** in a separate building |
| **Identity controls** (locking down passwords/logins) | Putting **extra locks** on the master key room |

The whole project asks: **if you can't afford every protection, which
ones should you buy first?**

---

## 3. Why does this matter in real life?

Hospitals really do get hit by ransomware, and when they do, patients
get hurt (cancelled surgeries, delayed care). But hospitals around the
world have **very different budgets**. A rich hospital can buy every
defense; a small clinic can't. So the useful question isn't "what's the
best defense?" — it's **"what's the smartest thing to buy on a tight
budget?"** That's what this project figures out.

(The real-world facts we cite — like the WannaCry attack cancelling
~19,000 UK appointments — are in `report/references.md`, and every one
was checked by hand.)

---

## 4. How the computer actually does it (step by step)

Think of it like rolling dice many times and writing down what happens:

1. **Build a pretend hospital network.** The computer randomly creates a
   hospital with, say, 250 "computers" grouped into zones (records, lab,
   pharmacy, backups, etc.) and "connections" between them.
   → *You can see one of these drawn out in* **`outputs/figures/fig1_network_architecture.png`**.

2. **Start a pretend attack.** One computer gets "infected" (turns red).

3. **Let time tick forward.** Each tick (we say 1 tick = 15 minutes),
   the infection *tries* to spread to connected computers. Whether it
   succeeds is a dice roll, and the defenses change the odds.

4. **The defenders fight back.** Depending on the settings, the hospital
   might *detect* the infection and *isolate* (unplug) infected
   computers, and later *restore* them from backups.

5. **Measure the damage** — not by counting infected computers, but by
   asking **"how many hours were important patient services down?"**
   That's what actually matters to patients.

6. **Do it all again** with different random luck, different hospital
   sizes, different defenses, different budgets... **28,225 times.**

7. **Write every single run down as one row in a spreadsheet.** Then
   summarize.

Because it's random, one run isn't meaningful — but 28,225 runs show a
clear *pattern*. That's what "Monte Carlo" means: repeat a random thing
many times and look at the average picture. (Same idea as flipping a
coin — one flip tells you nothing, 10,000 flips tell you it's fair.)

---

## 5. THE TANGIBLE STUFF — files you can open and read right now

This is the part you asked about. **Yes, there is real data you can
open and understand.** Here's where to look, easiest first:

### A) The pictures (open these first — no reading required)
Folder: **`outputs/figures/`**

| File | What it shows you |
|---|---|
| `fig1_network_architecture.png` | What a pretend hospital network looks like (the "house with rooms") |
| `fig2_disruption_by_strategy.png` | Which defenses caused the least service disruption (shorter bars = better) |
| `fig3_patch_detection_heatmap.png` | A colored grid: dark = bad (attack wins), light = good. Shows patching vs. speed of detection |
| `fig4_pareto_frontier.png` | Money (left-right) vs. safety (up-down): the "best value" defenses |
| `fig5_facility_comparison.png` | Small clinic vs. big hospital — who suffers more |
| `fig6_backup_strategies.png` | Proof that **offline backups basically never get hit** (the bars drop to zero) |
| `fig7_cost_effectiveness.png` | "Bang for your buck" — safety gained per dollar-point spent |

### B) The plain-English writeup with the real answers
Folder: **`report/`**

- **`report/research_brief.md`** ← the main paper. Every number in it
  came straight from the data files. Read this to get the whole story.
- **`report/abstract.md`** ← the 1-paragraph summary.

### C) The actual data tables (open in Excel or Google Sheets)
Folder: **`data/`**

- **`data/raw/standard_main_results.csv`** ← THE BIG ONE. **15,750 rows**,
  one row = one simulated attack. Every column is explained in
  `docs/data_dictionary.md`. Open it and scroll — this is the raw
  evidence. Columns include how many computers got infected, how many
  service-hours were lost, whether it was "catastrophic," etc.
- **`data/processed/standard_baseline_comparisons.csv`** ← the summary
  that answers "how much did each defense help vs. doing nothing?"
- **`data/processed/standard_best_portfolios.csv`** ← the best defense
  bundle for each budget level.
- Every number in every figure is also saved as a small CSV in
  **`outputs/tables/`** (e.g. `fig6_backup_strategies_data.csv`), so you
  can check that the pictures match the data.

> **Tip:** if a `.csv` file looks like a wall of commas in a text editor,
> open it in **Google Sheets** (File → Import) or **Excel** and it turns
> into a normal spreadsheet.

---

## 6. What did we actually find? (the answers, in plain words)

All of these come from the data files above:

1. **Doing nothing is a disaster.** With no defenses, in a medium
   hospital, an attack caused a "catastrophic" outage **95% of the time**.
2. **A full set of defenses works incredibly well** — it cut lost
   service-hours by about **98%** (from ~188 hours down to ~4).
3. **The single most valuable cheap defense** was **catching the attack
   fast and cutting it off** ("detection & isolation").
4. **Offline backups are almost magic**: when backups were kept fully
   offline, the chance of the attackers destroying them dropped from
   **76% to basically 0%**. (See `fig6`.)
5. **The most important lesson for tight budgets:** the smartest choice
   was **not** the single most expensive tool — it was a **smart
   combination of cheaper ones**. Poorer hospitals get the most benefit
   per dollar from fast detection + offline backups + some segmentation.
6. **The hard truth:** the lowest-resource hospitals **couldn't fully
   protect themselves even at the highest budget we tested** — which is
   exactly why this fairness question matters.

---

## 7. Want to run it yourself? (optional, ~2 minutes)

You need a computer with Python 3.11+ installed. Then, in a terminal,
inside the project folder:

```bash
pip install -e .                       # installs it (one time)
python -m grrc.cli validate            # checks the model behaves logically (should say 12/12 passed)
python scripts/reproduce_all.py --profile quick   # runs a fast mini-version and makes all the files
```

That regenerates the data and figures. To reproduce the full-size
results from the paper, use `--profile standard` instead (takes ~10-30
minutes). Because we use fixed "random seeds," **you'll get the exact
same numbers we did** — that's how anyone can check our work.

---

## 8. The most important honesty note

This is a **model**, not a crystal ball. It shows what happens **under
our assumptions** (which are all written down in
`docs/assumptions.md`). It does **not** predict exactly what would happen
at any real hospital, and it makes **no claims about specific countries**.
We were careful never to make up any numbers — everything traces back to
the data files. How an AI assistant helped build it is disclosed openly
in `report/ai_transparency.md`.

---

## 9. Where everything lives (quick map)

```
START_HERE.md        <- you are here
README.md            <- the fuller, more technical version of this guide
report/              <- the paper, abstract, presentation, Q&A prep
  research_brief.md      (read this for the full story + real numbers)
outputs/figures/     <- the 7 graphs (PNG pictures)
data/raw/            <- every simulated attack, one per row (the evidence)
data/processed/      <- summary tables (the answers)
outputs/tables/      <- the exact numbers behind each figure
docs/                <- how it works, all assumptions, the plan, limitations
src/grrc/            <- the actual program code (Python)
tests/               <- automatic checks that the code is correct
```

Any time you're lost: open **the pictures in `outputs/figures/`** and
read **`report/research_brief.md`**. That's the heart of it.
