from itertools import product

import numpy as np
import pytest

from grrc.frontier_certificates import certify_frontier, two_objective_frontier
from grrc.multiobjective import pareto_mask


def exhaustive(lower, upper):
    masks = []
    variable = np.argwhere(lower != upper)
    for choices in product([False, True], repeat=len(variable)):
        matrix = lower.copy()
        for (row, col), use_upper in zip(variable, choices):
            if use_upper:
                matrix[row, col] = upper[row, col]
        # Deliberately direct scalar oracle, independent from corner logic.
        masks.append(np.array([not any(y != x and
            all(matrix[y,j] <= matrix[x,j] for j in range(matrix.shape[1])) and
            any(matrix[y,j] < matrix[x,j] for j in range(matrix.shape[1]))
            for y in range(len(matrix))) for x in range(len(matrix))]))
    return np.logical_and.reduce(masks), np.logical_or.reduce(masks)


@pytest.mark.parametrize('seed', range(5))
def test_certificate_matches_exhaustive_corners_including_ties(seed):
    rng = np.random.default_rng(seed)
    lower = rng.integers(0,4,size=(4,2)).astype(float)
    upper = lower + rng.integers(0,3,size=lower.shape)
    cert = certify_frontier(lower, upper)
    guaranteed, possible = exhaustive(lower, upper)
    assert np.array_equal(cert.guaranteed, guaranteed)
    assert np.array_equal(cert.possible, possible)


def test_degenerate_bounds_equal_the_ordinary_frontier_and_keep_ties():
    values = np.array([[0.,1.],[0.,1.],[1.,0.],[2.,2.]])
    cert = certify_frontier(values,values)
    assert cert.guaranteed.tolist() == [True,True,True,False]
    assert np.array_equal(cert.guaranteed,cert.possible)
    assert cert.necessary_dominator[-1] in (0,1,2)


def test_common_positive_affine_units_preserve_certificate():
    lower=np.array([[1.,3.],[2.,2.],[3.,1.]])
    upper=lower+np.array([.5,1.5])
    a=certify_frontier(lower,upper)
    b=certify_frontier(lower*np.array([3.,.2])+7,upper*np.array([3.,.2])+7)
    assert np.array_equal(a.guaranteed,b.guaranteed)
    assert np.array_equal(a.possible,b.possible)


@pytest.mark.parametrize('bad', ['reversed','nan','empty','shape'])
def test_invalid_bounds_rejected(bad):
    lower,upper=np.zeros((2,2)),np.ones((2,2))
    if bad=='reversed': lower[0,0]=2
    if bad=='nan': upper[0,0]=np.nan
    if bad=='empty': lower=upper=np.empty((0,2))
    if bad=='shape': upper=upper[:1]
    with pytest.raises(ValueError): certify_frontier(lower,upper)


def test_sorting_oracle_matches_pairwise_algorithm_on_ties_and_random_inputs():
    rng=np.random.default_rng(14)
    for values in [rng.integers(0,6,size=(30,2)),rng.random((50,2)),np.empty((0,2))]:
        assert np.array_equal(two_objective_frontier(values),pareto_mask(values))
