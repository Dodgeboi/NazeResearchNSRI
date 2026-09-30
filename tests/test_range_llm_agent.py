import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pandas as pd
import pytest

from grrc.attack_graph import build_graph, load_bundle
from grrc.hospital_attack_model import build_model
from grrc.range import DefenseRange, default_regimes
from grrc.range.llm_agent import (OllamaAgent, ScriptedAgent, ollama_metadata, parse_action,
                                  run_episode)
from grrc.range.policies import greedy_order

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def model():
    return build_model(build_graph(load_bundle(ROOT / "data/attack/raw/enterprise-attack-17.1.json.gz")))


def _env(model, adversary, eps, k):
    label = f"{adversary}|assumed|eps={eps:.2f}|k={k}"
    return DefenseRange(model, next(r for r in default_regimes(model) if r.label == label))


def test_parse_action_accepts_valid_and_rejects_everything_else():
    ids, deployed = {"M1031", "M1032"}, {"M1032"}
    assert parse_action('{"action":"add","mitigation":"m1031","reason":"x"}', ids, deployed) == \
        dict(action="add", mitigation="M1031", reason="x")
    assert parse_action('Sure! {"action": "stop"} done', ids, deployed)["action"] == "stop"
    assert parse_action('{"action":"remove","mitigation":"M1032"}', ids, deployed)["action"] == "remove"
    for bad in ["no json here", '{"action":"add","mitigation":"M9999"}',
                '{"action":"add","mitigation":"M1032"}',          # already deployed
                '{"action":"remove","mitigation":"M1031"}',       # not deployed
                '{"action":"deploy","mitigation":"M1031"}', "[1, 2]"]:
        assert parse_action(bad, ids, deployed)["action"] == "invalid", bad


@pytest.mark.parametrize("adversary,eps,k", [("typical", 0.05, 1), ("typical", 0.10, 1),
                                             ("adaptive", 0.10, 3)])
def test_scripted_greedy_through_the_text_interface_matches_the_committed_benchmark(
        model, adversary, eps, k):
    env = _env(model, adversary, eps, k)
    ids = [env.graph.mitigations[i] for i in greedy_order(env)]
    metrics, traj = run_episode(env, ScriptedAgent(ids), max_steps=40)
    gap = pd.read_csv(ROOT / "data/defense_range/optimality_gap.csv")
    ref = gap[(gap.adversary == adversary) & (gap.degradation_source == "assumed")
              & (gap.epsilon == eps) & (gap.k == k)].iloc[0]
    assert metrics["certified"] and metrics["cost_to_certify"] == ref.greedy_cost
    assert metrics["stop_reason"] == "certified" and metrics["invalid_actions"] == 0
    assert traj["turns"][-1]["cat_guaranteed"]


def test_uncertifiable_regime_is_never_certified_and_invalid_actions_are_no_ops(model):
    env = _env(model, "adaptive", 0.05, 1)

    class Noisy:
        def __init__(self):
            self.n = 0

        def reply(self, messages):
            self.n += 1
            if self.n % 2:
                return dict(text="I think we should add everything")
            return dict(text=json.dumps({"action": "add", "mitigation": env.graph.mitigations[self.n]}))

    metrics, traj = run_episode(env, Noisy(), max_steps=10)
    assert not metrics["certified"] and metrics["stop_reason"] == "step_cap"
    assert metrics["invalid_actions"] == 5 and metrics["final_cost"] == 5
    stop = run_episode(env, ScriptedAgent([]), max_steps=10)[0]
    assert stop["stop_reason"] == "agent_stop" and stop["steps"] == 1 and stop["final_cost"] == 0


class _FakeOllama(BaseHTTPRequestHandler):
    requests = []

    def log_message(self, *args):
        pass

    def _send(self, obj):
        data = json.dumps(obj).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == "/api/version":
            self._send({"version": "0.0-test"})
        else:
            self._send({"models": [{"name": "fake:1b", "model": "fake:1b", "digest": "abc123"}]})

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        type(self).requests.append((self.path, body))
        if self.path == "/api/show":
            self._send({"details": {"family": "fake", "parameter_size": "1B",
                                    "quantization_level": "Q4_0"}})
            return
        n = sum(m["role"] == "assistant" for m in body["messages"])
        reply = {"action": "add", "mitigation": "M1032"} if n == 0 else {"action": "stop"}
        self._send({"message": {"role": "assistant", "content": json.dumps(reply)},
                    "prompt_eval_count": 100 + n, "eval_count": 7})


