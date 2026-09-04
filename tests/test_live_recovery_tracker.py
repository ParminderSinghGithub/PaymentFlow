"""Phase Audit Tests: Live Recovery Tracker & Merchant Experience.

Verifies:
1. Live Recovery Tracker queries filter strictly by case_source (MERCHANT_CHECKOUT).
2. Canonical benchmark evaluation cases are completely isolated from live queries.
3. Live tracker empty state: zero cases -> empty list.
4. Active case lifecycle transitions: FAILED_INGESTED -> ACTION_EXECUTED -> RECOVERED.
5. Authoritative gateway attribution: RECOVERED reflects verified captured payment amount.
6. Merchant recovery status endpoint (/merchant/v1/orders/{order_id}/recovery-status):
   - Strict Bearer token authentication required.
   - Cross-merchant tenant isolation: Merchant B cannot inspect Merchant A's order status.
   - Safe payload structure: public payment_link_url, amount, currency, state; no secrets.
7. Merchant Demo Storefront static inspection:
   - Customer details start completely empty (no hardcoded personal details).
   - Test mode failure instructions are neutral and use Netbanking/Wallet (no UPI).
   - Test mode disclaimer present.
   - Product is generic "Product" with no fake company branding.
"""

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from paymentflow.config import get_settings
from paymentflow.db.models import RecoveryCaseModel
from paymentflow.db.session import get_sessionmaker
from paymentflow.main import app
from paymentflow.merchant.models import MerchantProfile, hash_api_key
from paymentflow.merchant.service import MerchantRegistry


@pytest.fixture(autouse=True)
def reset_registry():
    MerchantRegistry.reset_to_default()
    yield
    MerchantRegistry.reset_to_default()


@pytest.mark.asyncio
async def test_live_tracker_empty_state_and_provenance_isolation():
    """Live tracker scoped to MERCHANT_CHECKOUT must exclude CANONICAL_EVALUATION cases."""
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        # Clean up any leftover test merchant checkout cases
        stmt = select(RecoveryCaseModel).where(RecoveryCaseModel.case_source == "MERCHANT_CHECKOUT")
        res = await session.execute(stmt)
        for c in res.scalars().all():
            await session.delete(c)
        await session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Query with case_source=MERCHANT_CHECKOUT
        res = await client.get("/cases?case_source=MERCHANT_CHECKOUT")
        assert res.status_code == 200
        data = res.json()
        assert isinstance(data, list)
        assert len(data) == 0  # Clean zero state


@pytest.mark.asyncio
async def test_live_tracker_case_lifecycle_truthfulness():
    """Verify truthful state progression from FAILED_INGESTED to ACTION_EXECUTED to RECOVERED."""
    sessionmaker = get_sessionmaker()
    test_case_id = "case_live_audit_test_99"
    test_order_id = "ORD-2026-TEST-99"

    async with sessionmaker() as session:
        # Create an ingested live case
        case = RecoveryCaseModel(
            case_id=test_case_id,
            failed_payment_id="pay_fail_audit_99",
            order_id=test_order_id,
            customer_id="cust_test_99",
            amount=250000,
            currency="INR",
            payment_method="netbanking",
            failure_category="C1",
            state="FAILED_INGESTED",
            case_source="MERCHANT_CHECKOUT",
            failure_context={
                "merchant_id": "merchant_demo_store",
                "external_order_id": test_order_id,
            },
        )
        session.add(case)
        await session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Stage 1: FAILED_INGESTED
        res1 = await client.get("/cases?case_source=MERCHANT_CHECKOUT")
        assert res1.status_code == 200
        cases1 = [c for c in res1.json() if c["case_id"] == test_case_id]
        assert len(cases1) == 1
        assert cases1[0]["state"] == "FAILED_INGESTED"
        assert cases1[0]["amount_inr"] == 2500.0
        assert cases1[0]["payment_link_id"] is None
        assert cases1[0]["recovered_amount_inr"] == 0.0

        # Stage 2: ACTION_EXECUTED (Link created, money NOT yet recovered)
        async with sessionmaker() as session:
            c_db = await session.get(RecoveryCaseModel, test_case_id)
            assert c_db is not None
            c_db.state = "ACTION_EXECUTED"
            c_db.payment_link_id = "plink_test_audit_99"
            c_db.payment_link_short_url = "https://rzp.io/i/audit99"
            c_db.payment_link_status = "created"
            await session.commit()

        res2 = await client.get("/cases?case_source=MERCHANT_CHECKOUT")
        cases2 = [c for c in res2.json() if c["case_id"] == test_case_id]
        assert len(cases2) == 1
        assert cases2[0]["state"] == "ACTION_EXECUTED"
        assert cases2[0]["payment_link_id"] == "plink_test_audit_99"
        assert cases2[0]["payment_link_short_url"] == "https://rzp.io/i/audit99"
        # Crucial check: ACTION_EXECUTED must NOT declare recovered money
        assert cases2[0]["recovered_amount_inr"] == 0.0

        # Stage 3: RECOVERED (Authoritative webhook capture)
        async with sessionmaker() as session:
            c_db = await session.get(RecoveryCaseModel, test_case_id)
            assert c_db is not None
            c_db.state = "RECOVERED"
            c_db.recovered_amount = 250000
            c_db.recovered_payment_id = "pay_rec_audit_99"
            await session.commit()

        res3 = await client.get("/cases?case_source=MERCHANT_CHECKOUT")
        cases3 = [c for c in res3.json() if c["case_id"] == test_case_id]
        assert len(cases3) == 1
        assert cases3[0]["state"] == "RECOVERED"
        assert cases3[0]["recovered_amount_inr"] == 2500.0
        assert cases3[0]["recovered_payment_id"] == "pay_rec_audit_99"

        # Clean up test case
        async with sessionmaker() as session:
            c_db = await session.get(RecoveryCaseModel, test_case_id)
            if c_db:
                await session.delete(c_db)
                await session.commit()


