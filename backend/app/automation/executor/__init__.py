"""Action execution layer (Playwright-based, visible browser)."""

from .applicator import ExecutionResult, execute_application
from .field_mapping import detect_ats, value_for_field

__all__ = ["execute_application", "ExecutionResult", "detect_ats", "value_for_field"]
