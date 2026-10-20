"""The shipped ticket-triage pipeline, as it runs at both centres."""

from .apply import decide, score, standardise

__all__ = ("decide", "score", "standardise")
