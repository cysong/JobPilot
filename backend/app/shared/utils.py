"""Shared utility helpers."""
import uuid


def generate_id(prefix: str) -> str:
    """Generate a prefixed identifier."""
    return f"{prefix}_{uuid.uuid4().hex}"
