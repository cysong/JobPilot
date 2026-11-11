"""API key scopes.

A key without scopes works on every endpoint that accepts API keys (the
default). Scopes only *open* endpoints that otherwise demand a browser session:
an admin endpoint guarded by ``require_admin_scope`` accepts an API key when the
key's owner is an admin and the key carries that scope.
"""
from __future__ import annotations

MATCHING_LABELS = "matching:labels"

# scope -> human description; only admins may grant these.
ADMIN_SCOPES: dict[str, str] = {
    MATCHING_LABELS: "Submit match calibration labels (/admin/matching/labels)",
}
