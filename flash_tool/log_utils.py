"""Helpers for keeping command output readable in the GUI."""

import re


# Covers CSI sequences (for example, SGR colour/style codes), OSC title
# sequences, and the remaining two-byte ESC commands emitted by terminals.
_ANSI_ESCAPE_RE = re.compile(
    r"\x1b(?:"
    r"\[[0-?]*[ -/]*[@-~]"
    r"|\][^\x07]*(?:\x07|\x1b\\)"
    r"|[@-_]"
    r")"
)


def strip_ansi(text: str) -> str:
    """Remove terminal escape sequences while preserving readable text."""
    return _ANSI_ESCAPE_RE.sub("", text)
