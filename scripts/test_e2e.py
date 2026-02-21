"""End-to-end test for Funnelier API with real database."""
import json
import urllib.request
import urllib.error

BASE = "http://127.0.0.1:8099"


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


def main():
    print("=" * 60)
    print("FUNNELIER E2E TEST - Database-Backed API")
    print("=" * 60)

    # 1. Health
    s, r = api("GET", "/health")
    print(f"\n1. Health Check: {s} -> {r['status']}")

    # 2. List contacts
    s, r = api("GET", "/api/v1/leads/contacts")
    print(f"2. List Contacts: {s} -> total={r['total_count']}")

    # 3. Create contact
    s, r = api("POST", "/api/v1/leads/contacts", {
        "phone_number": "09357654321",
        "name": "علی رضایی",
        "tags": ["سازنده", "تهران"]
    })
    contact_id = r.get("id", "")
    print(f"3. Create Contact: {s} -> id={contact_id[:8]}... name={r.get('name')}")

    # 4. Get by ID
    s, r = api("GET", f"/api/v1/leads/contacts/{contact_id}")
    print(f"4. Get Contact: {s} -> phone={r.get('phone_number')} stage={r.get('current_stage')}")

    # 5. Update stage
    s, r = api("PATCH", f"/api/v1/leads/contacts/{contact_id}/stage", {"stage": "sms_sent"})
    print(f"5. Update Stage: {s} -> stage={r.get('current_stage')}")

    # 6. Get by phone
    s, r = api("GET", "/api/v1/leads/contacts/by-phone/09357654321")
    print(f"6. Get by Phone: {s} -> name={r.get('name')}")

    # 7. Create category
    s, r = api("POST", "/api/v1/leads/categories", {
        "name": "پیمانکاران تهران",
        "description": "پیمانکاران شهرداری تهران",
        "color": "#F59E0B"
    })
    cat_id = r.get("id", "")
    print(f"7. Create Category: {s} -> id={cat_id[:8]}... name={r.get('name')}")

    # 8. List categories
    s, r = api("GET", "/api/v1/leads/categories")
    print(f"8. List Categories: {s} -> count={r.get('total_count')}")

    # 9. Stats
    s, r = api("GET", "/api/v1/leads/stats/summary")
    print(f"9. Stats Summary: {s} -> total={r.get('total_contacts')} active={r.get('active_contacts')}")

    # 10. Block contact
    s, r = api("POST", f"/api/v1/leads/contacts/{contact_id}/block?reason=test")
    print(f"10. Block Contact: {s} -> blocked={r.get('is_blocked')}")

    # 11. Unblock
    s, r = api("POST", f"/api/v1/leads/contacts/{contact_id}/unblock")
    print(f"11. Unblock Contact: {s} -> blocked={r.get('is_blocked')}")

    # 12. Duplicate check
    s, r = api("POST", "/api/v1/leads/contacts", {
        "phone_number": "09357654321",
        "name": "Duplicate"
    })
    print(f"12. Duplicate Check: {s} -> {r.get('detail', 'ERROR')}")

    # 13. Bulk import
    s, r = api("POST", "/api/v1/leads/contacts/bulk-import", {
        "contacts": [
            {"phone_number": "09111111111", "name": "بالک ۱"},
            {"phone_number": "09222222222", "name": "بالک ۲"},
            {"phone_number": "09333333333", "name": "بالک ۳"},
        ]
    })
    print(f"13. Bulk Import: {s} -> success={r.get('success_count')} errors={r.get('error_count')}")

    # 14. Final count
    s, r = api("GET", "/api/v1/leads/stats/summary")
    print(f"14. Final Stats: {s} -> total={r.get('total_contacts')}")

    # 15. Dashboard
    req = urllib.request.Request(BASE + "/")
    with urllib.request.urlopen(req) as resp:
        html = resp.read().decode()
        has_title = "فانلیر" in html
    print(f"15. Dashboard: {resp.status} -> title present={has_title}")

    # 16-18: Other modules (still mock)
    s, r = api("GET", "/api/v1/sales/products")
    print(f"16. Products (mock): {s} -> count={len(r.get('products', []))}")

    s, r = api("GET", "/api/v1/team/salespeople")
    print(f"17. Salespeople (mock): {s} -> count={len(r.get('salespeople', []))}")

    s, r = api("GET", "/api/v1/segments/segmentation/distribution")
    print(f"18. RFM Segments (mock): {s} -> segments={len(r.get('segments', []))}")

    # 19. Verify data persists in DB
    s, r = api("GET", "/api/v1/leads/contacts")
    print(f"19. Contacts Persisted: {s} -> total={r['total_count']} contacts in PostgreSQL")

    print("\n" + "=" * 60)
    print("ALL TESTS COMPLETED")
    print("=" * 60)


if __name__ == "__main__":
    main()

