"""Tests for the primitive-action attacker interface; skipped unless CybORG is installed
(run from .venv-cage). The two gates here are what the earlier primitive attempt lacked: that
the inverted-control interface is faithful, and that the primitive action menu can actually
express a breach."""
import pytest

pytest.importorskip("CybORG")

from CybORG.Agents import B_lineAgent  # noqa: E402

from grrc.cage.agents import react_restore, sleep_defender  # noqa: E402
from grrc.cage.attacker_env import run_defender_vs_red  # noqa: E402
from grrc.cage.champion import ChampionAgent  # noqa: E402
from grrc.cage.env import run_episode  # noqa: E402
from grrc.cage.llm_primitive_attacker import ScriptedPrimitiveAttacker, parse  # noqa: E402

SEED0 = 20261002


def test_parse_accepts_known_actions_only():
    assert parse('{"action": "impact", "target": "Op_Server0"}') == ("impact", "Op_Server0")
    assert parse('go {"action":"EXPLOIT","target":"10.0.0.1"} ok') == ("exploit", "10.0.0.1")
    assert parse('{"action":"sleep"}') == ("sleep", "")
    for bad in ["no json", '{"action":"nmap"}', "[1]", '{"target":"x"}']:
        assert parse(bad) is None


def test_inverted_control_matches_run_episode():
    """Gate 1: replaying B_line's own actions through the attacker interface (Red stepped
    externally) reproduces its breach outcomes from run_episode (Red registered)."""
    def champ():
        return ChampionAgent(fallback="sleep")
    for make in (react_restore, sleep_defender, champ):
        for i in range(8):
            a, _ = run_episode(make(), B_lineAgent, 30, seed=SEED0 + i)
            b, _ = run_defender_vs_red(make(), B_lineAgent(), 30, seed=SEED0 + i)
            assert a["breached"] == b["breached"]


def test_primitive_interface_can_breach():
    """Gate 2: a scripted greedy policy over the primitive action menu breaches the undefended
    Sleep defender (so a failure to breach is the attacker's, not the interface's), and the
    winner's fingerprint handles the same immediate attack."""
    sleep_breaches = sum(run_defender_vs_red(sleep_defender(), ScriptedPrimitiveAttacker(),
                                             40, seed=SEED0 + i)[0]["breached"] for i in range(10))
    champ_breaches = sum(run_defender_vs_red(ChampionAgent(fallback="sleep"),
                                             ScriptedPrimitiveAttacker(), 40, seed=SEED0 + i)[0]["breached"]
                         for i in range(10))
    assert sleep_breaches >= 8        # the interface can express a full breach path
    assert champ_breaches == 0        # a direct primitive attack does not beat the fingerprint
