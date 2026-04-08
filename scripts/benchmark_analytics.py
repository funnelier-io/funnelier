#!/usr/bin/env python3
"""
Analytics Endpoint Benchmark.

Fires sequential requests against the heaviest API endpoints and prints a
Markdown-formatted latency table with p50/p95/p99/mean/RPS.

Usage:
    python scripts/benchmark_analytics.py
    python scripts/benchmark_analytics.py --host http://api.funnelier.localhost --requests 200
    python scripts/benchmark_analytics.py --json results.json
"""

from __future__ import annotations

import argparse
import json
import sys
import time

import httpx

# Allow running from project root without PYTHONPATH tricks
sys.path.insert(0, ".")
from src.core.perf_utils import PerformanceStats, format_benchmark_table

# ── Configuration ────────────────────────────────────

ENDPOINTS = [
    ("GET", "/api/v1/analytics/funnel"),
    ("GET", "/api/v1/analytics/funnel/trend"),
    ("GET", "/api/v1/analytics/reports/daily"),
    ("GET", "/api/v1/analytics/predictive/churn"),
    ("GET", "/api/v1/analytics/predictive/lead-scores"),
    ("GET", "/api/v1/analytics/cohorts"),
    ("GET", "/api/v1/segments/distribution"),
    ("GET", "/api/v1/leads/contacts?page=1&per_page=20"),
    ("GET", "/api/v1/tenants/me/usage/detailed"),
    ("GET", "/health"),
    ("GET", "/metrics"),
]


# ── Runner ───────────────────────────────────────────


def authenticate(client: httpx.Client, host: str, username: str, password: str) -> str:
    """Login and return JWT access token."""
    resp = client.post(
        f"{host}/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def run_benchmark(
    host: str,
    num_requests: int,
    username: str,
    password: str,
) -> dict[str, PerformanceStats]:
    results: dict[str, PerformanceStats] = {}

    with httpx.Client(timeout=30.0) as client:
        # Authenticate
        token = authenticate(client, host, username, password)
        headers = {"Authorization": f"Bearer {token}"}

        for method, path in ENDPOINTS:
            stats = PerformanceStats()
            url = f"{host}{path}"
            label = path.split("?")[0]  # strip query for display

            print(f"  ⏱  {method} {label} ({num_requests} reqs) ... ", end="", flush=True)

            for _ in range(num_requests):
                start = time.perf_counter()
                try:
                    resp = client.request(method, url, headers=headers)
                    duration = time.perf_counter() - start
                    stats.latencies.append(duration)
                except httpx.HTTPError:
                    duration = time.perf_counter() - start
                    stats.latencies.append(duration)

            d = stats.as_dict()
            print(f"p50={d['p50_ms']}ms  p95={d['p95_ms']}ms  rps={d['rps']}")
            results[label] = stats

    return results


# ── CLI ──────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark Funnelier analytics endpoints")
    parser.add_argument("--host", default="http://localhost:8000", help="API base URL")
    parser.add_argument("--requests", type=int, default=50, help="Requests per endpoint")
    parser.add_argument("--username", default="admin", help="Login username")
    parser.add_argument("--password", default="admin1234", help="Login password")
    parser.add_argument("--json", dest="json_out", default="", help="Write JSON results to file")
    args = parser.parse_args()

    print(f"\n🚀 Funnelier Analytics Benchmark")
    print(f"   Host: {args.host}  |  Requests/endpoint: {args.requests}\n")

    results = run_benchmark(args.host, args.requests, args.username, args.password)

    # Markdown table
    print(f"\n{format_benchmark_table(results)}\n")

    # Optional JSON output
    if args.json_out:
        json_data = {ep: s.as_dict() for ep, s in results.items()}
        with open(args.json_out, "w") as f:
            json.dump(json_data, f, indent=2)
        print(f"📄 Results written to {args.json_out}")


if __name__ == "__main__":
    main()

