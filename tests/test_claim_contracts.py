import copy

import pandas as pd
import pytest

from grrc.claim_contracts import evaluate


def example():
    sources = {"s": (pd.DataFrame({"stage": ["test"] * 2, "profile": ["a", "b"],
                                  "gap": [3., 14.]}), {"gap": "percentage_points"})}
    claim = {"id": "c", "source": "s", "scope": {"stage": "test"}, "rows": 2,
             "group": "profile", "groups": ["a", "b"], "column": "gap",
             "unit": "percentage_points", "reduce": "each", "quantifier": "all",
             "relation": "le", "target": 4}
    return claim, sources


def test_universal_has_group_witness_and_cannot_pass_by_pooling():
    claim, sources = example()
    result = evaluate(claim, sources)
    assert result["status"] == "fail"
    assert [x["group"] for x in result["witnesses"] if not x["satisfies"]] == ["b"]
    claim["quantifier"] = "any"
    assert evaluate(claim, sources)["status"] == "pass"


@pytest.mark.parametrize("replace", [
    {"scope": {"stage": "missing"}}, {"rows": 3}, {"groups": ["a"]},
    {"unit": "probability"}, {"reduce": "unsupported"}, {"relation": "eval"},
    {"quantifier": "mostly"}, {"target": float("nan")}, {"tolerance": -1},
])
def test_invalid_contract_fails_closed(replace):
    claim, sources = example()
    claim.update(replace)
    assert evaluate(claim, sources)["status"] == "invalid"


def test_boundary_and_nonfinite_source():
    claim, sources = example()
    claim.update(reduce="max", target=14, relation="eq")
    assert evaluate(claim, sources)["status"] == "pass"
    sources["s"][0].loc[1, "gap"] = float("nan")
    assert evaluate(claim, sources)["status"] == "invalid"


def test_duplicate_groups_are_not_silently_averaged():
    claim, sources = example()
    sources["s"][0].loc[1, "profile"] = "a"
    assert evaluate(claim, sources)["status"] == "invalid"
