"""Suite-wide fixtures."""
import pytest


@pytest.fixture(autouse=True)
def _no_llm_availability_state(request, monkeypatch):
    """Keep LLM pause / circuit-breaker state (Redis) out of unit tests unless a test
    opts in with ``@pytest.mark.real_availability``."""
    if request.node.get_closest_marker("real_availability"):
        return
    from app.core.llm import availability

    monkeypatch.setattr(availability, "blocking_pause", lambda model: None)
    monkeypatch.setattr(availability, "global_pause", lambda: None)
    monkeypatch.setattr(availability, "active_pauses", lambda: {})
    monkeypatch.setattr(availability, "record_success", lambda: None)
    monkeypatch.setattr(availability, "record_outage_failure", lambda reason, source: None)
