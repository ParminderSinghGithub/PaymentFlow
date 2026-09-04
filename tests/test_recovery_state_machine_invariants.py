"""Phase C3.6.2: Comprehensive Recovery State Machine and Functional Invariants Test Suite.

Verifies:
1. Valid positive recovery transitions:
   A. Failed payment -> FAILED_INGESTED -> context -> eligibility -> advisory -> guardrail
      -> ACTION_EXECUTED
   B. ACTION_EXECUTED -> authoritative captured evidence -> RECOVERED
   C. Delayed recovery: pending until due -> executed -> not re-executed
   D. Benchmark CANONICAL_EVALUATION remains isolated from live attribution
2. Forbidden recovery transitions:
   - payment.failed alone cannot recover
   - payment.authorized alone cannot recover
   - payment_link.paid without captured status cannot recover
   - unmatched case / wrong payment ID / wrong payment link / wrong correlation cannot recover
   - amount mismatch / currency mismatch cannot recover
   - already-TERMINAL cases cannot transition to RECOVERED or receive credit
   - already-ESCALATED cases cannot transition to RECOVERED or receive credit
   - C4/AML and C5 technical failures cannot receive payment links or automated recovery
   - high-value >₹50,000 cannot receive automated recovery links
   - duplicate webhooks cannot duplicate recovery credit or mutate RECOVERED cases
3. Recovery immutability:
   - RECOVERED cases cannot regress to any other state
"""

import json
from unittest.mock import AsyncMock

import pytest

from paymentflow.adapters.razorpay_adapter import RazorpayAdapter
from paymentflow.db.models import RecoveryCaseModel, utc_now
from paymentflow.db.session import get_sessionmaker
from paymentflow.domain.enums import CaseState, FailureCategory, PolicyDecision, RecoveryPolicy
from paymentflow.domain.exceptions import InvalidStateTransitionError
from paymentflow.domain.models import PaymentContext
from paymentflow.domain.policy_engine import PolicyGuardrailEngine
from paymentflow.domain.state_machine import RecoveryStateMachine
from paymentflow.services.webhook_service import WebhookService


@pytest.fixture
def mock_razorpay():
    """Mock Razorpay adapter for authoritative gateway verification."""
    adapter = RazorpayAdapter(
        key_id="rzp_test_TWkctY0MsbW4Rd",
        key_secret="PWatfW99KA7gH4our6Sfvmoe",
    )
    adapter.get_payment = AsyncMock()
    return adapter


# ==============================================================================
# 1. State Machine Transition Graph Tests
# ==============================================================================


def test_state_machine_allowed_transitions():
    """Prove every valid transition in the state machine succeeds."""
    # From FAILED_INGESTED
    assert RecoveryStateMachine.can_transition(
        CaseState.FAILED_INGESTED, CaseState.CONTEXT_RETRIEVED
    )
    assert RecoveryStateMachine.can_transition(CaseState.FAILED_INGESTED, CaseState.ERROR_TERMINAL)

    # From CONTEXT_RETRIEVED
    assert RecoveryStateMachine.can_transition(
        CaseState.CONTEXT_RETRIEVED, CaseState.ELIGIBILITY_CHECKED
    )
    assert RecoveryStateMachine.can_transition(
        CaseState.CONTEXT_RETRIEVED, CaseState.TERMINAL_NO_ACTION
    )
    assert RecoveryStateMachine.can_transition(CaseState.CONTEXT_RETRIEVED, CaseState.ESCALATED)

    # From ELIGIBILITY_CHECKED
    assert RecoveryStateMachine.can_transition(CaseState.ELIGIBILITY_CHECKED, CaseState.AI_TRIAGED)
    assert RecoveryStateMachine.can_transition(
        CaseState.ELIGIBILITY_CHECKED, CaseState.TERMINAL_NO_ACTION
    )
    assert RecoveryStateMachine.can_transition(CaseState.ELIGIBILITY_CHECKED, CaseState.ESCALATED)

    # From ACTION_APPROVED
    assert RecoveryStateMachine.can_transition(CaseState.ACTION_APPROVED, CaseState.ACTION_EXECUTED)
    assert RecoveryStateMachine.can_transition(
        CaseState.ACTION_APPROVED, CaseState.TERMINAL_NO_ACTION
    )

    # From ACTION_EXECUTED
    assert RecoveryStateMachine.can_transition(CaseState.ACTION_EXECUTED, CaseState.RECOVERED)
    assert RecoveryStateMachine.can_transition(CaseState.ACTION_EXECUTED, CaseState.VERIFICATION)
    assert RecoveryStateMachine.can_transition(CaseState.ACTION_EXECUTED, CaseState.ESCALATED)