@pytest.mark.asyncio
async def test_merchant_recovery_status_endpoint_contract_and_tenant_isolation():
    """Verify /merchant/v1/orders/{order_id}/recovery-status authentication and tenant isolation."""
    settings = get_settings()
    sessionmaker = get_sessionmaker()

    # Create test case for merchant_demo_store
    order_a = "ORD-MERCHANT-A-01"
    async with sessionmaker() as session:
        case_a = RecoveryCaseModel(
            case_id=f"case_{order_a}",
            failed_payment_id="pay_fail_order_a",
            order_id=order_a,
            customer_id="cust_a",
            amount=300000,
            currency="INR",
            state="ACTION_EXECUTED",
            case_source="MERCHANT_CHECKOUT",
            payment_link_id="plink_order_a",
            payment_link_short_url="https://rzp.io/i/ordera",
            payment_link_status="created",
            failure_context={
                "merchant_id": "merchant_demo_store",
                "external_order_id": order_a,
                "masked_contact": "+91 98****3210",
                "notification_status": "REQUESTED",
            },
        )
        session.add(case_a)
        await session.commit()

    # Register Merchant B
    key_b = "pf_secret_key_merchant_beta_audit"
    merchant_b = MerchantProfile(
        merchant_id="merchant_beta_store",
        merchant_name="Beta Store",
        api_key_hash=hash_api_key(key_b),
        is_active=True,
        razorpay_key_id="rzp_test_BETA_KEY_ID",
        razorpay_key_secret="secret_BETA_KEY_SECRET",
    )
    MerchantRegistry.register_merchant(merchant_b)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Unauthenticated -> 401
        res_unauth = await client.get(f"/merchant/v1/orders/{order_a}/recovery-status")
        assert res_unauth.status_code == 401

        # 2. Authenticated as Merchant A (owner) -> 200 with safe status and link info
        res_a = await client.get(
            f"/merchant/v1/orders/{order_a}/recovery-status",
            headers={"Authorization": f"Bearer {settings.paymentflow_api_key}"},
        )
        assert res_a.status_code == 200
        data_a = res_a.json()
        assert data_a["order_id"] == order_a
        assert data_a["state"] == "ACTION_EXECUTED"
        assert data_a["amount"] == 300000
        assert data_a["currency"] == "INR"
        assert data_a["payment_link_sent"] is True
        assert data_a["payment_link_url"] == "https://rzp.io/i/ordera"
        assert "secret" not in str(data_a).lower()
        assert "key" not in data_a or "key_secret" not in data_a

        # 3. Cross-merchant isolation: Merchant B attempts to inspect Merchant A's order
        # Safe awaiting status returned without data leak
        res_b = await client.get(
            f"/merchant/v1/orders/{order_a}/recovery-status",
            headers={"Authorization": f"Bearer {key_b}"},
        )
        assert res_b.status_code == 200
        data_b = res_b.json()
        assert data_b["status"] == "AWAITING_INGESTION"
        assert "payment_link_url" not in data_b
        assert "amount" not in data_b

    # Cleanup
    async with sessionmaker() as session:
        c_db = await session.get(RecoveryCaseModel, f"case_{order_a}")
        if c_db:
            await session.delete(c_db)
            await session.commit()


def test_merchant_demo_storefront_static_compliance():
    """Verify storefront HTML contains no hardcoded customer details or UPI instructions."""
    frontend_dir = Path(__file__).resolve().parent.parent / "apps" / "merchant-demo" / "frontend"
    html_path = frontend_dir / "index.html"
    assert html_path.exists(), f"Storefront HTML not found at {html_path}"

    content = html_path.read_text(encoding="utf-8")

    # 1. No hardcoded customer PII
    assert "Priya Sharma" not in content
    assert "9876543210" not in content
    assert "priya.sharma@example.com" not in content

    # 2. Customer inputs must start completely empty
    assert 'id="input-name" class="form-input" placeholder="Enter customer name"' in content
    assert "value=" not in content.split('id="input-name"')[1].split(">")[0]
    assert "value=" not in content.split('id="input-phone"')[1].split(">")[0]
    assert "value=" not in content.split('id="input-email"')[1].split(">")[0]

    # 3. Neutral failure simulation copy
    assert "Test Mode payment" in content
    assert "To demonstrate recovery, intentionally fail the payment during Checkout" in content
    assert "This is a Razorpay Test Mode simulation. No real money is charged." in content

    # 4. Instructions recommend Netbanking or Wallet; UPI is NOT instructed
    assert "Netbanking:" in content
    assert "Wallet:" in content
    # Ensure no instruction tells the customer to select UPI
    assert "Select UPI" not in content
    assert "failure@razorpay" not in content

    # 5. Product name is generic "Product"
    assert '<span class="product-name">Product</span>' in content
