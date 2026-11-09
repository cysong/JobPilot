"""Periodic tasks must expire before their next run so busy workers do not pile up copies."""
from app.core.celery_app import _DEFAULT_BEAT_SCHEDULE


def _min_interval_seconds(schedule) -> float:
    """Shortest gap between runs: a plain interval, or an every-hour crontab (minute field only)."""
    if isinstance(schedule, (int, float)):
        return schedule
    minutes = sorted(schedule.minute)
    gaps = [b - a for a, b in zip(minutes, minutes[1:])] + [minutes[0] + 60 - minutes[-1]]
    return min(gaps) * 60


def test_every_periodic_task_expires_before_its_next_run():
    for name, entry in _DEFAULT_BEAT_SCHEDULE.items():
        expires = entry.get("options", {}).get("expires")
        assert expires is not None, f"{name} has no expires"
        interval = _min_interval_seconds(entry["schedule"])
        assert 0 < expires < interval, f"{name}: expires {expires}s, runs every {interval}s"
