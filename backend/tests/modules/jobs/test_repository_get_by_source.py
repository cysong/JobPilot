"""Surface contract for JobRepository.get_by_source_and_source_id.

The router/service layer relies on this method to resolve an internal
job_id from (source, source_id) when the AWS enqueue API reports
already_in_db. The signature must remain stable.
"""
from __future__ import annotations

import inspect

from app.modules.jobs.repository import JobRepository


def test_get_by_source_and_source_id_signature():
    fn = JobRepository.get_by_source_and_source_id
    sig = inspect.signature(fn)
    params = list(sig.parameters)
    # First arg is `db` (AsyncSession), then source, then source_id.
    assert params == ["db", "source", "source_id"], params
