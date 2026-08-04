---
title: "Focused list scrolling and UI polish"
description: "Add reliable focused-list mouse-wheel scrolling and bring the desktop UI onto a consistent professional visual system."
status: completed
priority: P2
branch: main
tags: [feature, bugfix, frontend]
blockedBy: []
blocks: []
created: 2026-08-04
completed: 2026-08-04
---

# Focused list scrolling and UI polish

## Overview

Improve the CustomTkinter desktop experience without changing flashing behavior.
The change covers reliable mouse-wheel routing for focused/nested scroll areas and
a cohesive dark-tool visual system across the main window components.

## Scope and constraints

- Preserve all profile, ROM scanning, device polling, worker, and flash command contracts.
- Modify UI/theme code, focused regression tests, and the smallest owning docs surfaces.
- Keep the existing minimum window size and nested image-list behavior usable on small screens.
- Do not add runtime dependencies.

## Phases

| Phase | Name | Status |
|---|---|---|
| 1 | Scroll behavior and visual consistency | Completed |

## Acceptance criteria

- Mouse-wheel events scroll the list most recently focused or clicked, even after the pointer leaves it.
- Nested image lists route wheel movement to the inner list first and bubble to the sidebar at its scroll boundary.
- Wheel delta normalization works for Windows/macOS-style deltas and Linux button events.
- Main window controls, cards, steps, console, and footer use shared theme tokens with visible active/disabled/status states.
- Flash/profile behavior and public non-UI contracts remain unchanged.
- `python -m unittest discover -s tests -v` and Python compile checks pass.
