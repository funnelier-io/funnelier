"""
Locust load-test suite for Funnelier API.

Run headless:
    locust -f tests/load/locustfile.py --headless -u 50 -r 5 -t 60s \
           --host http://localhost:8000

Run with Web UI:
    locust -f tests/load/locustfile.py --host http://localhost:8000
    # → open http://localhost:8089

Environment variables (optional):
    LOCUST_USERNAME   — login username  (default: admin)
    LOCUST_PASSWORD   — login password  (default: admin1234)
"""

from __future__ import annotations

import os
import random

from locust import HttpUser, between, tag, task


# ── Helpers ──────────────────────────────────────────

_USERNAME = os.getenv("LOCUST_USERNAME", "admin")
_PASSWORD = os.getenv("LOCUST_PASSWORD", "admin1234")

_STAGE_NAMES = [
    "lead_acquired",
    "sms_sent",
    "sms_delivered",
    "call_attempted",
    "call_answered",
    "invoice_issued",
    "payment_received",
]

_SEGMENT_NAMES = [
    "champions",
    "loyal",
    "potential_loyalist",
    "new_customers",
    "at_risk",
    "hibernating",
    "lost",
]

_SEARCH_TERMS = [
    "محمد",
    "علی",
    "سیمان",
    "شیراز",
    "تهران",
    "test",
    "09",
]


# ── User Behaviour ───────────────────────────────────


class FunnelierUser(HttpUser):
    """
    Simulated multi-tenant user hitting the most common API paths.

    Weight distribution mirrors production usage patterns:
    - Reads (analytics, leads list) are heavy  (70 %)
    - Writes (contact create, import) are light (10 %)
    - Health / metrics are background noise     (20 %)
    """

    wait_time = between(1, 3)
    host = os.getenv("LOCUST_TARGET_HOST", "http://localhost:8000")

    # Token cached after on_start
    _token: str = ""

    # ── Lifecycle ────────────────────────────────────

    def on_start(self) -> None:
        """Authenticate once and cache the JWT token."""
        resp = self.client.post(
            "/api/v1/auth/login",
            json={"username": _USERNAME, "password": _PASSWORD},
            name="/api/v1/auth/login",
        )
        if resp.status_code == 200:
            self._token = resp.json().get("access_token", "")
        else:
            # Still allow the user to run (some endpoints are public)
            self._token = ""

    @property
    def _auth(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token}"} if self._token else {}

    # ── Health / Infra (weight 2) ────────────────────

    @task(2)
    @tag("health")
    def health(self) -> None:
        self.client.get("/health", name="/health")

    @task(1)
    @tag("health")
    def health_ready(self) -> None:
        self.client.get("/health/ready", name="/health/ready")

    @task(1)
    @tag("metrics")
    def metrics(self) -> None:
        self.client.get("/metrics", name="/metrics")

    # ── Analytics (weight 6) ─────────────────────────

    @task(6)
    @tag("analytics")
    def funnel(self) -> None:
        self.client.get(
            "/api/v1/analytics/funnel",
            headers=self._auth,
            name="/api/v1/analytics/funnel",
        )

    @task(3)
    @tag("analytics")
    def funnel_trend(self) -> None:
        self.client.get(
            "/api/v1/analytics/funnel/trend",
            headers=self._auth,
            name="/api/v1/analytics/funnel/trend",
        )

    @task(3)
    @tag("analytics")
    def daily_report(self) -> None:
        self.client.get(
            "/api/v1/analytics/reports/daily",
            headers=self._auth,
            name="/api/v1/analytics/reports/daily",
        )

    @task(2)
    @tag("analytics", "predictive")
    def churn_prediction(self) -> None:
        self.client.get(
            "/api/v1/analytics/predictive/churn",
            headers=self._auth,
            name="/api/v1/analytics/predictive/churn",
        )

    @task(2)
    @tag("analytics", "predictive")
    def lead_scores(self) -> None:
        self.client.get(
            "/api/v1/analytics/predictive/lead-scores",
            headers=self._auth,
            name="/api/v1/analytics/predictive/lead-scores",
        )

    @task(1)
    @tag("analytics")
    def cohorts(self) -> None:
        self.client.get(
            "/api/v1/analytics/cohorts",
            headers=self._auth,
            name="/api/v1/analytics/cohorts",
        )

    # ── Leads (weight 5) ────────────────────────────

    @task(5)
    @tag("leads")
    def contacts_list(self) -> None:
        page = random.randint(1, 5)
        self.client.get(
            f"/api/v1/leads/contacts?page={page}&per_page=20",
            headers=self._auth,
            name="/api/v1/leads/contacts",
        )

    @task(2)
    @tag("leads")
    def contacts_by_stage(self) -> None:
        stage = random.choice(_STAGE_NAMES)
        self.client.get(
            f"/api/v1/leads/contacts?stage={stage}&per_page=20",
            headers=self._auth,
            name="/api/v1/leads/contacts?stage=*",
        )

    @task(2)
    @tag("leads")
    def contacts_by_segment(self) -> None:
        seg = random.choice(_SEGMENT_NAMES)
        self.client.get(
            f"/api/v1/leads/contacts?segment={seg}&per_page=20",
            headers=self._auth,
            name="/api/v1/leads/contacts?segment=*",
        )

    # ── Segments (weight 3) ──────────────────────────

    @task(3)
    @tag("segments")
    def segment_distribution(self) -> None:
        self.client.get(
            "/api/v1/segments/distribution",
            headers=self._auth,
            name="/api/v1/segments/distribution",
        )

    @task(1)
    @tag("segments")
    def segment_recommendations(self) -> None:
        seg = random.choice(_SEGMENT_NAMES)
        self.client.get(
            f"/api/v1/segments/recommendations/{seg}",
            headers=self._auth,
            name="/api/v1/segments/recommendations/{seg}",
        )

    # ── Search (weight 2) ────────────────────────────

    @task(2)
    @tag("search")
    def search(self) -> None:
        q = random.choice(_SEARCH_TERMS)
        self.client.get(
            f"/api/v1/search?q={q}",
            headers=self._auth,
            name="/api/v1/search?q=*",
        )

    # ── Billing / Usage (weight 1) ───────────────────

    @task(1)
    @tag("billing")
    def usage_detailed(self) -> None:
        self.client.get(
            "/api/v1/tenants/me/usage/detailed",
            headers=self._auth,
            name="/api/v1/tenants/me/usage/detailed",
        )

    @task(1)
    @tag("billing")
    def billing_plans(self) -> None:
        self.client.get(
            "/api/v1/tenants/me/billing/plans",
            headers=self._auth,
            name="/api/v1/tenants/me/billing/plans",
        )

    # ── Communications (weight 2) ────────────────────

    @task(2)
    @tag("communications")
    def call_logs(self) -> None:
        self.client.get(
            "/api/v1/communications/calls?page=1&per_page=20",
            headers=self._auth,
            name="/api/v1/communications/calls",
        )

    @task(1)
    @tag("communications")
    def sms_templates(self) -> None:
        self.client.get(
            "/api/v1/communications/templates",
            headers=self._auth,
            name="/api/v1/communications/templates",
        )

