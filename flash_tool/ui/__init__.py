"""UI components for FlashTool.

Dialog imports stay lazy so display-free utility tests can import UI helpers
without requiring the optional desktop toolkit at collection time.
"""


def ask_yes_no(parent, title: str, message: str) -> bool:
    """Show the themed confirmation dialog and return the user's choice."""
    from flash_tool.ui.confirm_dialog import ask_yes_no as _ask_yes_no

    return _ask_yes_no(parent, title, message)


def __getattr__(name: str):
    """Resolve dialog classes only when a caller explicitly requests them."""
    if name == "ConfirmDialog":
        from flash_tool.ui.confirm_dialog import ConfirmDialog

        return ConfirmDialog
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["ConfirmDialog", "ask_yes_no"]
