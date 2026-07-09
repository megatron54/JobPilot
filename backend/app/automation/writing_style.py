"""Writing-style rules for generated application content.

Distilled from the writing-style guide in ai-job-search (MIT). Provides reusable
prompt fragments that enforce a warm-but-direct, cliche-free, forward-looking
style grounded in real experience.
"""

from __future__ import annotations

# Hard rules injected into every content-generation system prompt.
STYLE_RULES = (
    "WRITING STYLE (strict):\n"
    "- No em-dashes. Use commas or periods.\n"
    "- No cliches or filler: avoid 'passionate about', 'great fit', 'leverage my "
    "skills', 'hit the ground running', 'drive results', 'synergies', 'team player'.\n"
    "- No generic buzzwords without a concrete example backing them.\n"
    "- No apologetic or overly humble language. Not 'I think I could' but "
    "'I bring X, shown by Y'.\n"
    "- First person, active voice. Demonstrate, do not state.\n"
    "- Forward-looking: focus on the tasks you can solve for THIS employer, not a "
    "CV recap. Use 1-2 brief past examples only to back forward-looking claims.\n"
    "- Never claim experience the candidate does not have. Reframe emphasis, not "
    "substance.\n"
)

# Cliches to detect in the reviewer pass.
CLICHES = (
    "passionate about", "great fit", "leverage my skills", "hit the ground running",
    "drive results", "synergies", "team player", "think outside the box",
    "self-starter", "results-oriented", "detail-oriented",
)


def contains_cliches(text: str) -> list[str]:
    """Return any style cliches found in the text (for the reviewer pass/tests)."""
    low = text.lower()
    return [c for c in CLICHES if c in low]


def has_em_dash(text: str) -> bool:
    return "\u2014" in text or "--" in text
