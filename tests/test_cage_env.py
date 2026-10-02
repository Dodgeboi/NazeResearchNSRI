"""CAGE-2 integration tests; skipped unless the CAGE environment is installed
(``bash scripts/setup_cage.sh``, then run pytest from ``.venv-cage``)."""
import json

import pytest

pytest.importorskip("CybORG")

from grrc.cage.agents import ATTACKERS, react_restore  # noqa: E402
from grrc.cage.champion import ChampionAgent  # noqa: E402
from grrc.cage.env import run_episode  # noqa: E402
from grrc.cage.llm_defender import LLMDefender, parse  # noqa: E402


def test_episodes_are_reproducible_from_the_seed():
    a, _ = run_episode(react_restore(), ATTACKERS["b_line"], 30, seed=7)
    b, _ = run_episode(react_restore(), ATTACKERS["b_line"], 30, seed=7)
    assert a == b and -15.8 * 30 <= a["reward"] <= 0


def test_champion_fingerprints_the_seen_attackers_and_misses_the_delayed_one():
    seen = {}
    for name in ("b_line", "meander", "delayed_b_line"):
        agent = ChampionAgent()
        run_episode(agent, ATTACKERS[name], 30, seed=3)
        seen[name] = agent.loaded
    assert seen["b_line"] == "bline" and seen["meander"] == "meander"
    assert seen["delayed_b_line"] in ("sleep", "bline")
    repaired = ChampionAgent(fallback="bline")
    run_episode(repaired, ATTACKERS["delayed_b_line"], 30, seed=3)
    assert repaired.loaded in ("bline", "bline-fallback")


def test_llm_defender_parses_and_counts_invalid_replies():
    assert parse('{"action": "restore", "host": "op_server0"}') == ("Restore", "Op_Server0")
    assert parse('{"action": "Remove", "host": "User0"}') is None        # attacker foothold
    assert parse("no json") is None

    class Model:
        def __init__(self):
            self.n = 0

        def reply(self, messages):
            self.n += 1
            if self.n % 3 == 0:
                return dict(text="I would restore everything")
            return dict(text=json.dumps({"action": "Restore", "host": "Op_Server0"}), cost_usd=0.01)

    d = LLMDefender(Model(), "scripted")
    out, _ = run_episode(d, ATTACKERS["b_line"], 30, seed=1)
    assert out["calls"] == 30 and out["invalid"] == 10
    assert abs(out["cost_usd"] - 0.2) < 1e-9
