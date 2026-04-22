"""Project-wide SQLAlchemy column helpers.

Centralises the conventions enforced across all models so individual
modules do not need to remember every keyword argument.
"""
from __future__ import annotations

from enum import Enum

from sqlalchemy import Enum as SQLEnum


def EnumColumn(enum_cls: type[Enum], *, name: str) -> SQLEnum:
    """Project-standard SQLAlchemy enum column type.

    Forces:
      * native PostgreSQL ENUM (not VARCHAR + CHECK)
      * values_callable so the DB stores the enum *value* (not the
        Python member name). Without this kwarg SQLAlchemy silently
        stores the member name, which historically diverged from the
        value and broke Pydantic deserialisation.

    The convention is that every enum used at the storage layer has
    name == value in UPPER_SNAKE_CASE, but values_callable is still
    set explicitly to keep new enums safe by default.
    """
    return SQLEnum(
        enum_cls,
        name=name,
        native_enum=True,
        values_callable=lambda c: [item.value for item in c],
        validate_strings=True,
    )
