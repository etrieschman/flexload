"""Realized dispatch: after the market clears, the imbalance ε_t realizes, and
reserve covers it or load is shed. The operator's ORDC is its model of ε_t;
this is the ε_t nature draws.

    ε_t = Σ_{j∈𝒪} (g_jt + r_jt)  +  net-load error  +  η_t

Units trip independently, each with its hourly probability 1/MTTF, and a unit
that trips loses its output and its reserve. The net-load error is the year's
real-time path, not drawn. η_t is the load's own within-hour variability,
normal with standard deviation κ d_t. Each hour has twelve five-minute
intervals; a trip lasts the hour, the error and η_t move by interval.
"""

from __future__ import annotations

import numpy as np

from .load import LoadType
from .system import Dispatch, Scenario, reserve


def shed(scenario: Scenario, dispatch: Dispatch, theta: LoadType, rng: np.random.Generator, n: int) -> np.ndarray:
    """(n, T) load shed in MWh, one row per draw of the window:
    shed_t = mean over the hour's intervals of max(0, ε_t − R_t), where ε_t
    counts the output and the reserve of the units that tripped.
    The draws depend on ``rng`` and the scenario's shape only, so one seed
    gives the same trips and the same η_t/κd_t under every construct and type."""
    M = scenario.units
    out = rng.random((n, scenario.T, M.shape[0])) < (M @ scenario.trip / M.sum(axis=1))  # (n, T, U): unit tripped
    eta = theta.kappa * dispatch.d[:, None] * rng.standard_normal((n, scenario.T, scenario.error.shape[1]))
    lost_output = np.einsum("ntu,ut->nt", out, M @ dispatch.g)
    lost_reserve = np.einsum("ntu,ut->nt", out, M @ dispatch.r)
    epsilon = lost_output[:, :, None] + scenario.error + eta  # (n, T, 12)
    R = reserve(dispatch.r, dispatch.sigma, dispatch.d, dispatch.d_firm).value
    return np.maximum(epsilon - (R - lost_reserve)[:, :, None], 0.0).mean(axis=2)


def worst(scenario: Scenario, dispatch: Dispatch, k: int) -> np.ndarray:
    """(T,) load shed in MW if the k thermal units with the most output and
    reserve trip in that hour, and nothing else is short: the named stress
    case. A requirement on the largest unit covers k = 1."""
    lost = scenario.units @ ((dispatch.g + dispatch.r) * ~scenario.renewable[:, None])  # (U, T): what a unit's trip takes away
    R = reserve(dispatch.r, dispatch.sigma, dispatch.d, dispatch.d_firm).value
    return np.maximum(np.sort(lost, axis=0)[-k:].sum(axis=0) - R, 0.0)


def outcomes(scenario: Scenario, dispatch: Dispatch, theta: LoadType, draws: int) -> dict:
    """What a dispatch holds and what it sheds once the imbalance realizes: the
    reserve pool C^res, the ORDC's cost C^ORDC, the lowest reserve held, load
    shed in each of ``draws`` draws (the window's MWh, ``shed_draws``; the
    tables sum them over windows draw by draw), and the worst hour's shed if
    the two largest thermal units trip. The seed is the window's start, so
    every construct and type sees the same draws."""
    mwh = shed(scenario, dispatch, theta, np.random.default_rng(scenario.start), draws).sum(axis=1)
    R = reserve(dispatch.r, dispatch.sigma, dispatch.d, dispatch.d_firm).value
    return {
        "reserve_cost": float(dispatch.C_res.sum()),
        "C_ordc": float(dispatch.C_ordc.sum()),
        "reserve_min": float(R.min()),
        "shed_draws": mwh.tolist(),
        "worst_2": float(worst(scenario, dispatch, 2).max()),
    }
