"""Tests for the CAGE-2 language-model adaptive attacker; skipped unless CybORG is
installed (run from .venv-cage)."""
import json

import pytest

pytest.importorskip("CybORG")

from grrc.cage.agents import ATTACKERS  # noqa: E402
from grrc.cage.champion import ChampionAgent  # noqa: E402
from grrc.cage.env import run_episode  # noqa: E402
from grrc.cage.llm_attacker import STRATEGIES, SelectorAgent, history_prompt, parse  # noqa: E402


def test_parse_accepts_known_strategies_only():
    assert parse('{"strategy": "delayed_b_line", "reason": "x"}') == "delayed_b_line"
    assert parse('Here: {"strategy":"B_LINE"} ok') == "b_line"
    for bad in ["no json", '{"strategy": "nmap"}', "[1,2]", '{"foo": 1}']:
        assert parse(bad) is None


def test_history_prompt_summarises_each_strategy():
    text = history_prompt([("b_line", False, -5.0), ("b_line", True, -40.0),
                           ("delayed_b_line", True, -90.0)])
    assert "b_line: 2 tried, 1 breached" in text
    assert "delayed_b_line: 1 tried, 1 breached" in text
    assert "meander: not tried yet" in text
    assert "Episode 4" in history_prompt([("b_line", False, -5.0)] * 3)


def test_invalid_reply_falls_back_to_a_counted_random_choice():
    sel = SelectorAgent(type("B", (), {"reply": lambda self, m: {"text": "garbage"}})(), seed=3)
    choices = [sel.choose()[0] for _ in range(5)]
    assert all(c in STRATEGIES for c in choices) and sel.invalid == 5


def test_delayed_strategy_breaches_the_champion_through_the_selector():
    """End to end on the real environment (no LLM): the selector launches the chosen
    scripted attack, and the delayed start breaches the winner where b_line does not."""
    class Fixed:
        def __init__(self, s):
            self.s = s

        def reply(self, messages):
            return dict(text=json.dumps({"strategy": self.s}))

    SEED0 = 20261002
    def breaches(strategy):
        sel = SelectorAgent(Fixed(strategy))
        n = 0
        for i in range(8):
            s, _ = sel.choose()
            out, _ = run_episode(ChampionAgent(fallback="sleep"), ATTACKERS[s], 30, seed=SEED0 + i)
            sel.record(s, out["breached"], out["reward"])
            n += out["breached"]
        return n
    assert breaches("delayed_b_line") >= 4      # the blind spot
    assert breaches("b_line") == 0              # the winner handles what it was built for
