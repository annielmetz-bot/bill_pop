"""Shared column-type helpers."""

import enum

from sqlalchemy import Enum as SAEnum


def str_enum(enum_cls: type[enum.Enum]) -> SAEnum:
    """A VARCHAR-backed enum column.

    We deliberately avoid native Postgres ENUM types: the roadmap requires
    controlled vocabularies (modalities, payer types, NM codes) to grow through
    2026–2027 without painful ``ALTER TYPE`` migrations. Storing the enum's
    ``value`` as a string keeps validation in the app layer while leaving the
    schema flexible.
    """
    return SAEnum(
        enum_cls,
        native_enum=False,
        length=32,
        values_callable=lambda e: [member.value for member in e],
    )
