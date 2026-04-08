"""
Performance measurement utilities.

Provides ``PerformanceStats`` for computing latency percentiles
and ``format_benchmark_table`` for rendering results as Markdown.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field


@dataclass
class PerformanceStats:
    """Compute p50/p95/p99/mean/min/max from a list of latencies (seconds)."""

    latencies: list[float] = field(default_factory=list)

    # ── Computed properties ───────────────────────────────

    @property
    def count(self) -> int:
        return len(self.latencies)

    @property
    def mean(self) -> float:
        return statistics.mean(self.latencies) if self.latencies else 0.0

    @property
    def min(self) -> float:
        return builtins_min(self.latencies) if self.latencies else 0.0

    @property
    def max(self) -> float:
        return builtins_max(self.latencies) if self.latencies else 0.0

    @property
    def p50(self) -> float:
        return self._percentile(50)

    @property
    def p95(self) -> float:
        return self._percentile(95)

    @property
    def p99(self) -> float:
        return self._percentile(99)

    @property
    def rps(self) -> float:
        """Requests per second (total_time = sum of latencies in serial mode)."""
        total = sum(self.latencies)
        return self.count / total if total > 0 else 0.0

    # ── Helpers ───────────────────────────────────────────

    def _percentile(self, pct: int) -> float:
        if not self.latencies:
            return 0.0
        sorted_lats = sorted(self.latencies)
        k = (pct / 100) * (len(sorted_lats) - 1)
        f = int(k)
        c = f + 1
        if c >= len(sorted_lats):
            return sorted_lats[-1]
        return sorted_lats[f] + (k - f) * (sorted_lats[c] - sorted_lats[f])

    def as_dict(self) -> dict:
        return {
            "count": self.count,
            "mean_ms": round(self.mean * 1000, 2),
            "min_ms": round(self.min * 1000, 2),
            "max_ms": round(self.max * 1000, 2),
            "p50_ms": round(self.p50 * 1000, 2),
            "p95_ms": round(self.p95 * 1000, 2),
            "p99_ms": round(self.p99 * 1000, 2),
            "rps": round(self.rps, 1),
        }


# builtins aliased to avoid shadowing by dataclass field names
import builtins as _builtins

builtins_min = _builtins.min
builtins_max = _builtins.max


def format_benchmark_table(results: dict[str, PerformanceStats]) -> str:
    """
    Render a dict of ``{endpoint: PerformanceStats}`` as a Markdown table.

    Example output::

        | Endpoint | Reqs | Mean (ms) | p50 (ms) | p95 (ms) | p99 (ms) | RPS |
        |---|---|---|---|---|---|---|
        | /api/v1/analytics/funnel | 100 | 42.5 | 38.0 | 95.2 | 120.1 | 23.5 |
    """
    header = "| Endpoint | Reqs | Mean (ms) | p50 (ms) | p95 (ms) | p99 (ms) | RPS |"
    sep = "|---|---|---|---|---|---|---|"
    rows = [header, sep]
    for endpoint, stats in results.items():
        d = stats.as_dict()
        rows.append(
            f"| {endpoint} | {d['count']} | {d['mean_ms']} | {d['p50_ms']} "
            f"| {d['p95_ms']} | {d['p99_ms']} | {d['rps']} |"
        )
    return "\n".join(rows)

