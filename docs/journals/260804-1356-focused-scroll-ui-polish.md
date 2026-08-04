---
title: "Focused list scrolling and UI polish"
date: 2026-08-04
tags: [ui, scrolling, customtkinter]
---

# Focused list scrolling and UI polish

## Context

FlashTool's nested configuration and flash-step lists did not reliably respond
to the mouse wheel after focus moved away from the list.

## What changed

- Added `WheelScrollManager` for focused/clicked list fallback, cross-platform
  wheel normalization, nested boundary bubbling, and callback-specific cleanup.
- Registered the sidebar, image selector list, and flash-step list.
- Centralized interaction colors/radii and aligned main window, step, console,
  confirmation, and update dialogs.
- Added focused-wheel regression tests and documented the new behavior.

## Decisions

Pointer-over-list scrolling remains CustomTkinter's native path; the manager
only handles focused-list fallback and boundary handoff to avoid double scroll.

## Verification

`python -m unittest discover -s tests -v` passed 14/14 tests. Python compile
checks and `git diff --check` also passed. A full GUI smoke test remains
display-server dependent.
