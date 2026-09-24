"""A language-model defender for the cyber range, driven through the same API.

The range's score is a certificate, so an LLM defender is evaluated exactly like the
reference policies: it adds or removes ATT&CK mitigations turn by turn and is held to
the ``cat_guaranteed`` verdict (worst-case P(at least k clinical services in sustained
outage) <= epsilon over the whole uncertainty set). This module supplies

- the text observation (:func:`render_catalog`, :func:`render_turn`) and the system
  prompt with a JSON action schema;
- :func:`parse_action`, which turns a model reply into an action or an ``invalid``
  marker (invalid actions are a no-op and are counted);
- :func:`run_episode`, which drives any agent with a ``reply(messages)`` method and
  records the full trajectory;
- :class:`OllamaAgent`, a client for a local Ollama server (``POST /api/chat`` with
  JSON output), using only the standard library; and
- :class:`ScriptedAgent`, which replays a fixed policy order through the same text
  interface (used for tests and dry runs).

Nothing here reveals the reachability floor to the agent: whether a target can be met
at all is part of what the agent must judge.
"""
from __future__ import annotations

import json
import time
import urllib.request

SYSTEM_PROMPT = """You are an autonomous cyber-defense agent protecting a hospital network \
against ransomware. You choose which MITRE ATT&CK mitigations to deploy. Each turn you see \
the mitigations you have deployed and a certified score: an upper bound on the worst-case \
probability that at least k clinical services suffer a simultaneous sustained outage. The \
bound holds for every parameter value in an uncertainty set and every dependence between \
service failures, so it only falls when a deployment provably helps.

Goal: make the certified bound at most the target epsilon, deploying as few mitigations as \
possible. Deployments cost the same. If you judge that the target cannot be reached with the \
available mitigations, stop rather than deploy everything.

Reply with one JSON object and nothing else:
{"action": "add" | "remove" | "stop", "mitigation": "M####" (omit for stop), "reason": "<one short sentence>"}"""


def render_catalog(env) -> str:
    lines = ["Available mitigations (id | name | ATT&CK techniques covered | kill-chain stages):"]
    for m in env.mitigation_catalog():
        stages = ", ".join(m["stages"]) if m["stages"] else "none"
        lines.append(f"{m['id']} | {m['name']} | {m['techniques_covered']} | {stages}")
    return "\n".join(lines)


def _regime_text(env) -> str:
    r = env.regime
    who = ("an adaptive attacker who always uses the least-defended technique at each stage"
           if r.adversary == "adaptive" else
           "a typical attacker whose techniques follow their observed usage frequencies")
    return (f"Threat: {who}. Target: certified probability that at least {r.k} of "
            f"{len(env.model.services)} clinical services are down at once must be at most "
            f"{r.epsilon:.2f}.")


def render_turn(env, score, last_result, step, max_steps) -> str:
    ids = [env.graph.mitigations[i] for i in env.portfolio_indices()]
    status = "MET" if score["cat_guaranteed"] else "not met"
    parts = []
    if last_result:
        parts.append(f"Result of your last action: {last_result}")
    parts += [f"Turn {step + 1} of {max_steps}.",
              f"Deployed ({len(ids)}): {', '.join(ids) if ids else 'none'}",
              f"Certified worst-case bound: {score['cat_worst']:.4f} "
              f"(target {env.regime.epsilon:.2f}; {status})",
              "Your action (JSON):"]
    return "\n".join(parts)


def parse_action(text, catalog_ids, deployed_ids):
    """Parse a reply into ``{"action", "mitigation", "reason"}`` or an invalid marker."""
    try:
        start, end = text.index("{"), text.rindex("}") + 1
        obj = json.loads(text[start:end])
    except (ValueError, TypeError):
        return dict(action="invalid", why="no JSON object")
    if not isinstance(obj, dict):
        return dict(action="invalid", why="not an object")
    action = str(obj.get("action", "")).strip().lower()
    reason = str(obj.get("reason", ""))[:300]
    if action == "stop":
        return dict(action="stop", mitigation=None, reason=reason)
    if action not in ("add", "remove"):
        return dict(action="invalid", why=f"unknown action {action!r}")
    mid = str(obj.get("mitigation", "")).strip().upper()
    if mid not in catalog_ids:
        return dict(action="invalid", why=f"unknown mitigation {mid!r}")
    if action == "add" and mid in deployed_ids:
        return dict(action="invalid", why=f"{mid} already deployed")
    if action == "remove" and mid not in deployed_ids:
        return dict(action="invalid", why=f"{mid} not deployed")
    return dict(action=action, mitigation=mid, reason=reason)


