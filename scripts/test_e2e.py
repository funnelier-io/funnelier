"""End-to-end test for Funnelier API with real database."""
import json
import sys
import urllib.request
import urllib.error

BASE = "http://127.0.0.1:8099"
passed = 0
failed = 0


def api(method, path, data=None):
    url = BASE + path
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, method=method)
    if body:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read()
        return e.code, json.loads(body) if body else {}


def check(num, name, status, expected_status, extra=""):
    global passed, failed
    ok = status == expected_status
    icon = "✓" if ok else "✗"
    if ok:
        passed += 1
    else:
        failed += 1
    print(f"  {icon} {num}. {name}: {status} {extra}")


def main():
    global passed, failed
    print("=" * 65)
    print("  FUNNELIER E2E TEST SUITE - Database-Backed API")
    print("=" * 65)

    # ── Health ──
    print("\n── Health & Info ──")
    s, r = api("GET", "/health")
    check(1, "Health check", s, 200, f"-> {r.get('status')}")

    s, r = api("GET", "/api/v1")
    check(2, "API info", s, 200, f"-> {len(r.get('endpoints', {}))} modules")

    # ── Leads Module (DB-backed) ──
    print("\n── Leads Module (PostgreSQL) ──")
    s, r = api("GET", "/api/v1/leads/contacts")
    prev_total = r.get("total_count", 0)
    check(3, "List contacts", s, 200, f"-> existing={prev_total}")

    s, r = api("POST", "/api/v1/leads/contacts", {
        "phone_number": "09384567890", "name": "تست E2E", "tags": ["e2e"]
    })
    cid = r.get("id", "")
    check(4, "Create contact", s, 201, f"-> id={cid[:8]}...")

    s, r = api("GET", f"/api/v1/leads/contacts/{cid}")
    check(5, "Get contact by ID", s, 200, f"-> stage={r.get('current_stage')}")

    s, r = api("PATCH", f"/api/v1/leads/contacts/{cid}/stage", {"stage": "sms_sent"})
    check(6, "Update stage", s, 200, f"-> stage={r.get('current_stage')}")

    s, r = api("GET", "/api/v1/leads/contacts/by-phone/09384567890")
    check(7, "Get by phone", s, 200, f"-> name={r.get('name')}")

    s, r = api("POST", f"/api/v1/leads/contacts/{cid}/block?reason=test_block")
    check(8, "Block contact", s, 200, f"-> blocked={r.get('is_blocked')}")

    s, r = api("POST", f"/api/v1/leads/contacts/{cid}/unblock")
    check(9, "Unblock contact", s, 200, f"-> blocked={r.get('is_blocked')}")

    s, r = api("POST", "/api/v1/leads/contacts", {"phone_number": "09384567890", "name": "Dup"})
    check(10, "Duplicate check", s, 409, f"-> {r.get('detail', '')[:40]}")

    s, r = api("POST", "/api/v1/leads/contacts/bulk-import", {
        "contacts": [
            {"phone_number": "09440001111", "name": "بالک A"},
            {"phone_number": "09440002222", "name": "بالک B"},
        ]
    })
    check(11, "Bulk import", s, 200, f"-> success={r.get('success_count')}")

    # Categories
    s, r = api("POST", "/api/v1/leads/categories", {
        "name": f"تست E2E {passed}", "description": "تست", "color": "#EF4444"
    })
    check(12, "Create category", s, 201, f"-> name={r.get('name')}")

    s, r = api("GET", "/api/v1/leads/categories")
    check(13, "List categories", s, 200, f"-> count={r.get('total_count')}")

    s, r = api("GET", "/api/v1/leads/stats/summary")
    check(14, "Stats summary", s, 200, f"-> total={r.get('total_contacts')}")

    # ── Communications Module (DB-backed) ──
    print("\n── Communications Module (PostgreSQL) ──")

    s, r = api("POST", "/api/v1/communications/templates", {
        "name": "تست E2E", "content": "سلام {name}، تست!", "category": "test",
        "target_segments": ["new_customers"]
    })
    tmpl_id = r.get("id", "")
    check(15, "Create SMS template", s, 201, f"-> id={tmpl_id[:8]}...")

    s, r = api("GET", "/api/v1/communications/templates")
    check(16, "List templates", s, 200, f"-> count={r.get('total_count')}")

    if tmpl_id:
        s, r = api("GET", f"/api/v1/communications/templates/{tmpl_id}")
        check(17, "Get template by ID", s, 200, f"-> name={r.get('name')}")
    else:
        check(17, "Get template by ID", 0, 200, "-> SKIPPED (no id)")

    s, r = api("POST", "/api/v1/communications/sms/send", {
        "phone_number": "09384567890", "content": "تست ارسال"
    })
    sms_id = r.get("id", "")
    check(18, "Send SMS (persist)", s, 200, f"-> id={sms_id[:8] if sms_id else 'N/A'}...")

    s, r = api("GET", "/api/v1/communications/sms/logs")
    check(19, "List SMS logs", s, 200, f"-> count={r.get('total_count')}")

    s, r = api("GET", "/api/v1/communications/sms/stats")
    check(20, "SMS stats", s, 200, f"-> total_sent={r.get('total_sent')}")

    s, r = api("GET", "/api/v1/communications/calls")
    check(21, "List call logs", s, 200, f"-> count={r.get('total_count')}")

    s, r = api("GET", "/api/v1/communications/calls/stats")
    check(22, "Call stats", s, 200, f"-> total={r.get('total_calls')}")

    # ── Sales Module (DB-backed) ──
    print("\n── Sales Module (PostgreSQL) ──")

    s, r = api("POST", "/api/v1/sales/products", {
        "name": "سیمان تیپ ۲", "code": "CEM-T2-E2E", "category": "cement",
        "unit": "ton", "base_price": 8000000, "current_price": 8500000,
        "recommended_segments": ["loyal", "champions"]
    })
    pid = r.get("id", "")
    check(23, "Create product", s, 201, f"-> id={pid[:8]}...")

    s, r = api("GET", "/api/v1/sales/products")
    check(24, "List products", s, 200, f"-> count={r.get('total_count')}")

    if pid:
        s, r = api("GET", f"/api/v1/sales/products/{pid}")
        check(25, "Get product by ID", s, 200, f"-> name={r.get('name')}")
    else:
        check(25, "Get product by ID", 0, 200, "-> SKIPPED")

    s, r = api("GET", "/api/v1/sales/invoices")
    check(26, "List invoices", s, 200, f"-> count={r.get('total_count')}")

    s, r = api("GET", "/api/v1/sales/payments")
    check(27, "List payments", s, 200, f"-> count={r.get('total_count')}")

    s, r = api("GET", "/api/v1/sales/stats")
    check(28, "Sales stats", s, 200, f"-> total_invoices={r.get('total_invoices')}")

    # ── Analytics, Segments, Team, Campaigns (mock but routed) ──
    print("\n── Other Modules (mock data, routes verified) ──")

    s, r = api("GET", "/api/v1/analytics/analytics/funnel")
    check(29, "Funnel metrics", s, 200, f"-> leads={r.get('total_leads')}")

    s, r = api("GET", "/api/v1/segments/segmentation/distribution")
    check(30, "RFM distribution", s, 200, f"-> segments={len(r.get('segments', []))}")

    s, r = api("GET", "/api/v1/segments/segmentation/recommendations/at_risk")
    check(31, "Segment recommendations", s, 200, f"-> segment={r.get('segment')}")

    s, r = api("GET", "/api/v1/team/salespeople")
    check(32, "Team salespeople", s, 200, f"-> count={len(r.get('salespeople', []))}")

    s, r = api("GET", "/api/v1/team/performance")
    check(33, "Team performance", s, 200)

    s, r = api("GET", "/api/v1/campaigns")
    check(34, "List campaigns", s, 200)

    # ── Dashboard ──
    print("\n── Web Dashboard ──")
    req = urllib.request.Request(BASE + "/")
    with urllib.request.urlopen(req) as resp:
        html = resp.read().decode()
        has_title = "فانلیر" in html
    check(35, "Dashboard HTML", resp.status, 200, f"-> Persian title={has_title}")

    # ── Summary ──
    print("\n" + "=" * 65)
    total = passed + failed
    print(f"  Results: {passed}/{total} passed, {failed} failed")
    if failed == 0:
        print("  ✅ ALL TESTS PASSED")
    else:
        print("  ❌ SOME TESTS FAILED")
    print("=" * 65)
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()

