"""Real LLM Decision Provider for PaymentFlow with telemetry and safety fallbacks."""

import json
import logging
import time
from typing import Any

import httpx
from pydantic import ValidationError

from paymentflow.config import Settings, get_settings
from paymentflow.domain.enums import RecoveryPolicy
from paymentflow.eval.agent_evaluator import AgentDecisionProvider
from paymentflow.eval.models import AgentDecision, DecisionContext

logger = logging.getLogger(__name__)

LLM_SYSTEM_PROMPT = """You are the Razorpay PaymentFlow Recovery Agent.
Your role is to analyze sanitized payment failure details and advise on recovery strategy.

ALLOWED FAILURE CATEGORIES:
- C1: Customer-action / transient issuer or network failure.
- C2: User friction / OTP dropoff / checkout timeout.
- C3: Hard payment instrument / card limit / insufficient funds failure.
- C4: Business rule / risk / fraud / AML limit rejection.
- C5: Technical integration / malformed request / non-recoverable error.

ALLOWED RECOVERY POLICIES:
- P_CREATE_LINK_IMMEDIATE: Send an immediate recovery Payment Link to the customer.
- P_CREATE_LINK_DELAYED: Schedule a delayed recovery link after gateway stabilization.
- P_ESCALATE_ONLY: Escalate to merchant operations without customer notification.
- P_NO_ACTION: Take no automated recovery action.

POLICY GUIDELINES:
- High-value payments (> ₹50,000 / 5,000,000 paise) MUST be recommended for P_ESCALATE_ONLY.
- Risk/AML rejections (C4) MUST be recommended for P_ESCALATE_ONLY.
- Technical failures (C5) MUST be recommended for P_NO_ACTION.
- Transient gateway outages (C1) and card balance issues (C3) benefit from P_CREATE_LINK_DELAYED.
- Soft friction/timeout drops (C2) benefit from P_CREATE_LINK_IMMEDIATE.

Respond ONLY with a valid JSON object strictly matching this schema:
{
  "case_id": "<string>",
  "failure_category": "C1" | "C2" | "C3" | "C4" | "C5",
  "proposed_policy_id": "P_CREATE_LINK_IMMEDIATE" | "P_CREATE_LINK_DELAYED" |
                       "P_ESCALATE_ONLY" | "P_NO_ACTION",
  "reasoning": "<concise explanation for the triage proposal>",
  "confidence_score": <float between 0.0 and 1.0>,
  "proposed_amount": <integer in paise, matching original amount>,
  "proposed_currency": "<string matching original currency, e.g. INR>"
}
"""


class LLMTelemetry:
    """Observability container tracking LLM invocations, token usage, latency, and errors."""

    def __init__(self) -> None:
        self.call_count: int = 0
        self.fallback_count: int = 0
        self.total_latency_ms: float = 0.0
        self.prompt_tokens: int = 0
        self.completion_tokens: int = 0
        self.total_tokens: int = 0
        self.errors: list[str] = []

    @property
    def avg_latency_ms(self) -> float:
        return self.total_latency_ms / self.call_count if self.call_count > 0 else 0.0

    def record_call(
        self,
        latency_ms: float,
        is_fallback: bool,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        error: str | None = None,
    ) -> None:
        self.call_count += 1
        self.total_latency_ms += latency_ms
        self.prompt_tokens += prompt_tokens
        self.completion_tokens += completion_tokens
        self.total_tokens += prompt_tokens + completion_tokens
        if is_fallback:
            self.fallback_count += 1
        if error:
            self.errors.append(error)

    def to_dict(self) -> dict[str, Any]:
        return {
            "call_count": self.call_count,
            "fallback_count": self.fallback_count,
            "avg_latency_ms": round(self.avg_latency_ms, 2),
            "total_latency_ms": round(self.total_latency_ms, 2),
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "error_count": len(self.errors),
            "last_error": self.errors[-1] if self.errors else None,
        }


