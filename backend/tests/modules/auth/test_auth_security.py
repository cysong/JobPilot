import os

import pytest
from pydantic import ValidationError

os.environ["DEBUG"] = "false"

from app.modules.auth.models import SecurityTokenType
from app.modules.auth.schemas import SalaryExpectation, UserPreferences
from app.modules.auth.token_service import SecurityTokenRateLimitError, hash_security_token
from app.core.response_codes import ResponseCode
from app.shared.enums import TailoringLevel


def test_hash_security_token_is_deterministic():
    token = "plain-token"

    first_hash = hash_security_token(token)
    second_hash = hash_security_token(token)

    assert first_hash == second_hash
    assert first_hash != token
    assert len(first_hash) == 64


def test_salary_expectation_exact_requires_value():
    with pytest.raises(ValidationError, match="salary_expectation.value is required when mode is exact"):
        SalaryExpectation(mode="exact")


def test_salary_expectation_range_requires_min_and_max():
    with pytest.raises(ValidationError, match="salary_expectation.min and max are required when mode is range"):
        SalaryExpectation(mode="range", min=100000)


def test_salary_expectation_range_rejects_inverted_bounds():
    with pytest.raises(ValidationError, match="salary_expectation.max must be greater than or equal to min"):
        SalaryExpectation(mode="range", min=150000, max=120000)


def test_user_preferences_defaults_are_safe():
    preferences = UserPreferences()

    assert preferences.default_tailoring_level is None
    assert preferences.job_locations == []
    assert preferences.salary_expectation is None


def test_user_preferences_accept_moderate_tailoring_level():
    preferences = UserPreferences(default_tailoring_level="moderate")

    assert preferences.default_tailoring_level == TailoringLevel.MODERATE


def test_security_token_type_values_remain_stable():
    assert SecurityTokenType.EMAIL_VERIFY.value == "EMAIL_VERIFY"
    assert SecurityTokenType.PASSWORD_RESET.value == "PASSWORD_RESET"
    assert SecurityTokenType.EMAIL_CHANGE.value == "EMAIL_CHANGE"


def test_security_token_rate_limit_error_uses_consistent_429_code():
    error = SecurityTokenRateLimitError()

    assert error.status_code == 429
    assert error.response_code == ResponseCode.TOO_MANY_REQUESTS
