"""A language-model defender for CAGE Challenge 2.

Each step the model sees the step number, CybORG's Blue table (per host: subnet,
activity seen this step, estimated compromise) and its own last few actions with their
outcomes, and replies with one JSON action. Calls are stateless (a short memory window
replaces the full transcript), which keeps the cost per step roughly constant. Any model
behind the ``reply(messages)`` interface of :mod:`grrc.range.llm_agent` can be used:
Claude through the Claude Code CLI, or a local open-weight model through Ollama.
Invalid replies fall back to ``Sleep`` and are counted.
"""
from __future__ import annotations

import json

from CybORG.Shared.Actions import Analyse, Monitor, Remove, Restore, Sleep
from CybORG.Shared.Actions.ConcreteActions.DecoyApache import DecoyApache
from CybORG.Shared.Actions.ConcreteActions.DecoyFemitter import DecoyFemitter
from CybORG.Shared.Actions.ConcreteActions.DecoyHarakaSMPT import DecoyHarakaSMPT
from CybORG.Shared.Actions.ConcreteActions.DecoySmss import DecoySmss
from CybORG.Shared.Actions.ConcreteActions.DecoySSHD import DecoySSHD
from CybORG.Shared.Actions.ConcreteActions.DecoySvchost import DecoySvchost
from CybORG.Shared.Actions.ConcreteActions.DecoyTomcat import DecoyTomcat
from CybORG.Shared.Actions.ConcreteActions.DecoyVsftpd import DecoyVsftpd

HOSTS = ["Defender", "Enterprise0", "Enterprise1", "Enterprise2", "Op_Host0", "Op_Host1",
         "Op_Host2", "Op_Server0", "User0", "User1", "User2", "User3", "User4"]
DECOYS = [DecoyApache, DecoyFemitter, DecoyHarakaSMPT, DecoySmss, DecoySSHD, DecoySvchost,
          DecoyTomcat, DecoyVsftpd]
MEMORY = 5

SYSTEM_PROMPT = """You are an autonomous cyber-defense agent protecting a simulated network \
(CAGE Challenge 2) from an attacker during a fixed number of steps.

Network: user subnet User0-User4 (the attacker starts on User0, which you cannot defend); \
enterprise subnet Enterprise0-Enterprise2 and Defender; operational subnet Op_Host0-Op_Host2 \
and Op_Server0. The attacker moves from the user subnet through the enterprise subnet to \
Op_Server0, whose disruption is the mission-critical loss.

Scoring each step (higher is better, 0 is best): -10 if the attacker disrupts Op_Server0; \
-1 per enterprise server or Op_Server0 where the attacker has privileged access; -0.1 per \
other host with privileged access; -1 for each Restore you perform.

Each step you see a table: for every host, Activity observed this step (None, Scan, Exploit) \
and Compromised as estimated from your observations (No, Unknown, User, Privileged).

Actions (exactly one per step):
- Sleep: do nothing.
- Monitor: collect events (already done automatically every step).
- Analyse <host>: check a host for malware; improves the compromise estimate.
- Remove <host>: kill the attacker's user-level access on a host (fails against privileged access).
- Restore <host>: reimage a host from backup, removing all attacker access (costs -1).
- Decoy <host>: deploy a decoy service on a host that traps and slows the attacker's exploits.

Reply with one JSON object and nothing else:
{"action": "Sleep|Monitor|Analyse|Remove|Restore|Decoy", "host": "<hostname or omit>", "reason": "<short>"}"""


def parse(text):
    """``(action, host)`` or ``None`` if the reply is not a valid action."""
    try:
        obj = json.loads(text[text.index("{"): text.rindex("}") + 1])
    except (ValueError, TypeError):
        return None
    if not isinstance(obj, dict):
        return None
    action = str(obj.get("action", "")).strip().capitalize()
    host = obj.get("host")
    if action in ("Sleep", "Monitor"):
        return action, None
    if action in ("Analyse", "Analyze", "Remove", "Restore", "Decoy"):
        host = next((h for h in HOSTS if str(host).strip().lower() == h.lower()), None)
        if host is None or host == "User0" and action != "Analyse":
            return None
        return ("Analyse" if action == "Analyze" else action), host
    return None


class LLMDefender:
    interface = "table"

    def __init__(self, agent, name):
        self.agent, self.name = agent, name
        self.end_episode()

    def end_episode(self):
        self.history, self.decoys = [], {h: 0 for h in HOSTS}
        self.invalid, self.calls, self.cost, self.prompt_tokens, self.completion_tokens = 0, 0, 0.0, 0, 0
        self.log = []

    def episode_info(self):
        return dict(invalid=self.invalid, calls=self.calls, cost_usd=round(self.cost, 6),
                    prompt_tokens=self.prompt_tokens, completion_tokens=self.completion_tokens)

    def _build(self, action, host):
        kw = dict(agent="Blue", session=0)
        if action == "Sleep":
            return Sleep()
        if action == "Monitor":
            return Monitor(**kw)
        if action == "Decoy":
            cls = DECOYS[self.decoys[host] % len(DECOYS)]
            self.decoys[host] += 1
            return cls(hostname=host, **kw)
        return {"Analyse": Analyse, "Remove": Remove, "Restore": Restore}[action](hostname=host, **kw)

    def get_action(self, table, action_space, cyborg=None, step=0, steps=30):
        if self.history and cyborg is not None:
            ok = str(cyborg.get_observation("Blue").get("success"))
            self.history[-1] += f" -> {'succeeded' if ok == 'TRUE' else 'failed' if ok == 'FALSE' else 'unknown'}"
        memory = "\n".join(self.history[-MEMORY:]) or "none yet"
        prompt = (f"Step {step + 1} of {steps}.\n{table}\n\nYour recent actions:\n{memory}\n\n"
                  "Your action (JSON):")
        reply = self.agent.reply([{"role": "system", "content": SYSTEM_PROMPT},
                                  {"role": "user", "content": prompt}])
        self.calls += 1
        self.cost += reply.get("cost_usd") or 0.0
        self.prompt_tokens += reply.get("prompt_tokens") or 0
        self.completion_tokens += reply.get("completion_tokens") or 0
        parsed = parse(reply.get("text", ""))
        if parsed is None:
            self.invalid += 1
            parsed = ("Sleep", None)
        self.history.append(f"step {step + 1}: {parsed[0]}{' ' + parsed[1] if parsed[1] else ''}")
        self.log.append(dict(step=step + 1, reply=reply.get("text", ""), action=parsed[0],
                             host=parsed[1]))
        return self._build(*parsed)
