"""API tests for bill generation and billing rules (tax calculations)."""

from decimal import Decimal
from datetime import date

import httpx


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


def _cleanup_fee_items(base_url: str, admin_token: str):
    """Deactivate all existing fee items to start with a clean slate."""
    with httpx.Client(
        base_url=base_url,
        timeout=30.0,
        headers={"Authorization": f"Bearer {admin_token}"},
    ) as c:
        resp = c.get("/billing/fee-items")
        resp.raise_for_status()
        for item in resp.json()["items"]:
            c.put(
                f"/billing/fee-items/{item['id']}",
                json={"is_active": False},
                headers={"If-Match": str(item["version"])},
            )


def test_bill_generation_with_tax_calculations(base_url: str, auth_token: str):
    """
    Create fee items, generate bills for a unique period, verify:
    - subtotal = 1500.00
    - tax_total = 6.00 (6% of $100 parking fee)
    - total = 1506.00
    - line_items has 2 items
    """
    property_id = _get_property_id(base_url, auth_token)
    billing_period = f"{date.today().year + 5}-{date.today().month:02d}"

    with httpx.Client(
        base_url=base_url,
        timeout=30.0,
        headers={"Authorization": f"Bearer {auth_token}"},
    ) as c:
        # Deactivate existing fee items so only our two are active
        _cleanup_fee_items(base_url, auth_token)

        # Create "Monthly Rent" $1400, not taxable
        rent_resp = c.post(
            "/billing/fee-items",
            json={
                "property_id": property_id,
                "name": "Monthly Rent",
                "amount": 1400.00,
                "is_taxable": False,
            },
        )
        print(f"[POST /billing/fee-items 'Monthly Rent'] status={rent_resp.status_code}")
        assert rent_resp.status_code == 201

        # Create "Parking Fee" $100, taxable
        parking_resp = c.post(
            "/billing/fee-items",
            json={
                "property_id": property_id,
                "name": "Parking Fee",
                "amount": 100.00,
                "is_taxable": True,
            },
        )
        print(f"[POST /billing/fee-items 'Parking Fee'] status={parking_resp.status_code}")
        assert parking_resp.status_code == 201

        # Generate bills for a far-future period to avoid collisions with existing data
        gen_resp = c.post(
            "/billing/generate",
            json={"property_id": property_id, "billing_period": billing_period},
        )
        print(f"[POST /billing/generate period={billing_period}] status={gen_resp.status_code}")
        assert gen_resp.status_code == 202
        gen_data = gen_resp.json()
        print(f"  -> bills_created={gen_data.get('bills_created')}")
        assert gen_data.get("bills_created", 0) > 0

        # Fetch the generated bills for this test period
        bills_resp = c.get("/billing/bills", params={"page_size": 100})
        bills_resp.raise_for_status()
        all_bills = bills_resp.json()["items"]

        # Filter for the target billing period and pick a newly-generated bill
        period_bills = [b for b in all_bills if b["billing_period"] == billing_period]
        assert len(period_bills) > 0, f"No bills found for {billing_period}"

        bill = period_bills[0]
        print(f"\n  Bill details:")
        print(f"    subtotal  = {bill['subtotal']}")
        print(f"    tax_total = {bill['tax_total']}")
        print(f"    late_fee  = {bill['late_fee']}")
        print(f"    total     = {bill['total']}")
        print(f"    line_items count = {len(bill['line_items'])}")

        # Verify amounts
        subtotal = Decimal(str(bill["subtotal"]))
        tax_total = Decimal(str(bill["tax_total"]))
        total = Decimal(str(bill["total"]))

        assert subtotal == Decimal("1500.00"), f"Expected subtotal=1500.00, got {subtotal}"
        assert tax_total == Decimal("6.00"), f"Expected tax_total=6.00, got {tax_total}"
        assert total == Decimal("1506.00"), f"Expected total=1506.00, got {total}"

        # Verify line items
        assert len(bill["line_items"]) == 2, f"Expected 2 line items, got {len(bill['line_items'])}"

        for li in bill["line_items"]:
            print(f"    line_item: {li['description']} amount={li['amount']} tax={li['tax_amount']}")

        print("\n  All billing rule assertions passed.")
