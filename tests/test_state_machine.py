"""Tests for recovery case state machine."""

import pytest

from paymentflow.domain.enums import CaseState
from paymentflow.domain.exceptions import InvalidStateTransitionError
from paymentflow.domain.state_machine import RecoveryStateMachine


def test_valid_state_transitions_flow():
    """Verify standard happy-path state transitions."""
    state = CaseState.FAILED_INGESTED
    state = RecoveryStateMachine.transition(state, CaseState.CONTEXT_RETRIEVED)
    assert state == CaseState.CONTEXT_RETRIEVED

    state = RecoveryStateMachine.transition(state, CaseState.ELIGIBILITY_CHECKED)
    assert state == CaseState.ELIGIBILITY_CHECKED

    state = RecoveryStateMachine.transition(state, CaseState.AI_TRIAGED)
    assert state == CaseState.AI_TRIAGED

    state = RecoveryStateMachine.transition(state, CaseState.POLICY_VALIDATED)
    assert state == CaseState.POLICY_VALIDATED

    state = RecoveryStateMachine.transition(state, CaseState.ACTION_APPROVED)
    assert state == CaseState.ACTION_APPROVED

    state = RecoveryStateMachine.transition(state, CaseState.ACTION_EXECUTED)
    assert state == CaseState.ACTION_EXECUTED

    state = RecoveryStateMachine.transition(state, CaseState.AWAITING_PAYMENT)
    assert state == CaseState.AWAITING_PAYMENT

    state = RecoveryStateMachine.transition(state, CaseState.VERIFICATION)
    assert state == CaseState.VERIFICATION

    state = RecoveryStateMachine.transition(state, CaseState.RECOVERED)
    assert state == CaseState.RECOVERED


def test_valid_alternative_terminal_transitions():
    """Verify alternative terminal branches from intermediate states."""
    # Ineligible path
    assert (
        RecoveryStateMachine.transition(CaseState.ELIGIBILITY_CHECKED, CaseState.TERMINAL_NO_ACTION)
        == CaseState.TERMINAL_NO_ACTION
    )
    assert (
        RecoveryStateMachine.transition(CaseState.ELIGIBILITY_CHECKED, CaseState.ESCALATED)
        == CaseState.ESCALATED
    )

    # Verification expiry or escalation
    assert (
        RecoveryStateMachine.transition(CaseState.VERIFICATION, CaseState.EXPIRED)
        == CaseState.EXPIRED
    )
    assert (
        RecoveryStateMachine.transition(CaseState.VERIFICATION, CaseState.ESCALATED)
        == CaseState.ESCALATED
    )

    # Error terminal from any intermediate state
    assert (
        RecoveryStateMachine.transition(CaseState.FAILED_INGESTED, CaseState.ERROR_TERMINAL)
        == CaseState.ERROR_TERMINAL
    )


def test_illegal_state_transitions_rejected():
    """Verify illegal jumps across states are rejected with InvalidStateTransitionError."""
    # Cannot jump directly from FAILED_INGESTED to ACTION_EXECUTED
    with pytest.raises(InvalidStateTransitionError) as exc_info:
        RecoveryStateMachine.transition(CaseState.FAILED_INGESTED, CaseState.ACTION_EXECUTED)
    assert "Invalid state transition" in str(exc_info.value)

    # Cannot jump from AI_TRIAGED to RECOVERED
    with pytest.raises(InvalidStateTransitionError):
        RecoveryStateMachine.transition(CaseState.AI_TRIAGED, CaseState.RECOVERED)

    # Cannot jump from ACTION_APPROVED to RECOVERED
    with pytest.raises(InvalidStateTransitionError):
        RecoveryStateMachine.transition(CaseState.ACTION_APPROVED, CaseState.RECOVERED)


def test_terminal_states_cannot_transition():
    """Verify terminal states can never transition to any other state."""
    terminal_states = [
        CaseState.RECOVERED,
        CaseState.EXPIRED,
        CaseState.ESCALATED,
        CaseState.TERMINAL_NO_ACTION,
        CaseState.ERROR_TERMINAL,
    ]

    for term in terminal_states:
        assert RecoveryStateMachine.is_terminal(term) is True
        for target in CaseState:
            with pytest.raises(InvalidStateTransitionError):
                RecoveryStateMachine.transition(term, target)
