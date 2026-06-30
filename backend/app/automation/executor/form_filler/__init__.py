"""Universal external form filling (ATS adapters + generic filler)."""

from .filler import FillOutcome, fill_external_form

__all__ = ["fill_external_form", "FillOutcome"]
