---
phase: 1
title: "Scroll behavior and visual consistency"
status: completed
priority: P2
dependencies: []
---

# Phase 1: Scroll behavior and visual consistency

## Overview

Implement focused mouse-wheel routing for the sidebar, image selector list, and
flash-step list. In the same UI boundary, consolidate colors and spacing for the
main window, step cards, and console so the controls read as one product.

## Requirements

- Functional: remember the nearest scrollable frame on click/focus; normalize
  wheel input across supported desktop platforms; scroll nested parents only at
  an inner frame boundary; unregister global bindings on window destruction.
- Non-functional: no new dependency; no flash/profile logic changes; keep the
  UI responsive and compatible with CustomTkinter 5.2+.
- Visual: use semantic theme tokens, consistent card borders/radii, readable
  hierarchy, and text/symbol controls that do not depend on emoji rendering.

## Architecture

Add a small UI-only `WheelScrollManager` in `flash_tool/ui/scrolling.py`.
It owns the root-level event bindings and receives the registered
`CTkScrollableFrame` instances from `MainWindow`. Native CustomTkinter handling
continues to serve pointer-over-list scrolling; the manager handles the
focused-list case and boundary bubbling without changing list contents.

Update `theme.py` with semantic hover/border/radius tokens and consume them from
`main_window.py`, `step_widget.py`, and `log_panel.py`. Keep profile selection,
step generation, worker callbacks, and command construction untouched.

## Related Code Files

- Create: `flash_tool/ui/scrolling.py`
- Create: `tests/test_scrolling.py`
- Modify: `flash_tool/ui/main_window.py`
- Modify: `flash_tool/ui/theme.py`
- Modify: `flash_tool/ui/step_widget.py`
- Modify: `flash_tool/ui/log_panel.py`
- Modify: `flash_tool/ui/confirm_dialog.py`
- Modify: `flash_tool/ui/update_dialog.py`
- Modify: `README.md`
- Modify: `docs/codebase-summary.md`
- Modify: `docs/system-architecture.md`

## Implementation Steps

1. Add platform-independent wheel-delta normalization and a Tk-aware manager
   that tracks focus/click targets, scrolls the target canvas, bubbles at
   boundaries, and cleans up bindings.
2. Register the sidebar, image selector list, and step list after construction;
   unregister them before destroying the main window.
3. Replace ad-hoc UI colors/radii and structural emoji controls with shared
   semantic tokens and consistent labels; add a compact step count/status cue.
4. Add unit tests for wheel normalization and boundary target selection using
   lightweight fakes; avoid requiring a display server.
5. Run compile checks, the full unittest suite, diff checks, and a final
   source-level review of all touched UI call sites.

## Success Criteria

- [x] Focused and nested list wheel routing is covered by tests and wired into the window.
- [x] UI components share theme tokens and retain usable hover/disabled/status states.
- [x] Existing flash and profile code paths are unchanged except for UI presentation wiring.
- [x] Compile checks and all tests pass.
- [x] No whitespace errors or unintended staged-change overwrites are introduced.

## Risk Assessment

- Risk: CustomTkinter may already bind wheel events while a pointer is over a
  list, causing duplicate scrolling. Mitigation: focused fallback only handles
  events outside a registered list; native pointer-over behavior remains primary.
- Risk: nested frames could steal wheel input from the sidebar. Mitigation: walk
  registered ancestors and bubble only when the inner canvas is at its boundary.
- Risk: global Tk bindings can outlive the window. Mitigation: retain binding
  identifiers and remove them in `destroy()`.
