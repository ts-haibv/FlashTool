---
title: "Focused scroll and UI polish review"
status: done-with-concerns
created: 2026-08-04
---

# Focused scroll and UI polish review

## Summary

Spec compliance passes. The focused-wheel manager is isolated to UI event
routing, nested boundary behavior is covered, and the existing staged ROM
detection/ROM-type changes remain untouched.

## Findings

- `WheelScrollManager` registers only the sidebar, image list, and flash-step list.
- Pointer-over-list events are left to CustomTkinter; focused-list events use the
  remembered target, and boundary events bubble through registered parents.
- Root bindings are removed by their own Tk callback IDs, avoiding removal of
  unrelated global callbacks.
- `theme.py` now owns interaction colors, scrollbar hover color, radii, and
  status symbols consumed by the main window, steps, console, and dialogs.
- `ui/__init__.py` keeps `ask_yes_no` compatible while avoiding eager desktop
  toolkit import during display-free utility tests.

## Verification

- `python -m unittest discover -s tests -v` → 14 tests, 0 failures.
- `python -m py_compile ...` for all touched Python files → exit 0.
- `git diff --check` → exit 0.
- Consumer scan confirms `WheelScrollManager` has one runtime owner and the
  lazy dialog export has one existing caller (`main_window.py`).

## Risks / unresolved questions

- No GUI smoke test was possible because no display server is available. UI
  modules import successfully against temporary `customtkinter` 6.0.0, and the
  code uses the documented/current `CTkScrollableFrame._parent_canvas` and
  `_scrollbar` internals; behavior is covered with display-free fakes.
