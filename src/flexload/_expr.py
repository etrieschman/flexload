"""Arithmetic that works on numpy arrays and cvxpy expressions alike.

Every formula in the memo is written once and evaluated twice: on numbers at
settlement and on cvxpy variables inside an objective. These helpers are the
only place the two cases are told apart.
"""

from __future__ import annotations

import cvxpy as cp
import numpy as np


def is_expr(*xs) -> bool:
    return any(isinstance(x, cp.Expression) for x in xs)


def sum_(x):
    return cp.sum(x) if is_expr(x) else float(np.sum(x))


def mul(a, x):
    """Elementwise product."""
    return cp.multiply(a, x) if is_expr(a, x) else a * x


def dot(a, x):
    """Inner product of two vectors."""
    return a @ x if is_expr(a, x) else float(np.dot(a, x))


def sum_squares(x):
    return cp.sum_squares(x) if is_expr(x) else float(np.sum(np.square(x)))


def where(mask, a, b):
    """``a`` where ``mask`` else ``b``; mask is a boolean numpy array."""
    m = np.asarray(mask, dtype=float)
    if is_expr(a, b):
        return mul(m, a) + mul(1.0 - m, b)
    return np.where(mask, a, b)
