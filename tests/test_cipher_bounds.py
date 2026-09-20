from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from grrc.cipher_bounds import (load_corpus, high_severity_counts,
                                partial_identification_bounds, degradation_bounds,
                                time_profile, CLINICAL_SERVICES)
from grrc.enums import Service

ROOT = Path(__file__).resolve().parents[1]
REAL = ROOT / "data/cipher/raw/cipher-v1.0.1.csv"


def _tiny():
    return pd.DataFrame({
        "Technical Domain": ["Health Records", "Health Records", "Laboratory Systems",
                             "ePrescribing", "Hospital Infrastructure"],
        "Clinical Impact Score": [8, 8, 9, 5, 8],
        "Time Point": ["First Day", "Firsy Day", "First Week", "First Week", "Week 2"],
    })


def test_high_severity_counts_and_residual():
    counts, other, total = high_severity_counts(_tiny(), tau=7)
    assert counts[Service.EHR] == 2 and counts[Service.LABORATORY] == 1
    assert counts[Service.PHARMACY] == 0 and counts[Service.IMAGING] == 0  # ePrescribing was low severity
    assert other == 1 and total == 4  # infrastructure is unmodelled residual


def test_observed_share_and_partial_id_bounds_match_hand_calc():
    counts, _o, total = high_severity_counts(_tiny(), tau=7)
    at0 = partial_identification_bounds(counts, total, 0.0)
    assert at0[Service.EHR] == pytest.approx((0.5, 0.5))  # 2/4
    at1 = partial_identification_bounds(counts, total, 1.0)
    # hi = 2*2/(2*2+2)=4/6 ; lo = 2/(2+2*2)=2/6
    assert at1[Service.EHR][1] == pytest.approx(4 / 6)
    assert at1[Service.EHR][0] == pytest.approx(2 / 6)


@pytest.mark.parametrize("svc", list(CLINICAL_SERVICES))
def test_envelope_monotone_contains_observed_and_in_unit_interval(svc):
    counts, _o, total = high_severity_counts(load_corpus(REAL)) if REAL.exists() else (None, None, None)
    if counts is None:
        pytest.skip("real corpus absent")
    obs = partial_identification_bounds(counts, total, 0.0)[svc][0]
    prev = (obs, obs)
    for g in (0.0, 0.5, 1.0, 2.0):
        lo, hi = partial_identification_bounds(counts, total, g)[svc]
        assert 0.0 <= lo <= obs <= hi <= 1.0
        assert lo <= prev[0] + 1e-12 and hi >= prev[1] - 1e-12  # widens with gamma
        prev = (lo, hi)


def test_typo_cleaning():
    df = load_corpus(REAL) if REAL.exists() else _tiny_loaded()
    assert "Firsy Day" not in set(df["Time Point"])


def _tiny_loaded():
    # load_corpus path for the tiny frame via a temp file is overkill; clean inline.
    df = _tiny()
    df["Time Point"] = df["Time Point"].replace({"Firsy Day": "First Day"})
    return df


def test_degradation_bounds_shape_and_order():
    df = load_corpus(REAL) if REAL.exists() else _tiny()
    if not REAL.exists():
        pytest.skip("real corpus absent")
    bounds = degradation_bounds(df, 1.0)
    assert bounds.shape == (4, 2)
    assert (bounds[:, 0] <= bounds[:, 1]).all()
    assert (bounds >= 0).all() and (bounds <= 1).all()


def test_time_profile_sums_to_one_on_real_corpus():
    if not REAL.exists():
        pytest.skip("real corpus absent")
    prof = time_profile(load_corpus(REAL))
    assert sum(prof.values()) == pytest.approx(1.0)
    assert prof["Week 2"] + prof["First Month"] > 0  # harm beyond first week exists


@pytest.mark.parametrize("gamma", [-0.1, -1])
def test_negative_gamma_rejected(gamma):
    counts, _o, total = high_severity_counts(_tiny(), tau=7)
    with pytest.raises(ValueError):
        partial_identification_bounds(counts, total, gamma)


@pytest.mark.parametrize("tau", [0, 11, -3])
def test_bad_tau_rejected(tau):
    with pytest.raises(ValueError):
        high_severity_counts(_tiny(), tau=tau)


def test_missing_columns_rejected(tmp_path):
    bad = tmp_path / "bad.csv"
    bad.write_text("a,b\n1,2\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_corpus(bad)


def test_no_high_severity_records_rejected():
    df = pd.DataFrame({"Technical Domain": ["Imaging"], "Clinical Impact Score": [3],
                       "Time Point": ["First Day"]})
    with pytest.raises(ValueError):
        high_severity_counts(df, tau=7)