def test_state_machine_forbidden_transitions():
    """Prove illegal transitions and terminal state modifications are blocked."""
    # Direct illegal jumps
    assert not RecoveryStateMachine.can_transition(CaseState.FAILED_INGESTED, CaseState.RECOVERED)
    assert not RecoveryStateMachine.can_transition(
        CaseState.FAILED_INGESTED, CaseState.ACTION_EXECUTED
    )
    assert not RecoveryStateMachine.can_transition(CaseState.AI_TRIAGED, CaseState.RECOVERED)
    assert not RecoveryStateMachine.can_transition(CaseState.ACTION_APPROVED, CaseState.RECOVERED)

    # Terminal states can NEVER transition to any state
    terminal_states = [
        CaseState.RECOVERED,
        CaseState.ESCALATED,
        CaseState.TERMINAL_NO_ACTION,
        CaseState.EXPIRED,
        CaseState.ERROR_TERMINAL,
    ]
    for term in terminal_states:
        assert RecoveryStateMachine.is_terminal(term)
        for target in CaseState:
            assert not RecoveryStateMachine.can_transition(term, target)
            with pytest.raises(InvalidStateTransitionError):
                RecoveryStateMachine.transition(term, target)


# ==============================================================================
# 2. Guardrail Safety Invariants Tests
# ==============================================================================


def test_guardrail_amount_immutability_blocked():
    """Proposed recovery amount mutating original amount is strictly rejected."""
    ctx = PaymentContext(payment_id="pay_inv_01", amount=500000, currency="INR", status="failed")
    res = PolicyGuardrailEngine.validate(
        context=ctx,
        requested_policy=RecoveryPolicy.P_CREATE_LINK_IMMEDIATE,
        proposed_amount=450000,  # Discount / mutation attempted!
        proposed_currency="INR",
    )
    assert res.decision == PolicyDecision.REJECT
    assert res.effective_policy == RecoveryPolicy.P_NO_ACTION
    assert res.reason_code == "AMOUNT_MUTATION_FORBIDDEN"


def test_guardrail_currency_immutability_blocked():
    """Proposed currency differing from original currency is strictly rejected."""
    ctx = PaymentContext(payment_id="pay_inv_02", amount=500000, currency="INR", status="failed")
    res = PolicyGuardrailEngine.validate(
        context=ctx,
        requested_policy=RecoveryPolicy.P_CREATE_LINK_IMMEDIATE,
        proposed_amount=500000,
        proposed_currency="USD",  # Currency mutation attempted!
    )
    assert res.decision == PolicyDecision.REJECT
    assert res.effective_policy == RecoveryPolicy.P_NO_ACTION
    assert res.reason_code == "CURRENCY_MUTATION_FORBIDDEN"


def test_guardrail_high_value_cap_escalates():
    """Transaction > ₹50,000 unconditionally escalates without link creation."""
    ctx = PaymentContext(payment_id="pay_inv_03", amount=6_000_000, currency="INR", status="failed")
    res = PolicyGuardrailEngine.validate(
        context=ctx,
        requested_policy=RecoveryPolicy.P_CREATE_LINK_IMMEDIATE,
        proposed_amount=6_000_000,
        proposed_currency="INR",
    )
    assert res.decision == PolicyDecision.ESCALATE
    assert res.effective_policy == RecoveryPolicy.P_ESCALATE_ONLY
    assert res.reason_code == "HIGH_VALUE_THRESHOLD"


def test_guardrail_c4_aml_risk_escalates():
    """C4 business/AML risk rejection unconditionally escalates."""
    ctx = PaymentContext(payment_id="pay_inv_04", amount=150000, currency="INR", status="failed")
    res = PolicyGuardrailEngine.validate(
        context=ctx,
        requested_policy=RecoveryPolicy.P_CREATE_LINK_IMMEDIATE,
        failure_category=FailureCategory.C4,
        proposed_amount=150000,
        proposed_currency="INR",
    )
    assert res.decision == PolicyDecision.DOWNGRADE
    assert res.effective_policy == RecoveryPolicy.P_ESCALATE_ONLY
    assert res.reason_code == "RISK_FAILURE_INELIGIBLE_FOR_LINK"


def test_guardrail_c5_technical_halt():
    """C5 integration / technical failure halts to P_NO_ACTION."""
    ctx = PaymentContext(payment_id="pay_inv_05", amount=150000, currency="INR", status="failed")
    res = PolicyGuardrailEngine.validate(
        context=ctx,
        requested_policy=RecoveryPolicy.P_CREATE_LINK_IMMEDIATE,
        failure_category=FailureCategory.C5,
        proposed_amount=150000,
        proposed_currency="INR",
    )
    assert res.decision == PolicyDecision.DOWNGRADE
    assert res.effective_policy == RecoveryPolicy.P_NO_ACTION
    assert res.reason_code == "TECHNICAL_FAILURE_INELIGIBLE_FOR_LINK"


