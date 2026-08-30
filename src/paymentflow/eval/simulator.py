"""Policy-independent customer response simulator for recovery evaluation."""

import hashlib
import logging
import random

from paymentflow.domain.enums import RecoveryPolicy
from paymentflow.eval.models import EvaluationCase, SimulatedOutcome

logger = logging.getLogger(__name__)


class CustomerResponseSimulator:
    """Simulates customer response to recovery interventions in a policy-independent manner.

    IMPORTANT ARCHITECTURAL INVARIANT:
    The simulator does NOT know whether the intervention was chosen by:
    - Rule-based baseline
    - LLM agent
    - Human operator
    - Random/Ablation policy

    It evaluates the outcome solely based on the case characteristics, the applied policy,
    and the simulation ground truth.
    """

    @staticmethod
    def simulate(
        case: EvaluationCase,
        policy: RecoveryPolicy | str,
        seed: int | None = None,
    ) -> SimulatedOutcome:
        """Simulate customer response to a specified recovery policy.

        Args:
            case: The EvaluationCase containing decision context and ground truth.
            policy: The RecoveryPolicy applied (e.g. P_CREATE_LINK_IMMEDIATE).
            seed: Optional integer seed for deterministic, reproducible random draws.

        Returns:
            SimulatedOutcome with recovery status, recovered amount, and probability.
        """
        # 1. Parse and validate policy
        if isinstance(policy, str):
            try:
                validated_policy = RecoveryPolicy(policy)
            except ValueError:
                allowed = [p.value for p in RecoveryPolicy]
                raise ValueError(f"Invalid recovery policy '{policy}'. Must be one of {allowed}.")
        elif isinstance(policy, RecoveryPolicy):
            validated_policy = policy
        else:
            raise ValueError(f"Expected RecoveryPolicy or str, got {type(policy).__name__}")

        # 2. Extract ground-truth recovery probability for the applied intervention
        gt = case.ground_truth
        match validated_policy:
            case RecoveryPolicy.P_NO_ACTION:
                prob = gt.p_recovery_no_action
                estimated_time_s = 7200 if prob > 0 else None
            case RecoveryPolicy.P_CREATE_LINK_IMMEDIATE:
                prob = gt.p_recovery_immediate_link
                estimated_time_s = 300 if prob > 0 else None
            case RecoveryPolicy.P_CREATE_LINK_DELAYED:
                prob = gt.p_recovery_delayed_link
                estimated_time_s = 5400 if prob > 0 else None
            case RecoveryPolicy.P_ESCALATE_ONLY:
                prob = gt.p_recovery_escalate
                estimated_time_s = 14400 if prob > 0 else None
            case _:
                raise ValueError(f"Unhandled policy: {validated_policy}")

        # 3. Deterministic pseudo-random draw using stable SHA-256 seed
        if seed is not None:
            seed_key = f"{case.decision_context.case_id}:{seed}".encode("utf-8")
            seed_int = int(hashlib.sha256(seed_key).hexdigest()[:16], 16)
            rng = random.Random(seed_int)
            draw = rng.random()
        else:
            draw = random.random()

        recovered = draw < prob
        recovered_amount = case.decision_context.amount if recovered else 0

        return SimulatedOutcome(
            case_id=case.decision_context.case_id,
            policy=validated_policy,
            recovered=recovered,
            recovered_amount=recovered_amount,
            recovery_probability=prob,
            time_to_recovery_seconds=estimated_time_s if recovered else None,
            seed=seed,
        )
