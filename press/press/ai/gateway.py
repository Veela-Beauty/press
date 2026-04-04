"""AI gateway — single entry point for all AI requests.

Orchestrates: scope guard -> branch check -> budget check -> reserve ->
              provider call -> lint response -> reconcile -> return result.

The _call_provider function is the only external dependency (mocked in tests).
"""

from dataclasses import dataclass, field

from press.press.ai.linter import LintResult, lint_response
from press.press.ai.site_scope_guard import check_scope, check_branch
from press.press.ai.token_budget import BudgetEngine

# Module-level budget engine (singleton for the process)
_budget_engine: BudgetEngine | None = None


def get_budget_engine() -> BudgetEngine:
    global _budget_engine
    if _budget_engine is None:
        _budget_engine = BudgetEngine()
    return _budget_engine


def reset_budget_engine():
    """Reset for testing — creates a fresh engine."""
    global _budget_engine
    _budget_engine = BudgetEngine()


@dataclass
class GatewayResult:
    success: bool
    response_text: str = ""
    lint_result: LintResult | None = None
    error: str = ""
    tokens_used: int = 0
    cost_estimate: float = 0.0
    needs_confirm: bool = False  # Staging site — requires explicit confirm


# Default token estimate for budget reservation
DEFAULT_ESTIMATED_TOKENS = 4000


def process_ai_request(
    user: str,
    project: str,
    site_type: str,
    branch: str,
    prompt: str,
    provider: str,
    api_key: str | None,
    company_key: str | None = None,
    estimated_tokens: int = DEFAULT_ESTIMATED_TOKENS,
    context: dict | None = None,
) -> GatewayResult:
    """Process a single AI request through the full pipeline.

    Steps:
    1. Check site scope (dev/staging/prod)
    2. Check branch (dev-* only)
    3. Validate API key exists
    4. Check token budget
    5. Reserve tokens
    6. Call provider
    7. Lint response
    8. Reconcile usage
    9. Return result
    """
    # 1. Site scope guard
    scope = check_scope(site_type, "write_file")
    if not scope.allowed:
        return GatewayResult(success=False, error=scope.message)

    # 2. Branch guard
    branch_check = check_branch(branch)
    if not branch_check.allowed:
        return GatewayResult(success=False, error=branch_check.message)

    # 3. API key check
    resolved_key = api_key or company_key
    if not resolved_key or not resolved_key.strip():
        return GatewayResult(
            success=False,
            error="No API key configured. Please set a personal or company key in Settings.",
        )

    # 4. Budget check
    engine = get_budget_engine()
    budget = engine.check_budget(user, project, estimated_tokens)
    if not budget.allowed:
        return GatewayResult(
            success=False,
            error=f"Token budget exceeded. {budget.reason}",
        )

    # 5. Reserve tokens
    reservation = engine.reserve(user, project, estimated_tokens)

    try:
        # 6. Call provider
        raw_response = _call_provider(
            prompt=prompt,
            api_key=resolved_key,
            provider=provider,
            context=context,
        )

        # 7. Lint response
        lint_result = lint_response(raw_response["text"])

        # 8. Reconcile actual usage (replaces reservation with real count)
        input_tokens = raw_response.get("input_tokens", 0)
        output_tokens = raw_response.get("output_tokens", 0)
        actual_tokens = input_tokens + output_tokens
        engine.reconcile(reservation.reservation_id, actual_tokens)

        return GatewayResult(
            success=True,
            response_text=lint_result.sanitized_text,
            lint_result=lint_result,
            tokens_used=actual_tokens,
            needs_confirm=scope.needs_confirm,
        )

    except Exception as e:
        # Cancel reservation on failure
        engine.cancel_reservation(reservation.reservation_id)
        return GatewayResult(success=False, error=f"Provider error: {str(e)}")


def _call_provider(prompt: str, api_key: str, provider: str,
                   context: dict | None = None) -> dict:
    """Call the LLM provider. This is the only function that makes external calls.

    Returns: {"text": str, "input_tokens": int, "output_tokens": int, "model": str}

    In production this routes through LiteLLM. In tests it's mocked.
    """
    raise NotImplementedError(
        "Provider calls require LiteLLM. Install with: pip install litellm"
    )
