# Running the LLM defender on your computer (free)

This runs a free, open-weight language model on your own machine as a cyber-defense
agent in the certified cyber range, and saves the results for the AIDC paper. Nothing is
uploaded anywhere; the model runs locally through [Ollama](https://ollama.com).

**Time:** about 1–3 hours for the full run on a recent laptop (Apple Silicon or a GPU is
much faster than CPU only); `--quick` takes about 15–30 minutes. **Disk:** about 5 GB for
the model. The run can be stopped and restarted; finished episodes are kept.

## 1. Install Ollama and a model

- macOS / Windows: install the app from https://ollama.com/download and open it.
- Linux: `curl -fsSL https://ollama.com/install.sh | sh`

Then, in a terminal:

    ollama pull qwen2.5:7b

If your computer has less than 16 GB of memory, use `llama3.2:3b` instead (and pass
`--model llama3.2:3b` below).

## 2. Get the code (Python 3.12)

    git clone https://github.com/Dodgeboi/NazeResearchNSRI.git
    cd NazeResearchNSRI
    git checkout claude/stoic-galileo-81yrtm
    python3 -m venv .venv
    source .venv/bin/activate            # Windows: .venv\Scripts\activate
    pip install -r requirements-revision.txt
    pip install -e . --no-deps

If you already have a clone, `git pull origin claude/stoic-galileo-81yrtm` instead.

## 3. Check the harness (a few seconds, no model needed)

    python scripts/run_llm_defender.py --dry-run

It should print eight episodes ending with
`certified share by adversary: {'adaptive': 0.25, 'typical': 1.0}`.

## 4. Run the evaluation

    python scripts/run_llm_defender.py --model qwen2.5:7b

It prints one line per episode (24 in total: 8 threat regimes × 3 seeds). If it stops
or you close the laptop, run the same command again; it continues where it left off.
Short on time? Use `--quick` (4 regimes × 1 seed) — the full run is better for the paper.

## 5. Send the results back

    git add data/llm_defender
    git commit -m "Add LLM defender results (qwen2.5:7b)"
    git push origin claude/stoic-galileo-81yrtm

Then tell Claude the results are pushed; it will add them to the paper.

## Troubleshooting

- *Cannot reach Ollama*: open the Ollama app, or run `ollama serve` in another terminal.
- *Model not found*: run `ollama pull <model>` with exactly the tag you pass to `--model`.
- *Very slow*: use `llama3.2:3b` or `--quick`; close other heavy apps.
- *Push rejected*: run `git pull --rebase origin claude/stoic-galileo-81yrtm`, then push again.

## What is recorded

`data/llm_defender/<model>/episodes.jsonl` holds every prompt and reply;
`summary.csv` has one row per episode next to the reference defenders' costs;
`run_record.json` records the Ollama version, the model digest and quantization, the
sampling settings, the git commit and SHA-256 hashes of the code and outputs. It records
the operating system name but no user names or file paths.