def run_episode(env, agent, max_steps=30):
    """Drive ``agent`` from the empty portfolio until the target is certified, the agent
    stops, or ``max_steps`` turns elapse. Returns ``(metrics, trajectory)``."""
    env.reset()
    ids = [m["id"] for m in env.mitigation_catalog()]
    index = {m: i for i, m in enumerate(ids)}
    catalog_ids = set(ids)
    messages = [{"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": _regime_text(env) + "\n\n" + render_catalog(env)}]
    score = env.score()
    trajectory, invalid, last_result = [], 0, ""
    first_cert = 0 if score["cat_guaranteed"] else None
    stop_reason = "certified" if score["cat_guaranteed"] else "step_cap"
    steps = 0
    for step in range(max_steps if first_cert is None else 0):
        turn = render_turn(env, score, last_result, step, max_steps)
        if step == 0:
            messages[-1]["content"] += "\n\n" + turn
        else:
            messages.append({"role": "user", "content": turn})
        reply = agent.reply(messages)
        messages.append({"role": "assistant", "content": reply["text"]})
        deployed = {ids[i] for i in env.portfolio_indices()}
        act = parse_action(reply["text"], catalog_ids, deployed)
        steps = step + 1
        if act["action"] == "invalid":
            invalid += 1
            last_result = f"invalid ({act['why']}); nothing changed."
        elif act["action"] == "stop":
            stop_reason = "agent_stop"
        elif act["action"] == "add":
            env.add(index[act["mitigation"]])
            last_result = f"deployed {act['mitigation']}."
        else:
            env.remove(index[act["mitigation"]])
            last_result = f"removed {act['mitigation']}."
        score = env.score()
        trajectory.append(dict(step=steps, reply=reply["text"], action=act,
                               deployed=[ids[i] for i in env.portfolio_indices()],
                               cat_worst=score["cat_worst"],
                               cat_guaranteed=score["cat_guaranteed"],
                               prompt_tokens=reply.get("prompt_tokens"),
                               completion_tokens=reply.get("completion_tokens"),
                               seconds=reply.get("seconds")))
        if act["action"] == "stop":
            break
        if score["cat_guaranteed"]:
            first_cert = score["cost"]
            stop_reason = "certified"
            break
    metrics = dict(certified=first_cert is not None, cost_to_certify=first_cert,
                   steps=steps, invalid_actions=invalid, stop_reason=stop_reason,
                   final_cost=score["cost"], final_cat_worst=score["cat_worst"],
                   prompt_tokens=sum(t["prompt_tokens"] or 0 for t in trajectory),
                   completion_tokens=sum(t["completion_tokens"] or 0 for t in trajectory))
    return metrics, dict(messages=messages, turns=trajectory)


class ScriptedAgent:
    """Replays a fixed order of mitigation ids through the text interface."""

    def __init__(self, order_ids):
        self.order = list(order_ids)

    def reply(self, messages):
        n = sum(m["role"] == "assistant" for m in messages)
        if n >= len(self.order):
            return dict(text=json.dumps({"action": "stop", "reason": "order exhausted"}))
        return dict(text=json.dumps({"action": "add", "mitigation": self.order[n],
                                     "reason": "scripted"}))


class OllamaAgent:
    """Chat with a local Ollama model (``POST {host}/api/chat``), JSON output enforced."""

    def __init__(self, model, host="http://localhost:11434", temperature=0.7, seed=0,
                 num_ctx=16384, timeout=600):
        self.model, self.host = model, host.rstrip("/")
        # A full 30-turn episode is about 5k tokens; set the context explicitly so Ollama
        # never silently truncates the catalog (its default window can be smaller).
        self.options = {"temperature": float(temperature), "seed": int(seed),
                        "num_ctx": int(num_ctx)}
        self.timeout = timeout

    def reply(self, messages):
        body = json.dumps({"model": self.model, "messages": messages, "stream": False,
                           "format": "json", "options": self.options}).encode()
        req = urllib.request.Request(self.host + "/api/chat", data=body,
                                     headers={"Content-Type": "application/json"})
        t0 = time.monotonic()
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            out = json.loads(resp.read())
        return dict(text=out.get("message", {}).get("content", ""),
                    prompt_tokens=out.get("prompt_eval_count"),
                    completion_tokens=out.get("eval_count"),
                    seconds=round(time.monotonic() - t0, 3))


def ollama_metadata(model, host="http://localhost:11434", timeout=30):
    """Ollama server version and the model's digest, size and quantization."""
    host = host.rstrip("/")
    with urllib.request.urlopen(host + "/api/version", timeout=timeout) as resp:
        version = json.loads(resp.read()).get("version")
    req = urllib.request.Request(host + "/api/show", data=json.dumps({"model": model}).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        show = json.loads(resp.read())
    details = show.get("details", {})
    digest = None
    for tag in _list_tags(host, timeout):
        if tag.get("name") == model or tag.get("model") == model:
            digest = tag.get("digest")
    return dict(ollama_version=version, model=model, digest=digest,
                family=details.get("family"), parameter_size=details.get("parameter_size"),
                quantization=details.get("quantization_level"))


def _list_tags(host, timeout):
    try:
        with urllib.request.urlopen(host + "/api/tags", timeout=timeout) as resp:
            return json.loads(resp.read()).get("models", [])
    except OSError:
        return []
