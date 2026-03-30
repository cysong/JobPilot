import os

import pytest
from pydantic import ValidationError

os.environ["DEBUG"] = "false"

from app.modules.users.schemas import ProfilePreferencesUpdate


def test_profile_preferences_normalize_locations_and_tailoring_level():
    payload = ProfilePreferencesUpdate(
        default_tailoring_level=" MODERATE ",
        job_locations=[" auckland ", "Wellington", "Auckland"],
    )

    assert payload.default_tailoring_level == "moderate"
    assert payload.job_locations == ["Auckland", "Wellington"]


def test_profile_preferences_reject_unsupported_location():
    with pytest.raises(ValidationError, match="Unsupported job location: Sydney"):
        ProfilePreferencesUpdate(job_locations=["Sydney"])
