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


def test_profile_preferences_matching_conditions():
    payload = ProfilePreferencesUpdate(
        work_rights="work_visa", security_clearance="not_eligible", country="  New Zealand ",
        languages=[" English ", "chinese", "English", "  "],
    )
    assert payload.country == "New Zealand"
    assert payload.languages == ["English", "chinese"]
    with pytest.raises(ValidationError):
        ProfilePreferencesUpdate(work_rights="tourist")
    assert ProfilePreferencesUpdate(country="  ").country is None


@pytest.mark.asyncio
async def test_update_profile_preferences_merges_and_keeps_unsent_keys():
    from unittest.mock import AsyncMock, MagicMock

    from app.modules.users.service import update_profile_preferences

    user = MagicMock()
    user.preferences = {"job_locations": ["Auckland"], "work_rights": "work_visa", "languages": ["English"]}
    db = MagicMock()
    db.get = AsyncMock(return_value=user)
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    result_proxy = MagicMock()
    result_proxy.scalars.return_value.all.return_value = [{"work_right": "Open work visa"}]
    db.execute = AsyncMock(return_value=result_proxy)

    # An older client that only knows the original three fields.
    result = await update_profile_preferences(
        db, 1, ProfilePreferencesUpdate(job_locations=["Wellington"], default_tailoring_level="deep"))
    assert result == {"job_locations": ["Wellington"], "default_tailoring_level": "deep",
                      "work_rights": "work_visa", "languages": ["English"],
                      "work_right_hint": "Open work visa"}
    # The hint is derived on read, never persisted.
    assert "work_right_hint" not in user.preferences

    # Explicit null clears a value.
    result = await update_profile_preferences(db, 1, ProfilePreferencesUpdate(work_rights=None))
    assert "work_rights" in result and result["work_rights"] is None


@pytest.mark.asyncio
async def test_get_profile_preferences_adds_work_right_hint():
    from unittest.mock import AsyncMock, MagicMock

    from app.modules.users.service import get_profile_preferences

    user = MagicMock()
    user.preferences = {"work_rights": "work_visa"}
    result_proxy = MagicMock()
    result_proxy.scalars.return_value.all.return_value = [{}, {"work_right": " Open work visa "}]
    db = MagicMock()
    db.get = AsyncMock(return_value=user)
    db.execute = AsyncMock(return_value=result_proxy)

    result = await get_profile_preferences(db, 1)
    assert result == {"work_rights": "work_visa", "work_right_hint": "Open work visa"}
    assert user.preferences == {"work_rights": "work_visa"}  # stored preferences untouched
