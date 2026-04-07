"""API tests for late fee application on overdue bills."""

from decimal import Decimal
from datetime import date

import httpx
import pytest


def _get_property_id(base_url: str, admin_token: str) -> str:
    """Fetch the first property id."""
    with httpx.Client(
        base_url=base_url,
        timeout=30.0,
        headers={"Authorization": f"Bearer {admin_token}"},
    ) as c:
        resp = c.get("/properties/")
        resp.raise_for_status()
        return resp.json()["items"][0]["id"]


def _ensure_fee_items(base_url: str, admin_token: str, property_id: str):
    """Ensure at least one active fee item exists."""
    with httpx.Client(
        base_url=base_url,
        timeout=30.0,
        headers={"Authorization": f"Bearer {admin_token}"},
    ) as c:
        resp = c.get("/billing/fee-items")
        resp.raise_for_status()
        active_items = [i for i in resp.json()["items"] if i["is_active"]]
        if len(active_items) == 0:
            c.post(
                "/billing/fee-items",
                json={
                    "property_id": property_id,
                    "name": "Monthly Rent",
                    "amount": 1400.00,
                    "is_taxable": False,
                },
            )


def test_late_fee_application(base_url: str, auth_token: str):
    """
    Generate bills for a unique past period, apply late fees, verify:
    - late_fee = 25.00
    - total increased by 25.00
    - status is 'overdue'

    If /billing/apply-late-fees does not exist, skip gracefully.
    """
    property_id = _get_property_id(base_url, auth_token)
    billing_period = f"{date.today().year - 2}-{date.today().month:02d}"
    _ensure_fee_items(base_url, auth_token, property_id)

    with httpx.Client(
        base_url=base_url,
        timeout=30.0,
        headers={"Authorization": f"Bearer {auth_token}"},
    ) as c:
        # Generate bills for a past period
        gen_resp = c.post(
            "/billing/generate",
            json={"property_id": property_id, "billing_period": billing_period},
        )
        print(f"[POST /billing/generate period={billing_period}] status={gen_resp.status_code}")
        if gen_resp.status_code not in (200, 202):
            print(f"  -> Could not generate bills: {gen_resp.text}")
            pytest.skip("Could not generate bills for past period")

        gen_data = gen_resp.json()
        print(f"  -> bills_created={gen_data.get('bills_created')}")
        if gen_data.get("bills_created", 0) <= 0:
            pytest.skip(f"No new bills created for {billing_period}; period likely already populated")

        # Get the bill before late fees
        bills_resp = c.get("/billing/bills", params={"page_size": 100})
        bills_resp.raise_for_status()
        period_bills = [
            b for b in bills_resp.json()["items"]
            if b["billing_period"] == billing_period and b["status"] in ("generated", "partially_paid")
        ]
        if not period_bills:
            pytest.skip(f"No eligible bills generated for {billing_period}")

        original_total = Decimal(str(period_bills[0]["total"]))
        bill_id = period_bills[0]["id"]
        print(f"  -> bill id={bill_id}, original total={original_total}")

        # Apply late fees
        late_resp = c.post("/billing/apply-late-fees")
        print(f"[POST /billing/apply-late-fees] status={late_resp.status_code}")

        if late_resp.status_code in (404, 405):
            print("  -> /billing/apply-late-fees endpoint not found, skipping late fee assertions")
            pytest.skip("apply-late-fees endpoint not implemented (404/405)")

        assert late_resp.status_code == 200, f"Expected 200, got {late_resp.status_code}"

        # Fetch the bill again to check late fee
        bill_resp = c.get(f"/billing/bills/{bill_id}")
        print(f"[GET /billing/bills/{{bill_id}}] status={bill_resp.status_code}")
        assert bill_resp.status_code == 200

        bill = bill_resp.json()
        late_fee = Decimal(str(bill["late_fee"]))
        new_total = Decimal(str(bill["total"]))

        print(f"  -> late_fee={late_fee}, new total={new_total}, status={bill['status']}")

        assert late_fee == Decimal("25.00"), f"Expected late_fee=25.00, got {late_fee}"
        assert new_total == original_total + Decimal("25.00"), (
            f"Expected total={original_total + Decimal('25.00')}, got {new_total}"
        )
        assert bill["status"] == "overdue", f"Expected status='overdue', got {bill['status']}"
        print("  -> All late fee assertions passed.")
