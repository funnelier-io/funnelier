"""
Integration tests for Funnelier API using httpx TestClient.
Tests the full request/response cycle through FastAPI with real database.
"""

import pytest
from uuid import uuid4


class TestHealthEndpoints:
    """Test health and info endpoints."""

    @pytest.mark.asyncio(loop_scope="session")
    async def test_health_check(self, client):
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert "version" in data

    @pytest.mark.asyncio(loop_scope="session")
    async def test_api_info(self, client):
        resp = await client.get("/api/v1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Funnelier"
        assert "endpoints" in data


class TestLeadsAPI:
    """Integration tests for Leads module."""

    @pytest.mark.asyncio(loop_scope="session")
    async def test_create_and_get_contact(self, client):
        # Create
        phone = f"0935{uuid4().hex[:7]}"
        resp = await client.post("/api/v1/leads/contacts", json={
            "phone_number": phone,
            "name": "تست یکپارچه",
            "tags": ["integration-test"],
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "تست یکپارچه"
        contact_id = data["id"]

        # Get by ID
        resp = await client.get(f"/api/v1/leads/contacts/{contact_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == contact_id

    @pytest.mark.asyncio(loop_scope="session")
    async def test_duplicate_phone_rejected(self, client):
        phone = f"0935{uuid4().hex[:7]}"
        await client.post("/api/v1/leads/contacts", json={
            "phone_number": phone, "name": "اولی"
        })
        resp = await client.post("/api/v1/leads/contacts", json={
            "phone_number": phone, "name": "دومی"
        })
        assert resp.status_code == 409

    @pytest.mark.asyncio(loop_scope="session")
    async def test_update_contact_stage(self, client):
        phone = f"0935{uuid4().hex[:7]}"
        resp = await client.post("/api/v1/leads/contacts", json={
            "phone_number": phone, "name": "Stage Test"
        })
        cid = resp.json()["id"]

        resp = await client.patch(f"/api/v1/leads/contacts/{cid}/stage", json={
            "stage": "sms_sent"
        })
        assert resp.status_code == 200
        assert resp.json()["current_stage"] == "sms_sent"

    @pytest.mark.asyncio(loop_scope="session")
    async def test_block_unblock_contact(self, client):
        phone = f"0935{uuid4().hex[:7]}"
        resp = await client.post("/api/v1/leads/contacts", json={
            "phone_number": phone, "name": "Block Test"
        })
        cid = resp.json()["id"]

        # Block
        resp = await client.post(f"/api/v1/leads/contacts/{cid}/block?reason=spam")
        assert resp.status_code == 200
        assert resp.json()["is_blocked"] is True

        # Unblock
        resp = await client.post(f"/api/v1/leads/contacts/{cid}/unblock")
        assert resp.status_code == 200
        assert resp.json()["is_blocked"] is False

    @pytest.mark.asyncio(loop_scope="session")
    async def test_bulk_import(self, client):
        contacts = [
            {"phone_number": f"0911{uuid4().hex[:7]}", "name": f"Bulk {i}"}
            for i in range(5)
        ]
        resp = await client.post("/api/v1/leads/contacts/bulk-import", json={
            "contacts": contacts
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["success_count"] == 5
        assert data["error_count"] == 0

    @pytest.mark.asyncio(loop_scope="session")
    async def test_create_category(self, client):
        resp = await client.post("/api/v1/leads/categories", json={
            "name": f"تست {uuid4().hex[:6]}",
            "description": "دسته‌بندی تست",
            "color": "#3B82F6",
        })
        assert resp.status_code == 201
        assert resp.json()["color"] == "#3B82F6"

    @pytest.mark.asyncio(loop_scope="session")
    async def test_stats_summary(self, client):
        resp = await client.get("/api/v1/leads/stats/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_contacts" in data
        assert "active_contacts" in data


class TestCommunicationsAPI:
    """Integration tests for Communications module."""

    @pytest.mark.asyncio(loop_scope="session")
    async def test_create_and_list_templates(self, client):
        resp = await client.post("/api/v1/communications/templates", json={
            "name": f"قالب تست {uuid4().hex[:6]}",
            "content": "سلام {name}، خوش آمدید!",
            "category": "welcome",
            "target_segments": ["new_customers"],
        })
        assert resp.status_code == 201
        tmpl = resp.json()
        assert tmpl["character_count"] > 0

        resp = await client.get("/api/v1/communications/templates")
        assert resp.status_code == 200
        assert resp.json()["total_count"] >= 1

    @pytest.mark.asyncio(loop_scope="session")
    async def test_send_sms_persists(self, client):
        resp = await client.post("/api/v1/communications/sms/send", json={
            "phone_number": "09121234567",
            "content": "تست ارسال پیامک",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["phone_number"] == "09121234567"
        assert data["status"] == "pending"

    @pytest.mark.asyncio(loop_scope="session")
    async def test_sms_logs_list(self, client):
        resp = await client.get("/api/v1/communications/sms/logs")
        assert resp.status_code == 200
        data = resp.json()
        assert "logs" in data
        assert "total_count" in data

    @pytest.mark.asyncio(loop_scope="session")
    async def test_call_stats(self, client):
        resp = await client.get("/api/v1/communications/calls/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_calls" in data
        assert "answer_rate" in data


class TestSalesAPI:
    """Integration tests for Sales module."""

    @pytest.mark.asyncio(loop_scope="session")
    async def test_create_and_list_products(self, client):
        resp = await client.post("/api/v1/sales/products", json={
            "name": f"سیمان تست {uuid4().hex[:6]}",
            "code": f"CEM-{uuid4().hex[:4].upper()}",
            "category": "cement",
            "unit": "ton",
            "base_price": 8000000,
            "current_price": 8500000,
        })
        assert resp.status_code == 201
        pid = resp.json()["id"]

        resp = await client.get(f"/api/v1/sales/products/{pid}")
        assert resp.status_code == 200
        assert resp.json()["category"] == "cement"

    @pytest.mark.asyncio(loop_scope="session")
    async def test_list_invoices(self, client):
        resp = await client.get("/api/v1/sales/invoices")
        assert resp.status_code == 200
        assert "invoices" in resp.json()

    @pytest.mark.asyncio(loop_scope="session")
    async def test_sales_stats(self, client):
        resp = await client.get("/api/v1/sales/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_invoices" in data
        assert "total_revenue" in data


class TestAnalyticsAPI:
    """Integration tests for Analytics module (mock data)."""

    @pytest.mark.asyncio(loop_scope="session")
    async def test_funnel_metrics(self, client):
        resp = await client.get("/api/v1/analytics/analytics/funnel")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_leads"] > 0
        assert len(data["stage_counts"]) == 7

    @pytest.mark.asyncio(loop_scope="session")
    async def test_funnel_trend(self, client):
        resp = await client.get("/api/v1/analytics/analytics/funnel/trend")
        assert resp.status_code == 200
        assert len(resp.json()["snapshots"]) > 0

    @pytest.mark.asyncio(loop_scope="session")
    async def test_daily_report(self, client):
        resp = await client.get("/api/v1/analytics/analytics/reports/daily")
        assert resp.status_code == 200
        assert "leads" in resp.json()
        assert "revenue" in resp.json()


class TestSegmentationAPI:
    """Integration tests for Segmentation module."""

    @pytest.mark.asyncio(loop_scope="session")
    async def test_rfm_distribution(self, client):
        resp = await client.get("/api/v1/segments/segmentation/distribution")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_contacts"] > 0
        assert len(data["segments"]) == 11  # All RFM segments

    @pytest.mark.asyncio(loop_scope="session")
    async def test_segment_recommendations(self, client):
        resp = await client.get("/api/v1/segments/segmentation/recommendations/champions")
        assert resp.status_code == 200
        data = resp.json()
        assert data["segment"] == "champions"
        assert "recommended_message_types" in data


class TestTeamAPI:
    """Integration tests for Team module."""

    @pytest.mark.asyncio(loop_scope="session")
    async def test_list_salespeople(self, client):
        resp = await client.get("/api/v1/team/salespeople")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["salespeople"]) == 9

    @pytest.mark.asyncio(loop_scope="session")
    async def test_team_performance(self, client):
        resp = await client.get("/api/v1/team/performance")
        assert resp.status_code == 200


class TestDashboard:
    """Test web dashboard."""

    @pytest.mark.asyncio(loop_scope="session")
    async def test_dashboard_serves_html(self, client):
        resp = await client.get("/")
        assert resp.status_code == 200
        assert "فانلیر" in resp.text
        assert "<!DOCTYPE html>" in resp.text

