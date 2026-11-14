"""Name ordering that does not depend on the server's operating-system locale.

PostgreSQL's default collation comes from the C library of the machine that
created the database (`en_US.utf8` on `nba`). Another machine, or another glibc
version, can sort the same names differently, and a page of a list would then
hold different rows (DATABASE_AUDIT_2026-11-10, R-07). On PostgreSQL names are
compared with ICU's root collation (`und-x-icu`), which every ICU-enabled server
provides whatever its OS locale; accented names stay next to their unaccented
neighbours, unlike byte order (`"C"`), which puts "Álex" after "Zydrunas". Other
databases keep their default, which in SQLite is already a fixed byte order.
"""

from __future__ import annotations

from sqlalchemy.orm import InstrumentedAttribute, Session
from sqlalchemy.sql.elements import ColumnElement

NAME_COLLATION = "und-x-icu"


def portable_name_order(
    session: Session, column: InstrumentedAttribute[str] | ColumnElement[str]
) -> InstrumentedAttribute[str] | ColumnElement[str]:
    """`column` compared under a locale-independent collation, for ORDER BY."""
    if session.get_bind().dialect.name == "postgresql":
        return column.collate(NAME_COLLATION)
    return column
