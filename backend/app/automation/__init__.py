"""JobPilot Autopilot - Automation engine for daily job discovery and application.

This package runs as a child process of the Tauri app, exposing a FastAPI
service on a local port. It handles:
  - LinkedIn job discovery via the Voyager API (fast, httpx-based)
  - Job matching/scoring against the user profile (Ollama)
  - Action queue management with user confirmation
  - Execution of approved actions (Playwright, only when needed)

See docs/AUTOPILOT_PLAN.md for the full architecture.
"""

__version__ = "0.1.0"
