"""Focused mouse-wheel routing for nested CustomTkinter scroll areas."""

from __future__ import annotations

from collections.abc import Iterable
from tkinter import TclError
from typing import Any


def normalize_wheel_units(delta: int | float = 0, event_num: int | None = None) -> int:
    """Convert Tk wheel input into canvas ``yview_scroll`` units.

    Tk reports wheel movement as ``delta`` on Windows/macOS and as button
    numbers 4/5 on X11. Positive movement always means scroll up here.
    """
    if event_num == 4:
        return -1
    if event_num == 5:
        return 1
    if not delta:
        return 0
    if abs(delta) >= 120:
        return -int(delta / 120)
    return -1 if delta > 0 else 1


class WheelScrollManager:
    """Route focused-list wheel events without changing list implementations."""

    _WHEEL_EVENTS = ("<MouseWheel>", "<Button-4>", "<Button-5>")
    _TARGET_EVENTS = ("<Button-1>", "<Enter>", "<FocusIn>")

    def __init__(self, root: Any):
        self.root = root
        self._scrollables: list[Any] = []
        self._active: Any | None = None
        self._bound_sequences = (*self._WHEEL_EVENTS, *self._TARGET_EVENTS)
        self._binding_ids: dict[str, str] = {}

        for sequence in self._bound_sequences:
            callback = self._on_wheel if sequence in self._WHEEL_EVENTS else self._remember_target
            self._binding_ids[sequence] = root.bind_all(sequence, callback, add="+")

    def register(self, scrollable: Any) -> None:
        """Register a scrollable frame, preserving registration order."""
        if scrollable not in self._scrollables:
            self._scrollables.append(scrollable)

    def unregister(self, scrollable: Any) -> None:
        """Stop tracking a scrollable frame."""
        if scrollable in self._scrollables:
            self._scrollables.remove(scrollable)
        if self._active is scrollable:
            self._active = None

    def destroy(self) -> None:
        """Remove the manager's root bindings before the root is destroyed."""
        for sequence, binding_id in self._binding_ids.items():
            try:
                self.root._unbind(("bind", "all", sequence), binding_id)
            except (AttributeError, TclError):
                # The root may already be tearing down; Tcl will remove the
                # binding with the interpreter and there is nothing to clean.
                pass
        self._binding_ids.clear()
        self._scrollables.clear()
        self._active = None

    def _remember_target(self, event: Any) -> None:
        target = self._target_for_widget(getattr(event, "widget", None))
        if target is not None:
            self._active = target

    def _on_wheel(self, event: Any) -> str | None:
        units = normalize_wheel_units(
            getattr(event, "delta", 0),
            getattr(event, "num", None),
        )
        if not units:
            return None

        pointer_target = self._target_for_widget(getattr(event, "widget", None))
        target = pointer_target or self._active
        if target is None:
            return None

        # CustomTkinter already handles the common pointer-over-list case. We
        # only take over there when the inner frame is at a boundary, allowing
        # the movement to bubble to its registered parent.
        if pointer_target is not None and self._can_scroll(target, units):
            return None

        if self.scroll(target, units):
            return "break"
        return None

    def scroll(self, target: Any, units: int) -> bool:
        """Scroll ``target`` or a registered ancestor that can move."""
        for candidate in self._target_chain(target):
            if self._scroll_one(candidate, units):
                return True
        return False

    def _target_chain(self, target: Any) -> Iterable[Any]:
        """Yield target followed by registered scrollable ancestors."""
        yield target
        current = getattr(target, "master", None)
        seen = {id(target)}
        while current is not None:
            for candidate in reversed(self._scrollables):
                if candidate is current and id(candidate) not in seen:
                    seen.add(id(candidate))
                    yield candidate
            current = getattr(current, "master", None)

    @staticmethod
    def _canvas_for(scrollable: Any) -> Any | None:
        return getattr(scrollable, "_parent_canvas", None)

    def _can_scroll(self, scrollable: Any, units: int) -> bool:
        canvas = self._canvas_for(scrollable)
        if canvas is None:
            return False
        try:
            first, last = canvas.yview()
        except (AttributeError, TypeError, TclError):
            return False
        if units < 0:
            return first > 0.0
        return last < 1.0

    def _scroll_one(self, scrollable: Any, units: int) -> bool:
        if not self._can_scroll(scrollable, units):
            return False
        canvas = self._canvas_for(scrollable)
        canvas.yview_scroll(units, "units")
        return True

    def _target_for_widget(self, widget: Any) -> Any | None:
        matches = [target for target in self._scrollables if self._belongs_to(widget, target)]
        if not matches:
            return None
        return max(matches, key=self._widget_depth)

    @classmethod
    def _belongs_to(cls, widget: Any, target: Any) -> bool:
        if widget is None:
            return False
        canvas = cls._canvas_for(target)
        if widget is target or widget is canvas or widget is getattr(target, "_scrollbar", None):
            return True

        current = widget
        for _ in range(64):
            if current is target:
                return True
            current = getattr(current, "master", None)
            if current is None:
                return False
        return False

    @staticmethod
    def _widget_depth(widget: Any) -> int:
        depth = 0
        current = widget
        while current is not None and depth < 64:
            depth += 1
            current = getattr(current, "master", None)
        return depth
