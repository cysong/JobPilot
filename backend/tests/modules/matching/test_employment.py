"""Company blocklist for crowd / paid-per-task platforms."""
from app.modules.matching.employment import company_key, is_non_employment_company


def test_company_key():
    assert company_key("Joblet-AI Ltd.") == "joblet ai"
    assert company_key("  ALIGNERR  ") == "alignerr"


def test_blocklist_matches_names_and_prefixes():
    assert is_non_employment_company("Alignerr")
    assert is_non_employment_company(None, "crewlia")
    assert is_non_employment_company("TELUS Digital AI Data Solutions")
    assert not is_non_employment_company("TELUS Digital Philippines")
    assert not is_non_employment_company("Hiredly Recruitment")  # whole words only
    assert not is_non_employment_company(None, None)
