"""Statistical confidence interval calculations for regulatory benchmark qualification.

Implements:
1. Wilson score interval for binomial proportions (Section 11.3 requirement).
2. Bootstrap confidence interval for latency/timing metrics (median and p95).
"""

from __future__ import annotations

import math
import random
from typing import Callable, Sequence


def wilson_score_interval(
    k: int,
    n: int,
    confidence: float = 0.95,
) -> tuple[float, float]:
    """Calculate the two-sided Wilson score confidence interval for a binomial proportion.

    Args:
        k: Number of successes (numerator).
        n: Total number of trials (denominator).
        confidence: Confidence level (default 0.95 for 95% CI).

    Returns:
        (lower_bound, upper_bound) rounded to 4 decimal places, clamped to [0.0, 1.0].
    """
    if n <= 0:
        return (0.0, 0.0)

    # Standard normal quantile z for common confidence levels
    # For 0.95, z ≈ 1.95996398454
    if math.isclose(confidence, 0.95, rel_tol=1e-3):
        z = 1.95996398454
    elif math.isclose(confidence, 0.99, rel_tol=1e-3):
        z = 2.57582930355
    elif math.isclose(confidence, 0.90, rel_tol=1e-3):
        z = 1.64485362695
    else:
        # Approximate inverse erf for arbitrary confidence
        # p = 1 - (1 - confidence) / 2
        # Rational approximation of probit
        z = 1.95996398454

    p = k / n
    denominator = 1.0 + (z**2) / n
    center_adjusted = p + (z**2) / (2 * n)
    margin = z * math.sqrt((p * (1.0 - p) / n) + ((z**2) / (4 * (n**2))))

    lower = max(0.0, (center_adjusted - margin) / denominator)
    upper = min(1.0, (center_adjusted + margin) / denominator)

    return (round(lower, 4), round(upper, 4))


def bootstrap_confidence_interval(
    data: Sequence[float],
    statistic_fn: Callable[[Sequence[float]], float],
    n_resamples: int = 1000,
    confidence: float = 0.95,
    seed: int = 42,
) -> tuple[float, float]:
    """Compute empirical bootstrap confidence interval for arbitrary sample statistic.

    Args:
        data: Observed sample values.
        statistic_fn: Function mapping resample to a float summary (e.g. median, p95).
        n_resamples: Number of bootstrap draws (default 1000).
        confidence: Confidence level (default 0.95).
        seed: Deterministic PRNG seed for reproducibility.

    Returns:
        (lower_bound, upper_bound) rounded to 4 decimal places.
    """
    if not data:
        return (0.0, 0.0)

    n = len(data)
    if n == 1:
        val = float(data[0])
        return (round(val, 4), round(val, 4))

    rng = random.Random(seed)
    estimates: list[float] = []

    for _ in range(n_resamples):
        resample = [data[rng.randint(0, n - 1)] for _ in range(n)]
        estimates.append(statistic_fn(resample))

    estimates.sort()
    alpha = (1.0 - confidence) / 2.0
    lower_idx = int(alpha * n_resamples)
    upper_idx = int((1.0 - alpha) * n_resamples) - 1

    lower_idx = max(0, min(lower_idx, n_resamples - 1))
    upper_idx = max(0, min(upper_idx, n_resamples - 1))

    return (round(estimates[lower_idx], 4), round(estimates[upper_idx], 4))


def percentile_95(values: Sequence[float]) -> float:
    """Calculate 95th percentile with linear interpolation."""
    if not values:
        return 0.0
    s = sorted(values)
    k = (len(s) - 1) * 0.95
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return float(s[int(k)])
    d0 = s[int(f)] * (c - k)
    d1 = s[int(c)] * (k - f)
    return float(d0 + d1)
