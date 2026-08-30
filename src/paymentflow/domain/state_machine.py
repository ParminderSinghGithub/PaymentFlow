"""Deterministic state machine for Recovery Cases."""

import logging
from typing import ClassVar

from paymentflow.domain.enums import CaseState
from paymentflow.domain.exceptions import InvalidStateTransitionError

logger = logging.getLogger(__name__)


class RecoveryStateMachine:
    """Enforces deterministic state transitions for recovery cases."""

    # Explicit allowed transition graph
    _TRANSITIONS: ClassVar[dict[CaseState, set[CaseState]]] = {
        CaseState.FAILED_INGESTED: {
            CaseState.CONTEXT_RETRIEVED,
            CaseState.ERROR_TERMINAL,
        },
        CaseState.CONTEXT_RETRIEVED: {
            CaseState.ELIGIBILITY_CHECKED,
            CaseState.ERROR_TERMINAL,
        },
        CaseState.ELIGIBILITY_CHECKED: {
            CaseState.AI_TRIAGED,
            CaseState.TERMINAL_NO_ACTION,
            CaseState.ESCALATED,
            CaseState.ERROR_TERMINAL,
        },
        CaseState.AI_TRIAGED: {
            CaseState.POLICY_VALIDATED,
            CaseState.ERROR_TERMINAL,
        },
        CaseState.POLICY_VALIDATED: {
            CaseState.ACTION_APPROVED,
            CaseState.TERMINAL_NO_ACTION,
            CaseState.ESCALATED,
            CaseState.ERROR_TERMINAL,
        },
        CaseState.ACTION_APPROVED: {
            CaseState.ACTION_EXECUTED,
            CaseState.TERMINAL_NO_ACTION,
            CaseState.ESCALATED,
            CaseState.ERROR_TERMINAL,
        },
        CaseState.ACTION_EXECUTED: {
            CaseState.AWAITING_PAYMENT,
            CaseState.ERROR_TERMINAL,
        },
        CaseState.AWAITING_PAYMENT: {
            CaseState.VERIFICATION,
            CaseState.EXPIRED,
            CaseState.ERROR_TERMINAL,
        },
        CaseState.VERIFICATION: {
            CaseState.RECOVERED,
            CaseState.EXPIRED,
            CaseState.ESCALATED,
            CaseState.ERROR_TERMINAL,
        },
        # Terminal states: no further transitions allowed
        CaseState.RECOVERED: set(),
        CaseState.EXPIRED: set(),
        CaseState.ESCALATED: set(),
        CaseState.TERMINAL_NO_ACTION: set(),
        CaseState.ERROR_TERMINAL: set(),
    }

    _TERMINAL_STATES: ClassVar[set[CaseState]] = {
        CaseState.RECOVERED,
        CaseState.EXPIRED,
        CaseState.ESCALATED,
        CaseState.TERMINAL_NO_ACTION,
        CaseState.ERROR_TERMINAL,
    }

    @classmethod
    def is_terminal(cls, state: CaseState) -> bool:
        """Return True if state is terminal."""
        return state in cls._TERMINAL_STATES

    @classmethod
    def can_transition(cls, from_state: CaseState, to_state: CaseState) -> bool:
        """Check if transition from from_state to to_state is allowed."""
        allowed = cls._TRANSITIONS.get(from_state, set())
        return to_state in allowed

    @classmethod
    def transition(cls, current_state: CaseState, target_state: CaseState) -> CaseState:
        """Validate and execute state transition. Raises InvalidStateTransitionError if illegal."""
        if cls.is_terminal(current_state):
            raise InvalidStateTransitionError(
                current_state.value,
                target_state.value,
                reason=f"Current state '{current_state.value}' is terminal and cannot be modified.",
            )

        if not cls.can_transition(current_state, target_state):
            reason = (
                f"Transition from '{current_state.value}' to '{target_state.value}' "
                "is not permitted in recovery workflow."
            )
            raise InvalidStateTransitionError(
                current_state.value,
                target_state.value,
                reason=reason,
            )

        logger.info(f"State transition approved: {current_state.value} -> {target_state.value}")
        return target_state
