# Running the LLM defender on your own computer (free)

This runs a free, open-weight language model **on your own machine** as the cyber-defense
agent in the certified cyber range, and saves the results for the paper. Nothing leaves
your computer: the model runs locally through [Ollama](https://ollama.com), and the only
network use is downloading the model once and pushing the results to GitHub.

| | |
|---|---|
| Time | about 15–30 min with `--quick`; 1–3 h for the full run (faster with Apple Silicon or a GPU) |
| Disk | about 5 GB (`qwen2.5:7b`) or 2 GB (`llama3.2:3b`) |
| Memory | 16 GB or more for `qwen2.5:7b`; otherwise `llama3.2:3b` |
| Cost | free |

The run can be stopped at any time (Ctrl+C, closing the laptop) and restarted with the
same command; finished episodes are kept.

---

## Step 1 — Check your memory and pick a model

- **macOS:** Apple menu → About This Mac → *Memory*.
- **Windows:** Settings → System → About → *Installed RAM*.
- **Linux:** run `free -g` and read the *total* column.

16 GB or more: use **`qwen2.5:7b`**. Less than 16 GB: use **`llama3.2:3b`**.
Below, replace `MODEL` with the one you picked.

## Step 2 — Install Ollama

- **macOS / Windows:** download from https://ollama.com/download, install it, and open
  the Ollama app (it runs in the menu bar / system tray).
- **Linux:** `curl -fsSL https://ollama.com/install.sh | sh`

Open a terminal (macOS: *Terminal*; Windows: *PowerShell*) and download the model:

    ollama pull MODEL

Check that it answers (type `/bye` to leave):

    ollama run MODEL "Say hello in five words."

## Step 3 — Install Python 3.12 and Git

Check what you have:

    python3 --version        # Windows: py --version
    git --version

If Python is missing or older than 3.12, install it from https://www.python.org/downloads/
(on Windows, tick *Add python.exe to PATH*). If Git is missing: macOS runs
`xcode-select --install`; Windows installs from https://git-scm.com/download/win; Linux uses
`sudo apt install git` (or your distribution's equivalent).

## Step 4 — Get the code

    git clone https://github.com/Dodgeboi/NazeResearchNSRI.git
    cd NazeResearchNSRI
    git checkout claude/stoic-galileo-81yrtm

If the repository is private, Git asks you to sign in; the easiest route is
GitHub Desktop (https://desktop.github.com): *File → Clone repository*, then switch to the
branch `claude/stoic-galileo-81yrtm` and open the folder in a terminal.

Already have a copy? Update it instead:

    cd NazeResearchNSRI
    git checkout claude/stoic-galileo-81yrtm
    git pull origin claude/stoic-galileo-81yrtm

## Step 5 — Set up Python

macOS / Linux:

    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements-revision.txt
    pip install -e . --no-deps

Windows (PowerShell):

    py -3.12 -m venv .venv
    .venv\Scripts\Activate.ps1
    pip install -r requirements-revision.txt
    pip install -e . --no-deps

(If PowerShell refuses to run the activate script, run
`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once and try again.)

Whenever you open a new terminal later, `cd NazeResearchNSRI` and run the *activate* line
again before the commands below.

## Step 6 — Check the harness (seconds, no model needed)

    python scripts/run_llm_defender.py --dry-run

The last line must read:

    wrote data/llm_defender/dry-run-greedy: 8 episodes; certified share by adversary: {'adaptive': 0.25, 'typical': 1.0}

## Step 7 — Quick run first (about 15–30 minutes)

Make sure the Ollama app is open, then:

    python scripts/run_llm_defender.py --model MODEL --quick

It prints one line per episode (4 in total), for example
`[1/4] typical|assumed|eps=0.05|k=1 seed=1: certified, cost=3, steps=5, invalid=0, ...`.

## Step 8 — Full run (1–3 hours)

    python scripts/run_llm_defender.py --model MODEL

24 episodes (8 threat scenarios × 3 seeds). The 4 quick episodes you already ran are
kept, so it continues from there. If it stops, run the same command again.

## Step 9 — Send the results back

    git add data/llm_defender
    git commit -m "Add LLM defender results (MODEL)"
    git push origin claude/stoic-galileo-81yrtm

Then tell Claude the results are pushed; it will add your model next to Claude in the
paper's results table and update the text.

---

## Troubleshooting

| Message | Fix |
|---|---|
| `Cannot reach Ollama at http://localhost:11434` | Open the Ollama app, or run `ollama serve` in a second terminal. |
| `model 'MODEL' not found` | Run `ollama pull MODEL` with exactly the tag you pass to `--model`. |
| Very slow (minutes per line) | Use `llama3.2:3b`, close other heavy apps, or stop after `--quick`. |
| `ModuleNotFoundError: grrc` | Activate the environment (Step 5) and rerun `pip install -e . --no-deps`. |
| `git push` rejected | `git pull --rebase origin claude/stoic-galileo-81yrtm`, then push again. |
| Push asks for a password | Use GitHub Desktop, or create a token at https://github.com/settings/tokens and paste it as the password. |

## What is recorded

`data/llm_defender/MODEL/episodes.jsonl` holds every prompt and reply; `summary.csv` has
one row per episode next to the reference defenders' costs; `run_record.json` records the
Ollama version, the model digest and quantization, the sampling settings, the git commit
and SHA-256 hashes of the code and outputs. It records the operating-system name but no
user names or file paths.
