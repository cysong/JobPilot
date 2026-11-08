"""Tests for the location hard filter. Cases use real seek_jobs location values."""
from __future__ import annotations

import pytest

from app.modules.matching.location import check_location, get_locations, is_remote
from app.modules.users.schemas import NZ_JOB_LOCATION_OPTIONS


def _check(city, label, prefs=("Christchurch",), work_types=None, title=None):
    return check_location(
        user_locations=prefs,
        location_city=city,
        location_label=label,
        work_types_label=work_types,
        title=title,
    )


def test_preference_options_all_have_location_aliases():
    assert set(NZ_JOB_LOCATION_OPTIONS) == set(get_locations().city_region)


def test_no_preference_is_not_applicable():
    assert _check("Auckland", "Auckland CBD, Auckland", prefs=()).status == "not_applicable"


@pytest.mark.parametrize(
    ("city", "label"),
    [
        ("Christchurch", "Christchurch, Canterbury, New Zealand"),
        ("Christchurch City", "Christchurch City, Canterbury, New Zealand"),
        # Seek often stores the region in location_city; the suburb comes first in the label.
        ("Canterbury", "Addington, Canterbury"),
        ("Canterbury", "Burnside, Canterbury"),
        ("Wellington or Christchurch", "Wellington or Christchurch, , New Zealand"),
        ("Christchurch or Wellington", "Christchurch or Wellington, , New Zealand"),
    ],
)
def test_matched(city, label):
    result = _check(city, label)
    assert result.status == "matched"
    assert "Christchurch" in result.job_cities


@pytest.mark.parametrize(
    ("city", "label"),
    [
        (None, "New Zealand"),
        (None, "Canterbury, New Zealand"),
        ("Canterbury", "Ashburton, Canterbury"),  # region known, town not a preference city
        ("Various locations", "Various locations, , New Zealand"),
        (None, None),
        ("", ""),
    ],
)
def test_unknown_is_never_rejected(city, label):
    assert _check(city, label).status == "unknown"


@pytest.mark.parametrize(
    ("city", "label"),
    [
        ("Auckland", "Auckland CBD, Auckland"),
        (None, "Auckland, New Zealand"),
        ("Wellington", "Hutt Central, Wellington"),
        ("Taupo", "Taupo, Waikato, New Zealand"),
        ("Invercargill", "Invercargill, Southland, New Zealand"),
        ("Hamilton", "Hamilton, Waikato, New Zealand"),
    ],
)
def test_rejected_when_city_is_known_and_not_preferred(city, label):
    assert _check(city, label).status == "rejected"


def test_hutt_counts_as_wellington_metro():
    assert _check("Wellington", "Hutt Central, Wellington", prefs=("Wellington",)).status == "matched"
    assert _check("Lower Hutt", "Lower Hutt, Wellington, New Zealand", prefs=("Wellington",)).status == "matched"


def test_macrons_and_apostrophes():
    assert _check("Palmerston North", "Palmerston North, Manawatū-Whanganui Region, New Zealand",
                  prefs=("Palmerston North",)).status == "matched"
    assert _check("Napier", "Napier, Hawke's Bay, New Zealand", prefs=("Napier-Hastings",)).status == "matched"
    assert _check("Hawkes Bay", "Hastings Central, Hawkes Bay", prefs=("Napier-Hastings",)).status == "matched"


def test_any_of_several_preferences_matches():
    assert _check("Auckland", "Auckland CBD, Auckland", prefs=("Christchurch", "Auckland")).status == "matched"


def test_remote_jobs_pass_even_when_city_differs():
    assert _check("Auckland", "Auckland CBD, Auckland", work_types="Full time, Remote").status == "remote"
    assert _check("Auckland", "Auckland", title="Software Engineer (Remote)").status == "remote"


@pytest.mark.parametrize(
    ("title", "label", "work_types", "expected"),
    [
        ("Software Engineer (Remote)", None, None, True),
        ("Software Engineer (Fully Remote, NZ)", None, None, True),
        ("Software Engineer - Remote", None, None, True),
        ("Remote - Data Engineer", None, None, True),
        ("Software Engineer | Remote", None, None, True),
        ("Remote Monitoring Engineer", None, None, False),
        ("Remote Sensing Analyst", None, None, False),
        ("Software Engineer", "Work from home", None, True),
        ("Software Engineer", None, "Contract/Temp, Remote", True),
        ("Software Engineer", "Auckland", "Full time", False),
    ],
)
def test_is_remote(title, label, work_types, expected):
    assert is_remote(title=title, location_label=label, work_types_label=work_types) is expected
