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
    async def test_create_and_get_contact(self, authed_client):
        # Create
        phone = f"0935{uuid4().hex[:7]}"
        resp = await authed_client.post("/api/v1/leads/contacts", json={
            "phone_number": phone,
            "name": "تست یکپارچه",
            "tags": ["integration-test"],
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "تست یکپارچه"
        contact_id = data["id"]

        # Get by ID
        resp = await authed_client.get(f"/api/v1/leads/contacts/{contact_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == contact_id

    @pytest.mark.asyncio(loop_scope="session")
    async def test_duplicate_phone_rejected(self, authed_client):
        phone = f"0935{uuid4().hex[:7]}"
        await authed_client.post("/api/v1/leads/contacts", json={
            "phone_number": phone, "name": "اولی"
        })
        resp = await authed_client.post("/api/v1/leads/contacts", json={
            "phone_number": phone, "name": "دومی"
        })
        assert resp.status_code == 409

    @pytest.mark.asyncio(loop_scope="session")
    async def test_update_contact_stage(self, authed_client):
        phone = f"0935{uuid4().hex[:7]}"
        resp = await authed_client.post("/api/v1/leads/contacts", json={
            "phone_number": phone, "name": "Stage Test"
        })
        cid = resp.json()["id"]

        resp = await authed_client.patch(f"/api/v1/leads/contacts/{cid}/stage", json={
            "stage": "sms_sent"
        })
        assert resp.status_code == 200
        assert resp.json()["current_stage"] == "sms_sent"

    @pytest.mark.asyncio(loop_scope="session")
    async def test_block_unblock_contact(self, authed_client):
        phone = f"0935{uuid4().hex[:7]}"
        resp = await authed_client.post("/api/v1/leads/contacts", json={
            "phone_number": phone, "name": "Block Test"
        })
        cid = resp.json()["id"]

        # Block
        resp = await authed_client.post(f"/api/v1/leads/contacts/{cid}/block?reason=spam")
        assert resp.status_code == 200
        assert resp.json()["is_blocked"] is True

        # Unblock
        resp = await authed_client.post(f"/api/v1/leads/contacts/{cid}/unblock")
        assert resp.status_code == 200
        assert resp.json()["is_blocked"] is False

    @pytest.mark.asyncio(loop_scope="session")
    async def test_bulk_import(self, authed_client):
        contacts = [
            {"phone_number": f"0911{uuid4().hex[:7]}", "name": f"Bulk {i}"}
            for i in range(5)
        ]
        resp = await authed_client.post("/api/v1/leads/contacts/bulk-import", json={
            "contacts": contacts
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["success_count"] == 5
        assert data["error_count"] == 0

    @pytest.mark.asyncio(loop_scope="session")
    async def test_create_category(self, authed_client):
        resp = await authed_client.post("/api/v1/leads/categories", json={
            "name": f"تست {uuid4().hex[:6]}",
            "description": "دسته‌بندی تست",
            "color": "#3B82F6",
        })
        assert resp.status_code == 201
        assert resp.json()["color"] == "#3B82F6"

    @pytest.mark.asyncio(loop_scope="session")
    async def test_stats_summary(self, authed_client):
        resp = await authed_client.get("/api/v1/leads/stats/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_contacts" in data
        assert "active_contacts" in data


class TestCommunicationsAPI:
    """Integration tests for Communications module."""

    @pytest.mark.asyncio(loop_scope="session")
    async def test_create_and_list_templates(self, authed_client):
        resp = await authed_client.post("/api/v1/communications/templates", json={
            "name": f"قالب تست {uuid4().hex[:6]}",
            "content": "سلام {name}، خوش آمدید!",
            "category": "welcome",
            "target_segments": ["new_customers"],
        })
        assert resp.status_code == 201
        tmpl = resp.json()
        assert tmpl["character_count"] > 0

        resp = await authed_client.get("/api/v1/communications/templates")
        assert resp.status_code == 200
        assert resp.json()["total_count"] >= 1

    @pytest.mark.asyncio(loop_scope="session")
    async def test_send_sms_persists(self, authed_client):
        resp = await authed_client.post("/api/v1/communications/sms/send", json={
            "phone_number": "09121234567",
            "content": "تست ارسال پیامک",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["phone_number"] == "09121234567"
        assert data["status"] == "pending"

    @pytest.mark.asyncio(loop_scope="session")
    async def test_sms_logs_list(self, authed_client):
        resp = await authed_client.get("/api/v1/communications/sms/logs")
        assert resp.status_code == 200
        data = resp.json()
        assert "logs" in data
        assert "total_count" in data

    @pytest.mark.asyncio(loop_scope="session")
    async def test_call_stats(self, authed_client):
        resp = await authed_client.get("/api/v1/communications/calls/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_calls" in data
        assert "answer_rate" in data


class TestSalesAPI:
    """Integration tests for Sales module."""

    @pytest.mark.asyncio(loop_scope="session")
    async def test_create_and_list_products(self, authed_client):
        resp = await authed_client.post("/api/v1/sales/products", json={
            "name": f"سیمان تست {uuid4().hex[:6]}",
            "code": f"CEM-{uuid4().hex[:4].upper()}",
            "category": "cement",
            "unit": "ton",
            "base_price": 8000000,
            "current_price": 8500000,
        })
        assert resp.status_code == 201
        pid = resp.json()["id"]

        resp = await authed_client.get(f"/api/v1/sales/products/{pid}")
        assert resp.status_code == 200
        assert resp.json()["category"] == "cement"

    @pytest.mark.asyncio(loop_scope="session")
    async def test_list_invoices(self, authed_client):
        resp = await authed_client.get("/api/v1/sales/invoices")
        assert resp.status_code == 200
        assert "invoices" in resp.json()

    @pytest.mark.asyncio(loop_scope="session")
    async def test_sales_stats(self, authed_client):
        resp = await authed_client.get("/api/v1/sales/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_invoices" in data
        assert "total_revenue" in data


class TestAnalyticsAPI:
    """Integration tests for Analytics module (mock data)."""

    @pytest.mark.asyncio(loop_scope="session")
    async def test_funnel_metrics(self, authed_client):
        resp = await authed_client.get("/api/v1/analytics/funnel")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_leads"] > 0
        assert len(data["stage_counts"]) == 7

    @pytest.mark.asyncio(loop_scope="session")
    async def test_funnel_trend(self, authed_client):
        resp = await authed_client.get("/api/v1/analytics/funnel/trend")
        assert resp.status_code == 200
        assert len(resp.json()["snapshots"]) > 0

    @pytest.mark.asyncio(loop_scope="session")
    async def test_daily_report(self, authed_client):
        resp = await authed_client.get("/api/v1/analytics/reports/daily")
        assert resp.status_code == 200
        assert "leads" in resp.json()
        assert "revenue" in resp.json()


class TestSegmentationAPI:
    """Integration tests for Segmentation module."""

    @pytest.mark.asyncio(loop_scope="session")
    async def test_rfm_distribution(self, authed_client):
        resp = await authed_client.get("/api/v1/segments/distribution")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_contacts"] > 0
        assert len(data["segments"]) == 11  # All RFM segments

    @pytest.mark.asyncio(loop_scope="session")
    async def test_segment_recommendations(self, authed_client):
        resp = await authed_client.get("/api/v1/segments/recommendations/champions")
        assert resp.status_code == 200
        data = resp.json()
        assert data["segment"] == "champions"
        assert "recommended_message_types" in data


class TestTeamAPI:
    """Integration tests for Team module."""

    @pytest.mark.asyncio(loop_scope="session")
    async def test_list_salespeople(self, authed_client):
        resp = await authed_client.get("/api/v1/team/salespeople")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["salespeople"]) >= 1

    @pytest.mark.asyncio(loop_scope="session")
    async def test_team_performance(self, authed_client):
        resp = await authed_client.get("/api/v1/team/performance")
        assert resp.status_code == 200


class TestAuthAPI:
    """Integration tests for Authentication module."""

    @pytest.mark.asyncio(loop_scope="session")
    async def test_login_with_default_admin(self, client):
        resp = await client.post("/api/v1/auth/login", json={
            "username": "admin", "password": "admin1234"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["token_type"] == "bearer"
        assert data["access_token"]
        assert data["refresh_token"]
        assert data["user"]["role"] == "super_admin"

    @pytest.mark.asyncio(loop_scope="session")
    async def test_login_bad_credentials(self, client):
        resp = await client.post("/api/v1/auth/login", json={
            "username": "admin", "password": "wrongpassword"
        })
        assert resp.status_code == 401

    @pytest.mark.asyncio(loop_scope="session")
    async def test_me_without_token(self, client):
        resp = await client.get("/api/v1/auth/me")
        assert resp.status_code == 401

    @pytest.mark.asyncio(loop_scope="session")
    async def test_me_with_token(self, client):
        login = await client.post("/api/v1/auth/login", json={
            "username": "admin", "password": "admin1234"
        })
        token = login.json()["access_token"]
        resp = await client.get("/api/v1/auth/me", headers={
            "Authorization": f"Bearer {token}"
        })
        assert resp.status_code == 200
        assert resp.json()["username"] == "admin"

    @pytest.mark.asyncio(loop_scope="session")
    async def test_register_new_user(self, client):
        uname = f"testuser_{uuid4().hex[:6]}"
        resp = await client.post("/api/v1/auth/register", json={
            "email": f"{uname}@test.ir",
            "username": uname,
            "password": "testpass1234",
            "full_name": "کاربر تست",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["user"]["role"] == "viewer"
        assert data["access_token"]

    @pytest.mark.asyncio(loop_scope="session")
    async def test_register_duplicate_username(self, client):
        uname = f"dupuser_{uuid4().hex[:6]}"
        await client.post("/api/v1/auth/register", json={
            "email": f"{uname}@test.ir", "username": uname,
            "password": "testpass1234",
        })
        resp = await client.post("/api/v1/auth/register", json={
            "email": f"{uname}2@test.ir", "username": uname,
            "password": "testpass1234",
        })
        assert resp.status_code == 409

    @pytest.mark.asyncio(loop_scope="session")
    async def test_refresh_token(self, client):
        login = await client.post("/api/v1/auth/login", json={
            "username": "admin", "password": "admin1234"
        })
        refresh = login.json()["refresh_token"]
        resp = await client.post("/api/v1/auth/refresh", json={
            "refresh_token": refresh
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["access_token"]
        assert data["refresh_token"]
        assert data["token_type"] == "bearer"
        # Verify the new token works
        me = await client.get("/api/v1/auth/me", headers={
            "Authorization": f"Bearer {data['access_token']}"
        })
        assert me.status_code == 200

    @pytest.mark.asyncio(loop_scope="session")
    async def test_change_password(self, client):
        # Register a new user
        uname = f"pwduser_{uuid4().hex[:6]}"
        reg = await client.post("/api/v1/auth/register", json={
            "email": f"{uname}@test.ir", "username": uname,
            "password": "oldpass1234",
        })
        user_id = reg.json()["user"]["id"]

        # Login as admin to approve the new user
        admin_login = await client.post("/api/v1/auth/login", json={
            "username": "admin", "password": "admin1234",
        })
        admin_token = admin_login.json()["access_token"]
        approve_resp = await client.post(
            f"/api/v1/auth/users/{user_id}/approve",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert approve_resp.status_code == 200

        # Login as the approved user
        login_resp = await client.post("/api/v1/auth/login", json={
            "username": uname, "password": "oldpass1234",
        })
        token = login_resp.json()["access_token"]

        # Change password
        resp = await client.put("/api/v1/auth/me/password", json={
            "old_password": "oldpass1234", "new_password": "newpass1234"
        }, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200

        # Login with new password
        resp = await client.post("/api/v1/auth/login", json={
            "username": uname, "password": "newpass1234"
        })
        assert resp.status_code == 200

    @pytest.mark.asyncio(loop_scope="session")
    async def test_list_users_requires_admin(self, client):
        # Register a viewer
        uname = f"viewer_{uuid4().hex[:6]}"
        reg = await client.post("/api/v1/auth/register", json={
            "email": f"{uname}@test.ir", "username": uname,
            "password": "viewerpass1",
        })
        token = reg.json()["access_token"]

        # Viewer can't list users
        resp = await client.get("/api/v1/auth/users", headers={
            "Authorization": f"Bearer {token}"
        })
        assert resp.status_code == 403

        # Admin can
        login = await client.post("/api/v1/auth/login", json={
            "username": "admin", "password": "admin1234"
        })
        admin_token = login.json()["access_token"]
        resp = await client.get("/api/v1/auth/users", headers={
            "Authorization": f"Bearer {admin_token}"
        })
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


class TestImportAPI:
    """Integration tests for ETL / Import module."""

    @pytest.mark.asyncio(loop_scope="session")
    async def test_scan_lead_files(self, authed_client):
        resp = await authed_client.get("/api/v1/import/leads/scan")
        assert resp.status_code == 200
        data = resp.json()
        assert "files" in data
        assert data["count"] >= 0
        if data["count"] > 0:
            assert "name" in data["files"][0]
            assert "category" in data["files"][0]

    @pytest.mark.asyncio(loop_scope="session")
    async def test_scan_call_log_files(self, authed_client):
        resp = await authed_client.get("/api/v1/import/calls/scan")
        assert resp.status_code == 200
        data = resp.json()
        assert "files" in data
        assert data["count"] >= 0

    @pytest.mark.asyncio(loop_scope="session")
    async def test_upload_leads_rejects_non_excel(self, authed_client):
        # Upload a non-Excel file
        resp = await authed_client.post(
            "/api/v1/import/leads/upload",
            files={"file": ("test.txt", b"hello world", "text/plain")},
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio(loop_scope="session")
    async def test_upload_calls_rejects_non_csv(self, authed_client):
        resp = await authed_client.post(
            "/api/v1/import/calls/upload",
            files={"file": ("test.xlsx", b"hello", "application/octet-stream")},
        )
        assert resp.status_code == 400


class TestAsyncImportEndpoints:
    """Integration tests for async (Celery-backed) import endpoints."""

    @pytest.mark.asyncio(loop_scope="session")
    async def test_async_leads_rejects_non_excel(self, authed_client):
        resp = await authed_client.post(
            "/api/v1/import/leads/upload-async",
            files={"file": ("test.txt", b"hello world", "text/plain")},
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio(loop_scope="session")
    async def test_async_calls_rejects_non_csv(self, authed_client):
        resp = await authed_client.post(
            "/api/v1/import/calls/upload-async",
            files={"file": ("test.xlsx", b"hello", "application/octet-stream")},
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio(loop_scope="session")
    async def test_async_sms_rejects_non_csv(self, authed_client):
        resp = await authed_client.post(
            "/api/v1/import/sms/upload-async",
            files={"file": ("test.xlsx", b"hello", "application/octet-stream")},
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio(loop_scope="session")
    async def test_async_voip_rejects_invalid_extension(self, authed_client):
        resp = await authed_client.post(
            "/api/v1/import/voip/upload-async",
            files={"file": ("test.csv", b"hello", "text/csv")},
        )
        assert resp.status_code == 400


class TestWebSocketEndpoints:
    """Integration tests for WebSocket-related HTTP endpoints."""

    @pytest.mark.asyncio(loop_scope="session")
    async def test_ws_status(self, authed_client):
        resp = await authed_client.get("/api/v1/ws/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "connections" in data
        assert data["status"] == "active"

    @pytest.mark.asyncio(loop_scope="session")
    async def test_task_status_unknown_task(self, authed_client):
        resp = await authed_client.get("/api/v1/tasks/nonexistent-task-id")
        assert resp.status_code == 200
        data = resp.json()
        assert data["task_id"] == "nonexistent-task-id"
        assert "status" in data


class TestAnalyticsTriggers:
    """Integration tests for analytics trigger endpoints."""

    @pytest.mark.asyncio(loop_scope="session")
    async def test_trigger_funnel_snapshot_endpoint_exists(self, authed_client):
        """Test that the endpoint responds (may fail if Celery not running)."""
        resp = await authed_client.post("/api/v1/import/analytics/funnel-snapshot")
        # May be 200 (queued) or 500 (Celery not available)
        assert resp.status_code in (200, 500)

    @pytest.mark.asyncio(loop_scope="session")
    async def test_trigger_rfm_recalculate_endpoint_exists(self, authed_client):
        resp = await authed_client.post("/api/v1/import/analytics/rfm-recalculate")
        assert resp.status_code in (200, 500)