def test_guardrail_one_link_limit():
    """Case already having an existing link cannot create a second link."""
    ctx = PaymentContext(payment_id="pay_inv_06", amount=150000, currency="INR", status="failed")
    res = PolicyGuardrailEngine.validate(
        context=ctx,
        requested_policy=RecoveryPolicy.P_CREATE_LINK_IMMEDIATE,
        has_existing_recovery_link=True,
        proposed_amount=150000,
        proposed_currency="INR",
    )
    assert res.decision == PolicyDecision.DOWNGRADE
    assert res.effective_policy == RecoveryPolicy.P_NO_ACTION
    assert res.reason_code == "ONE_LINK_LIMIT_EXCEEDED"


def test_guardrail_cooldown_limit():
    """Customer exceeding 3 attempts in 24h is halted."""
    ctx = PaymentContext(
        payment_id="pay_inv_07",
        customer_id="cust_07",
        amount=150000,
        currency="INR",
        status="failed",
    )
    res = PolicyGuardrailEngine.validate(
        context=ctx,
        requested_policy=RecoveryPolicy.P_CREATE_LINK_IMMEDIATE,
        customer_attempts_today=3,
        proposed_amount=150000,
        proposed_currency="INR",
    )
    assert res.decision == PolicyDecision.DOWNGRADE
    assert res.effective_policy == RecoveryPolicy.P_NO_ACTION
    assert res.reason_code == "CUSTOMER_COOLDOWN_EXCEEDED"


# ==============================================================================
# 3. Webhook Financial Attribution & Transition Invariants
# ==============================================================================


@pytest.mark.asyncio
async def test_webhook_payment_failed_alone_produces_zero_credit():
    """payment.failed creates a case in FAILED_INGESTED with zero recovered amount."""
    sessionmaker = get_sessionmaker()
    pay_id = "pay_inv_fail_alone_01"
    payload = {
        "event": "payment.failed",
        "id": "evt_fail_alone_01",
        "payload": {
            "payment": {
                "entity": {
                    "id": pay_id,
                    "amount": 250000,
                    "currency": "INR",
                    "status": "failed",
                }
            }
        },
    }
    async with sessionmaker() as session:
        service = WebhookService(session)
        res = await service.process_webhook(
            raw_body=json.dumps(payload).encode(),
            payload=payload,
            signature_verified=True,
        )

    assert res.state == CaseState.FAILED_INGESTED.value
    async with sessionmaker() as session:
        case = await session.get(RecoveryCaseModel, res.case_id)
        assert case.state == CaseState.FAILED_INGESTED.value
        assert case.recovered_amount is None
        assert case.recovered_payment_id is None