class LLMAgentDecisionProvider(AgentDecisionProvider):
    """Real LLM-backed decision provider with structured output and ground-truth isolation."""

    def __init__(
        self,
        settings: Settings | None = None,
        api_key: str | None = None,
        model: str | None = None,
        provider_type: str | None = None,
        base_url: str | None = None,
        timeout: float | None = None,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.api_key = api_key or self.settings.llm_api_key
        self.model = model or self.settings.llm_model
        self.provider_type = provider_type or self.settings.llm_provider_type
        self.base_url = base_url or self.settings.llm_base_url
        self.timeout = timeout or self.settings.llm_timeout_seconds
        self._external_client = http_client
        self.telemetry = LLMTelemetry()

    def serialize_decision_context(self, context: DecisionContext) -> dict[str, Any]:
        """Serialize DecisionContext explicitly, ensuring zero ground-truth leakage."""
        return {
            "case_id": context.case_id,
            "failed_payment_id": context.failed_payment_id,
            "order_id": context.order_id,
            "customer_id": context.customer_id,
            "amount_paise": context.amount,
            "amount_inr": f"₹{context.amount / 100:.2f}",
            "currency": context.currency,
            "payment_method": context.payment_method,
            "failure_code": context.failure_code,
            "failure_description": context.failure_description,
            "failure_source": context.failure_source,
            "failure_step": context.failure_step,
            "failure_reason": context.failure_reason,
            "prior_failed_count_24h": context.prior_failed_count_24h,
            "has_prior_recovery_attempt": context.last_attempt_at is not None,
            "created_at_utc": context.created_at.isoformat() if context.created_at else None,
        }

    def _build_user_prompt(self, context: DecisionContext) -> str:
        """Construct sanitized JSON user prompt containing decision-visible features only."""
        serialized = self.serialize_decision_context(context)
        return (
            "Analyze the following payment failure context and propose a recovery decision:\n"
            f"{json.dumps(serialized, indent=2)}"
        )

    def _safe_fallback(self, context: DecisionContext, reason: str) -> AgentDecision:
        """Deterministic fail-closed fallback when LLM is unavailable or produces errors."""
        logger.warning(
            f"LLM Decision fallback applied for case '{context.case_id}': {reason}"
        )
        if context.amount > 5_000_000:
            fallback_policy = RecoveryPolicy.P_ESCALATE_ONLY
            fallback_reason = f"Deterministic fallback (high-value escalation): {reason}"
        else:
            fallback_policy = RecoveryPolicy.P_NO_ACTION
            fallback_reason = f"Deterministic fail-closed fallback: {reason}"

        return AgentDecision(
            case_id=context.case_id,
            failure_category=context.failure_category,
            proposed_policy_id=fallback_policy,
            reasoning=fallback_reason,
            confidence_score=0.0,
            proposed_amount=context.amount,
            proposed_currency=context.currency,
        )

    def decide(self, context: DecisionContext) -> AgentDecision:
        """Execute structured LLM inference to produce an AgentDecision."""
        start_time = time.perf_counter()

        # Check for placeholder / unconfigured credentials
        if not self.api_key or "placeholder" in self.api_key.lower():
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            err = "LLM API key not configured or placeholder."
            self.telemetry.record_call(elapsed_ms, is_fallback=True, error=err)
            return self._safe_fallback(context, err)

        client = self._external_client or httpx.Client(timeout=self.timeout)
        should_close = self._external_client is None

        user_prompt = self._build_user_prompt(context)

        try:
            if self.provider_type == "openai" or (self.base_url and "openai" in self.base_url):
                # OpenAI Compatible REST format
                url = self.base_url or "https://api.openai.com/v1/chat/completions"
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                }
                payload = {
                    "model": self.model,
                    "temperature": 0.0,
                    "response_format": {"type": "json_object"},
                    "messages": [
                        {"role": "system", "content": LLM_SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ],
                }
                response = client.post(url, headers=headers, json=payload)
                elapsed_ms = (time.perf_counter() - start_time) * 1000

                if response.status_code != 200:
                    err_msg = f"HTTP {response.status_code}: {response.text}"
                    self.telemetry.record_call(elapsed_ms, is_fallback=True, error=err_msg)
                    return self._safe_fallback(context, err_msg)

                res_json = response.json()
                usage = res_json.get("usage", {})
                p_tokens = usage.get("prompt_tokens", 0)
                c_tokens = usage.get("completion_tokens", 0)
                raw_text = res_json["choices"][0]["message"]["content"]
            else:
                # Google Gemini REST format
                base = self.base_url or "https://generativelanguage.googleapis.com/v1beta/models"
                url = f"{base}/{self.model}:generateContent?key={self.api_key}"
                payload = {
                    "contents": [
                        {
                            "role": "user",
                            "parts": [
                                {"text": LLM_SYSTEM_PROMPT},
                                {"text": user_prompt},
                            ],
                        }
                    ],
                    "generationConfig": {
                        "response_mime_type": "application/json",
                        "temperature": 0.0,
                    },
                }
                response = client.post(url, json=payload)
                elapsed_ms = (time.perf_counter() - start_time) * 1000

                if response.status_code != 200:
                    err_msg = f"HTTP {response.status_code}: {response.text}"
                    self.telemetry.record_call(elapsed_ms, is_fallback=True, error=err_msg)
                    return self._safe_fallback(context, err_msg)

                res_json = response.json()
                usage = res_json.get("usageMetadata", {})
                p_tokens = usage.get("promptTokenCount", 0)
                c_tokens = usage.get("candidatesTokenCount", 0)
                raw_text = (
                    res_json.get("candidates", [{}])[0]
                    .get("content", {})
                    .get("parts", [{}])[0]
                    .get("text", "")
                )

            # Parse and strictly validate JSON against AgentDecision schema
            decision_dict = json.loads(raw_text)

            # Ensure case_id matches
            decision_dict["case_id"] = context.case_id

            # If amount or currency not in output, populate from context
            if decision_dict.get("proposed_amount") is None:
                decision_dict["proposed_amount"] = context.amount
            if decision_dict.get("proposed_currency") is None:
                decision_dict["proposed_currency"] = context.currency

            decision = AgentDecision.model_validate(decision_dict)
            self.telemetry.record_call(
                elapsed_ms,
                is_fallback=False,
                prompt_tokens=p_tokens,
                completion_tokens=c_tokens,
            )
            return decision

        except httpx.TimeoutException as te:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            err_msg = f"TimeoutException: {te}"
            self.telemetry.record_call(elapsed_ms, is_fallback=True, error=err_msg)
            return self._safe_fallback(context, err_msg)

        except httpx.RequestError as re:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            err_msg = f"RequestError: {re}"
            self.telemetry.record_call(elapsed_ms, is_fallback=True, error=err_msg)
            return self._safe_fallback(context, err_msg)

        except (json.JSONDecodeError, ValidationError) as ve:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            err_msg = f"SchemaValidationError: {ve}"
            self.telemetry.record_call(elapsed_ms, is_fallback=True, error=err_msg)
            return self._safe_fallback(context, err_msg)

        finally:
            if should_close:
                client.close()
