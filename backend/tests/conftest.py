"""Suite-wide fixtures."""
import pytest


@pytest.fixture(autouse=True)
def _no_llm_quota_pause(request, monkeypatch):
    """Keep the LLM quota pause flag (Redis) out of unit tests unless a test opts in
    with ``@pytest.mark.real_quota``."""
    if request.node.get_closest_marker("real_quota"):
        return
    from app.core.llm import quota

    monkeypatch.setattr(quota, "pause_state", lambda: None)
