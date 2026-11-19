"""Compatibility import: every route uses the same database dependency."""

from .database import get_db

__all__ = ["get_db"]
