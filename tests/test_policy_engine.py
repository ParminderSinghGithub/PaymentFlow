"""Deterministic unit tests for PolicyGuardrailEngine before LLM integration."""

from paymentflow.domain.enums import (
    FailureCategory,
    PolicyDecision,
    RecoveryPolicy,
    TemplateId,
)
from paymentflow.domain.models import (
    PaymentContext,
    PaymentFailureDetails,
    RecoveryProposal,
)
from paymentflow.domain.policy_engine import PolicyGuardrailEngine


def make_context(
    amount: int = 250000,
    currency: str = "INR",
    status: str = "failed",
    customer_id: str | None = "cust_01",
) -> PaymentContext:
    """Construct standard valid payment context."""
    return PaymentContext(
        payment_id="pay_guardrail_01",
        amount=amount,
        currency=currency,
        status=status,
        customer_id=customer_id,
        failure=PaymentFailureDetails(code="PAYMENT_AUTHENTICATION_ERROR"),
    )


def test_guardrail_approve_immediate_link():
    """Verify standard valid immediate recovery link proposal is approved."""
    ctx = make_context(amount=250000)
    proposal = RecoveryProposal(
        failure_category=FailureCategory.C1,
        policy_id=RecoveryPolicy.P_CREATE_LINK_IMMEDIATE,
        template_id=TemplateId.TPL_RECOVERY_STANDARD,
        explanation="Customer OTP expired; sending immediate payment link.",
    )
    result = PolicyGuardrailEngine.validate(context=ctx, proposal=proposal)
    assert result.decision == PolicyDecision.APPROVE
    assert result.effective_policy == RecoveryPolicy.P_CREATE_LINK_IMMEDIATE
    assert result.is_approved is True


def test_guardrail_approve_delayed_link():
    """Verify delayed link policy for soft infrastructure (C2) is approved."""
    ctx = make_context(amount=250000)
    proposal = RecoveryProposal(
        failure_category=FailureCategory.C2,
        policy_id=RecoveryPolicy.P_CREATE_LINK_DELAYED,
        template_id=TemplateId.TPL_RECOVERY_STANDARD,
        explanation="Bank gateway timeout; schedule delayed recovery link.",
    )
    result = PolicyGuardrailEngine.validate(context=ctx, proposal=proposal)
    assert result.decision == PolicyDecision.APPROVE
    assert result.effective_policy == RecoveryPolicy.P_CREATE_LINK_DELAYED
    assert result.is_approved is True


def test_guardrail_amount_mutation_rejected():
    """Verify proposed amount differing from verified original amount is rejected."""
    ctx = make_context(amount=250000)
    result = PolicyGuardrailEngine.validate(
        context=ctx,
        requested_policy=RecoveryPolicy.P_CREATE_LINK_IMMEDIATE,
        proposed_amount=100000,  # Attacker/hallucinated amount mutation
    )
    assert result.decision == PolicyDecision.REJECT
    assert result.effective_policy == RecoveryPolicy.P_NO_ACTION
    assert result.reason_code == "AMOUNT_MUTATION_FORBIDDEN"
    assert result.is_approved is False


def test_guardrail_currency_mutation_rejected():
    """Verify proposed currency differing from original is rejected."""
    ctx = make_context(amount=250000, currency="INR")
    result = PolicyGuardrailEngine.validate(
        context=ctx,
        requested_policy=RecoveryPolicy.P_CREATE_LINK_IMMEDIATE,
        proposed_currency="USD",
    )
    assert result.decision == PolicyDecision.REJECT
    assert result.effective_policy == RecoveryPolicy.P_NO_ACTION
    assert result.reason_code == "CURRENCY_MUTATION_FORBIDDEN"


