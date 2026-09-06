"""Small, explicit table assertions; not a natural-language fact checker.

Units are declared by the source schema. An assertion fixes its population,
row count, grouping, statistic, quantifier, and relation. Unsupported or
incomplete assertions fail closed. Human review must still establish that a
registered assertion expresses the intended manuscript sentence.
"""
from __future__ import annotations

import operator
from typing import Any

import numpy as np
import pandas as pd


def evaluate(assertion: dict, sources: dict[str, tuple[pd.DataFrame, dict]]) -> dict[str, Any]:
    result = {"id": assertion.get("id", "missing"), "status": "invalid", "witnesses": []}
    try:
        frame, schema = sources[assertion["source"]]
        frame = frame.copy()
        for column, value in assertion["scope"].items():
            frame = frame.loc[frame[column] == value]
        if frame.empty or len(frame) != assertion["rows"]:
            raise ValueError("population empty or row count differs")
        group = assertion["group"]
        if frame[group].duplicated().any() or frame[group].isna().any():
            raise ValueError("groups missing or duplicated")
        if set(frame[group]) != set(assertion["groups"]):
            raise ValueError("group population differs")
        column = assertion["column"]
        if schema[column] != assertion["unit"]:
            raise ValueError("unit differs from source schema")
        values = pd.to_numeric(frame[column], errors="raise").to_numpy(float)
        if not np.isfinite(values).all():
            raise ValueError("non-finite statistic")
        reducer = assertion["reduce"]
        if reducer == "each":
            labels = frame[group].tolist()
        elif reducer in ("sum", "min", "max", "mean"):
            values = np.array([getattr(np, reducer)(values)])
            labels = [reducer]
        else:
            raise ValueError("unsupported reducer")
        target = float(assertion["target"])
        tolerance = float(assertion.get("tolerance", 0))
        if not np.isfinite(target) or not np.isfinite(tolerance) or tolerance < 0:
            raise ValueError("invalid target or tolerance")
        relation = assertion["relation"]
        if relation == "eq":
            checks = np.abs(values - target) <= tolerance
        else:
            if tolerance:
                raise ValueError("tolerance only supported for equality")
            checks = {"lt": operator.lt, "le": operator.le,
                      "gt": operator.gt, "ge": operator.ge}[relation](values, target)
        quantifier = assertion["quantifier"]
        if quantifier not in ("all", "any"):
            raise ValueError("unsupported quantifier")
        passed = bool(checks.all() if quantifier == "all" else checks.any())
        result.update(status="pass" if passed else "fail", witnesses=[
            {"group": str(label), "value": float(value), "satisfies": bool(check)}
            for label, value, check in zip(labels, values, checks, strict=True)])
    except (KeyError, TypeError, ValueError) as error:
        result["reason"] = str(error)
    return result
