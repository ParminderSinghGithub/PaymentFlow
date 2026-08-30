"""LLM adapter for advisory recovery reasoning and structured output enforcement."""

import json
import logging
import time
from typing import Any

import httpx
from pydantic import ValidationError

from paymentflow.config import Settings, get_settings
from paymentflow.domain.enums import (
    FailureCategory,
    RecoveryPolicy,
    TemplateId,
)
from paymentflow.domain.models import PaymentContext, RecoveryProposal

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are the Razorpay PaymentFlow Recovery Agent.
Your task is to analyze sanitized payment failure details and advise on the recovery strategy.

Allowed Failure Categories:
- C1: Customer-action / transient customer failure (OTP expired, card declined).
- C2: Soft infrastructure / gateway / network timeout.
- C3: Hard payment instrument failure (e.g. expired card, blocked instrument).
- C4: Business rule / risk / limit rejection.
- C5: Technical / integration / non-recoverable failure.

Allowed Policy IDs:
- P_CREATE_LINK_IMMEDIATE: Send an immediate recovery Payment Link to the customer.
- P_CREATE_LINK_DELAYED: Schedule a delayed recovery link after gateway stabilization.
- P_ESCALATE_ONLY: Escalate to merchant operations without customer communication.
- P_NO_ACTION: Take no automated recovery action.

Allowed Template IDs:
- TPL_RECOVERY_STANDARD
- TPL_RECOVERY_URGENT
- TPL_RECOVERY_DISCOUNT
- TPL_ESCALATION_INTERNAL
- TPL_NONE

Respond ONLY with a valid JSON object strictly matching this schema:
{
  "failure_category": "C1" | "C2" | "C3" | "C4" | "C5",
  "policy_id": "P_CREATE_LINK_IMMEDIATE" | "P_CREATE_LINK_DELAYED" |
               "P_ESCALATE_ONLY" | "P_NO_ACTION",
  "template_id": "TPL_RECOVERY_STANDARD" | "TPL_RECOVERY_URGENT" |
                 "TPL_RECOVERY_DISCOUNT" | "TPL_ESCALATION_INTERNAL" | "TPL_NONE",
  "explanation": "Concise reasoning for the triage decision"
}
"""


class LLMClient:
    """Async client for LLM-based advisory recovery planning."""

    def __init__(
        self,
        settings: Settings | None = None,
        timeout: float = 10.0,
        http_client: httpx.AsyncClient | None = None,
    ):
        self.settings = settings or get_settings()
        self.timeout = timeout
        self._external_client = http_client

    def _build_user_prompt(self, context: PaymentContext) -> str:
        """Construct sanitized context for LLM reasoning without secrets or unnecessary PII."""
        failure_dict = {
            "error_code": context.failure.code,
            "error_description": context.failure.description,
            "error_source": context.failure.source,
            "error_step": context.failure.step,
            "error_reason": context.failure.reason,
        }
        sanitized_context = {
            "payment_id": context.payment_id,
            "amount_inr": f"₹{context.amount / 100:.2f}",
            "currency": context.currency,
            "payment_method": context.method,
            "failure_details": failure_dict,
        }
        return (
            "Analyze this payment failure and recommend a recovery policy:\n"
            f"{json.dumps(sanitized_context, indent=2)}"
        )

    def _fallback_proposal(self, reason: str) -> RecoveryProposal:
        """Deterministic safe fallback recommendation when LLM is unavailable or fails."""
        logger.warning(f"Using deterministic fallback proposal due to: {reason}")
        return RecoveryProposal(
            failure_category=FailureCategory.C5,
            policy_id=RecoveryPolicy.P_NO_ACTION,
            template_id=TemplateId.TPL_NONE,
            explanation=f"Deterministic fallback applied due to model error: {reason}",
        )

    async def generate_proposal(
        self,
        context: PaymentContext,
    ) -> tuple[RecoveryProposal, dict[str, Any]]:
        """Generate structured recovery proposal with latency tracking and safe fallbacks."""
        start_time = time.perf_counter()
        metadata: dict[str, Any] = {
            "model": self.settings.llm_model,
            "latency_ms": 0.0,
            "is_fallback": False,
            "error": None,
        }

        # If API key is placeholder / not configured, return fallback directly
        if not self.settings.llm_api_key or "placeholder" in self.settings.llm_api_key:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            metadata["latency_ms"] = elapsed_ms
            metadata["is_fallback"] = True
            metadata["error"] = "LLM API key not configured or placeholder."
            return self._fallback_proposal("API key not configured"), metadata

        client = self._external_client or httpx.AsyncClient(timeout=self.timeout)
        should_close = self._external_client is None

        user_prompt = self._build_user_prompt(context)

        try:
            # Using Google Gemini REST endpoint format
            url = (
                f"https://generativelanguage.googleapis.com/v1beta/models/"
                f"{self.settings.llm_model}:generateContent?key={self.settings.llm_api_key}"
            )
            payload = {
                "contents": [
                    {
                        "role": "user",
                        "parts": [
                            {"text": SYSTEM_PROMPT},
                            {"text": user_prompt},
                        ],
                    }
                ],
                "generationConfig": {
                    "response_mime_type": "application/json",
                    "temperature": 0.0,
                },
            }

            response = await client.post(url, json=payload)
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            metadata["latency_ms"] = elapsed_ms

            if response.status_code != 200:
                metadata["is_fallback"] = True
                metadata["error"] = f"LLM HTTP Error {response.status_code}: {response.text}"
                return (
                    self._fallback_proposal(f"Provider returned status {response.status_code}"),
                    metadata,
                )

            res_json = response.json()
            raw_text = (
                res_json.get("candidates", [{}])[0]
                .get("content", {})
                .get("parts", [{}])[0]
                .get("text", "")
            )

            proposal_dict = json.loads(raw_text)
            proposal = RecoveryProposal.model_validate(proposal_dict)
            return proposal, metadata

        except (httpx.TimeoutException, httpx.RequestError) as net_err:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            metadata["latency_ms"] = elapsed_ms
            metadata["is_fallback"] = True
            metadata["error"] = f"Network/Timeout error: {net_err}"
            return self._fallback_proposal("Network timeout or connection failure"), metadata

        except (json.JSONDecodeError, ValidationError) as parse_err:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            metadata["latency_ms"] = elapsed_ms
            metadata["is_fallback"] = True
            metadata["error"] = f"JSON/Schema validation error: {parse_err}"
            return self._fallback_proposal("Malformed JSON or invalid schema from LLM"), metadata

        finally:
            if should_close:
                await client.aclose()