def test_ollama_client_against_a_fake_server(model):
    server = HTTPServer(("127.0.0.1", 0), _FakeOllama)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    host = f"http://127.0.0.1:{server.server_port}"
    try:
        env = _env(model, "typical", 0.05, 1)
        metrics, traj = run_episode(env, OllamaAgent("fake:1b", host=host, seed=3), max_steps=5)
        meta = ollama_metadata("fake:1b", host=host)
    finally:
        server.shutdown()
    chats = [b for p, b in _FakeOllama.requests if p == "/api/chat"]
    assert len(chats) == 2 and chats[0]["format"] == "json" and chats[0]["stream"] is False
    assert chats[0]["options"] == {"temperature": 0.7, "seed": 3, "num_ctx": 16384}
    assert chats[0]["messages"][0]["role"] == "system"
    assert len(chats[1]["messages"]) == len(chats[0]["messages"]) + 2     # reply + next turn
    assert metrics["stop_reason"] == "agent_stop" and metrics["final_cost"] == 1
    assert metrics["prompt_tokens"] == 201 and metrics["completion_tokens"] == 14
    assert traj["turns"][0]["deployed"] == ["M1032"]
    assert meta == dict(ollama_version="0.0-test", model="fake:1b", digest="abc123",
                        family="fake", parameter_size="1B", quantization="Q4_0")


def test_claude_cli_agent_against_a_fake_executable(model, tmp_path):
    from grrc.range.llm_agent import ClaudeCLIAgent
    log = tmp_path / "calls.jsonl"
    fake = tmp_path / "claude"
    fake.write_text(f"""#!{__import__('sys').executable}
import json, os, sys
prompt = sys.stdin.read()
with open({str(log)!r}, "a") as fh:
    fh.write(json.dumps({{"argv": sys.argv[1:], "cwd": os.getcwd(), "prompt": prompt}}) + "\\n")
n = prompt.count("[You]")
reply = {{"action": "add", "mitigation": "M1032"}} if n == 0 else {{"action": "stop"}}
print(json.dumps({{"is_error": False, "result": json.dumps(reply), "total_cost_usd": 0.01,
                  "usage": {{"input_tokens": 5, "cache_read_input_tokens": 95, "output_tokens": 7}}}}))
""")
    fake.chmod(0o755)
    work = tmp_path / "empty"
    agent = ClaudeCLIAgent("claude-test", workdir=work, executable=str(fake))
    metrics, traj = run_episode(_env(model, "typical", 0.05, 1), agent, max_steps=5)
    calls = [json.loads(line) for line in log.read_text().splitlines()]
    assert len(calls) == 2 and all(c["cwd"] == str(work) for c in calls)
    assert list(work.iterdir()) == []                                   # nothing to read
    argv = calls[0]["argv"]
    assert argv[:3] == ["-p", "--tools", ""] and "--no-session-persistence" in argv
    assert argv[argv.index("--model") + 1] == "claude-test"
    assert argv[argv.index("--setting-sources") + 1] == ""
    assert "[You]" not in calls[0]["prompt"] and calls[1]["prompt"].count("[You]") == 1
    assert metrics["stop_reason"] == "agent_stop" and metrics["final_cost"] == 1
    assert metrics["cost_usd"] == pytest.approx(0.02) and metrics["prompt_tokens"] == 200

    broken = tmp_path / "broken"
    broken.write_text(f"#!{__import__('sys').executable}\nprint('not json')\n")
    broken.chmod(0o755)
    bad = ClaudeCLIAgent("x", workdir=work, executable=str(broken), retries=1)
    metrics, _ = run_episode(_env(model, "typical", 0.05, 1), bad, max_steps=2)
    assert metrics["invalid_actions"] == 2 and metrics["final_cost"] == 0