def test_guardrail_high_value_escalation():
    """Verify amount > ₹50,000 requesting link is deterministically escalated."""
    ctx = make_context(amount=60_000_00)  # ₹60,000
    proposal = RecoveryProposal(
        failure_category=FailureCategory.C1,
        policy_id=RecoveryPolicy.P_CREATE_LINK_IMMEDIATE,
        template_id=TemplateId.TPL_RECOVERY_STANDARD,
        explanation="Recover high value payment.",
    )
    result = PolicyGuardrailEngine.validate(context=ctx, proposal=proposal)
    assert result.decision == PolicyDecision.ESCALATE
    assert result.effective_policy == RecoveryPolicy.P_ESCALATE_ONLY
    assert result.reason_code == "HIGH_VALUE_THRESHOLD"


def test_guardrail_one_link_limit():
    """Verify case with existing recovery link is downgraded to P_NO_ACTION."""
    ctx = make_context()
    result = PolicyGuardrailEngine.validate(
        context=ctx,
        requested_policy=RecoveryPolicy.P_CREATE_LINK_IMMEDIATE,
        has_existing_recovery_link=True,
    )
    assert result.decision == PolicyDecision.DOWNGRADE
    assert result.effective_policy == RecoveryPolicy.P_NO_ACTION
    assert result.reason_code == "ONE_LINK_LIMIT_EXCEEDED"


def test_guardrail_customer_cooldown():
    """Verify customer reaching 3 daily attempts is downgraded to P_NO_ACTION."""
    ctx = make_context(customer_id="cust_cooldown_01")
    result = PolicyGuardrailEngine.validate(
        context=ctx,
        requested_policy=RecoveryPolicy.P_CREATE_LINK_IMMEDIATE,
        customer_attempts_today=3,
    )
    assert result.decision == PolicyDecision.DOWNGRADE
    assert result.effective_policy == RecoveryPolicy.P_NO_ACTION
    assert result.reason_code == "CUSTOMER_COOLDOWN_EXCEEDED"


def test_guardrail_c4_risk_downgrades_to_escalate():
    """Verify C4 (Risk) failure requesting link is downgraded to P_ESCALATE_ONLY."""
    ctx = make_context()
    proposal = RecoveryProposal(
        failure_category=FailureCategory.C4,
        policy_id=RecoveryPolicy.P_CREATE_LINK_IMMEDIATE,
        template_id=TemplateId.TPL_RECOVERY_STANDARD,
        explanation="Attempt recovery on risk failure.",
    )
    result = PolicyGuardrailEngine.validate(context=ctx, proposal=proposal)
    assert result.decision == PolicyDecision.DOWNGRADE
    assert result.effective_policy == RecoveryPolicy.P_ESCALATE_ONLY
    assert result.reason_code == "RISK_FAILURE_INELIGIBLE_FOR_LINK"


def test_guardrail_c5_technical_downgrades_to_no_action():
    """Verify C5 (Technical) failure requesting link is downgraded to P_NO_ACTION."""
    ctx = make_context()
    proposal = RecoveryProposal(
        failure_category=FailureCategory.C5,
        policy_id=RecoveryPolicy.P_CREATE_LINK_IMMEDIATE,
        template_id=TemplateId.TPL_RECOVERY_STANDARD,
        explanation="Attempt recovery on integration error.",
    )
    result = PolicyGuardrailEngine.validate(context=ctx, proposal=proposal)
    assert result.decision == PolicyDecision.DOWNGRADE
    assert result.effective_policy == RecoveryPolicy.P_NO_ACTION
    assert result.reason_code == "TECHNICAL_FAILURE_INELIGIBLE_FOR_LINK"


def test_guardrail_invalid_policy_id_rejected():
    """Verify unknown policy string is rejected."""
    ctx = make_context()
    result = PolicyGuardrailEngine.validate(
        context=ctx,
        requested_policy="P_ARBITRARY_ACTION_HACK",
    )
    assert result.decision == PolicyDecision.REJECT
    assert result.effective_policy == RecoveryPolicy.P_NO_ACTION
    assert result.reason_code == "INVALID_POLICY_ID"
