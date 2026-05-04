"""Token estimation utilities."""

from __future__ import annotations

from math import ceil


class TokenEstimator:
    """Approximate token estimator using 1 token ~= 4 characters."""

    @staticmethod
    def estimate(text: str) -> int:
        return ceil(len(text) / 4) if text else 0
