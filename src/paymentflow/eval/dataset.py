"""Dataset loading and validation service for synthetic recovery evaluation."""

import json
import logging
from pathlib import Path

from paymentflow.domain.enums import FailureCategory
from paymentflow.eval.models import EvaluationCase

logger = logging.getLogger(__name__)

DEFAULT_DATASET_PATH = Path(__file__).resolve().parent / "data" / "evaluation_cases.json"


def load_evaluation_dataset(dataset_path: Path | str | None = None) -> list[EvaluationCase]:
    """Load and validate the 75-case synthetic evaluation dataset.

    Args:
        dataset_path: Optional path to the JSON dataset file. Defaults to bundled dataset.

    Returns:
        List of 75 validated EvaluationCase objects.

    Raises:
        ValueError: If the dataset fails validation or cannot be parsed.
        FileNotFoundError: If the dataset file does not exist.
    """
    path = Path(dataset_path) if dataset_path else DEFAULT_DATASET_PATH
    if not path.exists():
        raise FileNotFoundError(f"Evaluation dataset not found at path: {path}")

    with open(path, "r", encoding="utf-8") as f:
        try:
            raw_data = json.load(f)
        except Exception as exc:
            raise ValueError(f"Failed to parse evaluation dataset JSON: {exc}")

    if not isinstance(raw_data, list):
        raise ValueError(f"Dataset root must be a JSON array, got {type(raw_data).__name__}")

    cases: list[EvaluationCase] = []
    for idx, item in enumerate(raw_data):
        if not isinstance(item, dict):
            raise ValueError(f"Dataset item at index {idx} must be a dictionary.")
        try:
            case = EvaluationCase.model_validate(item)
            cases.append(case)
        except Exception as exc:
            raise ValueError(f"Validation error in dataset case at index {idx}: {exc}")

    validate_dataset(cases)
    logger.info(f"Successfully loaded and validated {len(cases)} evaluation cases from {path.name}")
    return cases


def validate_dataset(cases: list[EvaluationCase]) -> None:
    """Perform rigorous structural and semantic validation on the evaluation dataset.

    Validates:
    - Exactly 75 cases.
    - Stable, unique case IDs.
    - Valid positive monetary amounts.
    - All 5 failure categories (C1-C5) represented.
    - All simulation probabilities in [0.0, 1.0].
    - Strict leakage prevention: DecisionContext does not leak SimulationGroundTruth.

    Raises:
        ValueError: If any validation invariant is violated.
    """
    # 1. Exact count
    if len(cases) != 75:
        raise ValueError(f"Dataset must contain exactly 75 cases, found {len(cases)}.")

    seen_ids: set[str] = set()
    categories_found: set[FailureCategory] = set()
    high_value_count = 0
    cooldown_count = 0
    non_inr_count = 0

    # Ground truth attribute names that must NEVER appear in DecisionContext
    forbidden_gt_fields = {
        "customer_intent_score",
        "p_recovery_no_action",
        "p_recovery_immediate_link",
        "p_recovery_delayed_link",
        "p_recovery_escalate",
        "notes",
    }

    for idx, case in enumerate(cases):
        dc = case.decision_context
        gt = case.ground_truth

        # 2. Case ID uniqueness
        if not dc.case_id or not isinstance(dc.case_id, str):
            raise ValueError(f"Case at index {idx} has missing or invalid case_id.")
        if dc.case_id in seen_ids:
            raise ValueError(f"Duplicate case_id '{dc.case_id}' detected at index {idx}.")
        seen_ids.add(dc.case_id)

        # 3. Monetary amount validity
        if dc.amount <= 0:
            raise ValueError(f"Case '{dc.case_id}' has non-positive amount {dc.amount}.")
        if dc.amount > 5000000:  # > ₹50,000
            high_value_count += 1

        # 4. Currency validity
        if dc.currency not in {"INR", "USD", "EUR"}:
            raise ValueError(f"Case '{dc.case_id}' has unexpected currency '{dc.currency}'.")
        if dc.currency != "INR":
            non_inr_count += 1

        # 5. Category presence
        categories_found.add(dc.failure_category)

        # 6. Cooldown
        if dc.last_attempt_at is not None:
            cooldown_count += 1

        # 7. Ground truth probability bounds
        probs = [
            ("p_recovery_no_action", gt.p_recovery_no_action),
            ("p_recovery_immediate_link", gt.p_recovery_immediate_link),
            ("p_recovery_delayed_link", gt.p_recovery_delayed_link),
            ("p_recovery_escalate", gt.p_recovery_escalate),
            ("customer_intent_score", gt.customer_intent_score),
        ]
        for name, p in probs:
            if not (0.0 <= p <= 1.0):
                raise ValueError(
                    f"Case '{dc.case_id}' probability '{name}'={p} is out of bounds [0.0, 1.0]."
                )

        # 8. Strict Data Leakage Invariant: Ensure DecisionContext has no GT fields
        dc_dict = dc.model_dump()
        leaked_fields = forbidden_gt_fields.intersection(dc_dict.keys())
        if leaked_fields:
            raise ValueError(
                f"Data Leakage Violation: DecisionContext for case '{dc.case_id}' "
                f"contains ground truth fields: {leaked_fields}"
            )

    # 9. All 5 failure categories represented
    expected_categories = {
        FailureCategory.C1,
        FailureCategory.C2,
        FailureCategory.C3,
        FailureCategory.C4,
        FailureCategory.C5,
    }
    missing_categories = expected_categories - categories_found
    if missing_categories:
        raise ValueError(
            "Dataset is missing required failure categories: "
            f"{[c.value for c in missing_categories]}."
        )

    logger.debug(
        f"Validation passed: 75 cases, {len(categories_found)} categories, "
        f"{high_value_count} high-value, {cooldown_count} cooldown, {non_inr_count} non-INR."
    )
