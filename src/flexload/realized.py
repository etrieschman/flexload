"""Realized dispatch: after the market clears, the imbalance ε_t realizes, and
reserve covers it or load is shed. The operator's ORDC is its model of ε_t;
this is the ε_t nature draws. Notes of 2026-11-06, "Realized ε_t".

    ε_t = Σ_{j∈𝒪} u_jt  +  net-load error  +  η_t

Units trip independently, each with its hourly probability 1/MTTF, and a unit
that trips loses its output and its reserve. The net-load error is the year's
real-time path, not drawn. η_t is the load's own within-hour variability,
normal with standard deviation κ d_t. Each hour has twelve five-minute
intervals; a trip lasts the hour, the error and η_t move by interval.
"""

from __future__ import annotations

import numpy as np

from .load import LoadType
from .system import Dispatch, Scenario


def reserve(dispatch: Dispatch) -> np.ndarray:
    """(T,) reserve held, R_t = Σ_j r_jt + σ_t + (d_t − dᶠⁱʳᵐ_t)."""
    return dispatch.r.sum(axis=0) + dispatch.sigma + (dispatch.d - dispatch.d_firm)


def shed(scenario: Scenario, dispatch: Dispatch, theta: LoadType, rng: np.random.Generator, n: int) -> np.ndarray:
    """(n, T) load shed in MWh, one row per draw of the window:
    shed_t = mean over the hour's intervals of max(0, ε_t − reserve left),
    where the reserve left is R_t less the reserve on the units that tripped.
    The draws depend on ``rng`` and the scenario's shape only, so one seed
    gives the same trips and the same η_t/κd_t under every construct and type."""
    M = scenario.units
    out = rng.random((n, scenario.T, M.shape[0])) < (M @ scenario.trip / M.sum(axis=1))  # (n, T, U): unit tripped
    eta = theta.kappa * dispatch.d[:, None] * rng.standard_normal((n, scenario.T, scenario.error.shape[1]))
    lost_output = np.einsum("ntu,ut->nt", out, M @ dispatch.u)
    lost_reserve = np.einsum("ntu,ut->nt", out, M @ dispatch.r)
    epsilon = lost_output[:, :, None] + scenario.error + eta  # (n, T, 12)
    return np.maximum(epsilon - (reserve(dispatch) - lost_reserve)[:, :, None], 0.0).mean(axis=2)


def worst(scenario: Scenario, dispatch: Dispatch, k: int) -> np.ndarray:
    """(T,) load shed in MW if the k thermal units with the most output and
    reserve trip in that hour, and nothing else is short: the named stress
    case. A requirement on the largest unit covers k = 1."""
    lost = scenario.units @ ((dispatch.u + dispatch.r) * ~scenario.renewable[:, None])  # (U, T): what a unit's trip takes away
    return np.maximum(np.sort(lost, axis=0)[-k:].sum(axis=0) - reserve(dispatch), 0.0)