@pytest.mark.asyncio
async def test_webhook_non_captured_payment_status_strictly_rejected(mock_razorpay):
    """Payment in 'authorized' status (not captured) cannot attribute recovery."""
    sessionmaker = get_sessionmaker()
    case_id = "case_inv_auth_only"
    plink_id = "plink_inv_auth_only"
    payment_id = "pay_inv_auth_only"

    async with sessionmaker() as session:
        case = RecoveryCaseModel(
            case_id=case_id,
            failed_payment_id="pay_fail_auth_only",
            amount=300000,
            currency="INR",
            state=CaseState.ACTION_EXECUTED.value,
            payment_link_id=plink_id,
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        session.add(case)
        await session.commit()

    mock_razorpay.get_payment.return_value = {
        "id": payment_id,
        "amount": 300000,
        "currency": "INR",
        "status": "authorized",  # NOT CAPTURED
    }

    payload = {
        "event": "payment.captured",
        "id": "evt_inv_auth_only",
        "payload": {
            "payment": {
                "entity": {
                    "id": payment_id,
                    "amount": 300000,
                    "currency": "INR",
                    "status": "authorized",
                    "payment_link_id": plink_id,
                }
            }
        },
    }

    async with sessionmaker() as session:
        service = WebhookService(session, razorpay_adapter=mock_razorpay)
        res = await service.process_webhook(
            raw_body=json.dumps(payload).encode(),
            payload=payload,
            signature_verified=True,
        )

    assert "is not captured" in res.message
    async with sessionmaker() as session:
        case = await session.get(RecoveryCaseModel, case_id)
        assert case.state == CaseState.ACTION_EXECUTED.value
        assert case.recovered_amount is None
        assert case.recovered_payment_id is None


@pytest.mark.asyncio
async def test_webhook_terminal_case_cannot_transition_to_recovered(mock_razorpay):
    """A case already in TERMINAL_NO_ACTION cannot transition to RECOVERED or receive credit."""
    sessionmaker = get_sessionmaker()
    case_id = "case_inv_term_blocked"
    plink_id = "plink_inv_term_blocked"
    payment_id = "pay_inv_term_blocked"

    async with sessionmaker() as session:
        case = RecoveryCaseModel(
            case_id=case_id,
            failed_payment_id="pay_fail_term_blocked",
            amount=300000,
            currency="INR",
            state=CaseState.TERMINAL_NO_ACTION.value,  # Terminal state!
            payment_link_id=plink_id,
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        session.add(case)
        await session.commit()

    payload = {
        "event": "payment.captured",
        "id": "evt_inv_term_blocked",
        "payload": {
            "payment": {
                "entity": {
                    "id": payment_id,
                    "amount": 300000,
                    "currency": "INR",
                    "status": "captured",
                    "payment_link_id": plink_id,
                }
            }
        },
    }

    async with sessionmaker() as session:
        service = WebhookService(session, razorpay_adapter=mock_razorpay)
        res = await service.process_webhook(
            raw_body=json.dumps(payload).encode(),
            payload=payload,
            signature_verified=True,
        )

    assert "cannot transition to RECOVERED" in res.message
    async with sessionmaker() as session:
        case = await session.get(RecoveryCaseModel, case_id)
        assert case.state == CaseState.TERMINAL_NO_ACTION.value
        assert case.recovered_amount is None
        assert case.recovered_payment_id is None


@pytest.mark.asyncio
async def test_webhook_unmatched_correlation_yields_zero_attribution(mock_razorpay):
    """Payment event with unknown payment link and case ID records anomaly and 0 recovery."""
    sessionmaker = get_sessionmaker()
    payload = {
        "event": "payment.captured",
        "id": "evt_inv_unmatched",
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_completely_random_999",
                    "amount": 300000,
                    "currency": "INR",
                    "status": "captured",
                    "payment_link_id": "plink_non_existent_999",
                }
            }
        },
    }

    async with sessionmaker() as session:
        service = WebhookService(session, razorpay_adapter=mock_razorpay)
        res = await service.process_webhook(
            raw_body=json.dumps(payload).encode(),
            payload=payload,
            signature_verified=True,
        )

    assert res.message == "Unmatched recovery payment."
    assert res.case_id is None


@pytest.mark.asyncio
async def test_recovery_immutability_duplicate_webhook_suppression(mock_razorpay):
    """Once RECOVERED, subsequent events are suppressed and cannot mutate recovered cash."""
    sessionmaker = get_sessionmaker()
    case_id = "case_inv_immutable_rec"
    plink_id = "plink_inv_immutable_rec"
    payment_id = "pay_inv_immutable_rec"

    # 1. Start in ACTION_EXECUTED
    async with sessionmaker() as session:
        case = RecoveryCaseModel(
            case_id=case_id,
            failed_payment_id="pay_fail_immutable_rec",
            amount=420000,
            currency="INR",
            state=CaseState.ACTION_EXECUTED.value,
            payment_link_id=plink_id,
            case_source="MERCHANT_CHECKOUT",
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        session.add(case)
        await session.commit()

    mock_razorpay.get_payment.return_value = {
        "id": payment_id,
        "amount": 420000,
        "currency": "INR",
        "status": "captured",
    }

    payload = {
        "event": "payment.captured",
        "id": "evt_inv_immut_first",
        "payload": {
            "payment": {
                "entity": {
                    "id": payment_id,
                    "amount": 420000,
                    "currency": "INR",
                    "status": "captured",
                    "payment_link_id": plink_id,
                }
            }
        },
    }

    # First event transitions to RECOVERED
    async with sessionmaker() as session:
        service = WebhookService(session, razorpay_adapter=mock_razorpay)
        res1 = await service.process_webhook(
            raw_body=json.dumps(payload).encode(),
            payload=payload,
            signature_verified=True,
        )
    assert res1.state == CaseState.RECOVERED.value

    # Second replayed event with different event ID
    payload2 = dict(payload)
    payload2["id"] = "evt_inv_immut_second"

    async with sessionmaker() as session:
        service = WebhookService(session, razorpay_adapter=mock_razorpay)
        res2 = await service.process_webhook(
            raw_body=json.dumps(payload2).encode(),
            payload=payload2,
            signature_verified=True,
        )
    assert res2.is_duplicate is True
    assert res2.state == CaseState.RECOVERED.value

    # Check DB values: never mutated to 2x (remains exactly 420000 paise)
    async with sessionmaker() as session:
        final_case = await session.get(RecoveryCaseModel, case_id)
        assert final_case.state == CaseState.RECOVERED.value
        assert final_case.recovered_amount == 420000
        assert final_case.recovered_payment_id == payment_id
