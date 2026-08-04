# FlashTool — Code Standards

## General Style

- Python 3.10+ with type hints (`str | None`, `list[str]`, `Callable[[...], None] | None`)
- 4-space indentation, no tabs
- Max line length: ~100 characters (soft limit)
- Docstrings for all modules, classes, and public functions
- Unicode section dividers (`# ── Section Name ──`) for visual scanning

## Naming Conventions

| Scope | Convention | Examples |
|-------|------------|----------|
| Modules | snake_case | `flash_worker.py`, `main_window.py` |
| Packages | snake_case | `flash_tool`, `profiles`, `ui` |
| Classes | PascalCase | `FlashWorker`, `MainWindow`, `StepWidget` |
| Functions / Methods | snake_case | `build_g6_ramba_steps`, `detect_adb_device` |
| Constants | UPPER_SNAKE_CASE | `APP_NAME`, `ADB_PATH`, `IMAGE_PATTERNS` |
| Private helpers | leading underscore | `_run_cmd`, `_build_command`, `_handle_unlock_step` |
| Type aliases | PascalCase | `DeviceState = Literal["fastboot", "adb", "disconnected"]` |
| UI StringVars | snake_case + `_var` suffix | `current_model`, `rom_type_var` |

## Python Conventions

- **Imports**: standard library → third-party → local, grouped with a blank line between each
- **Type hints**: encouraged on public function signatures; `Callable` and `Literal` from `typing`
- **Dataclasses**: preferred for configuration objects (`FlashStep`, `FlashProgress`)
- **Enums**: used for finite states (`StepStatus`)
- **Threading**: `threading.Thread` with `threading.Event` for cooperative stop (`_stop_event`)
- **Subprocess**: `subprocess.Popen` with `stdout=subprocess.PIPE` for real-time streaming; `subprocess.run` for short commands

## UI Patterns

- All UI code uses **customtkinter** (`ctk`) widgets, not raw tkinter
- Colors, fonts, and spacing are centralized in `theme.py`; never hard-code hex values in widget files
- Layout managers: `pack` for header/footer, `grid` for sidebar + center body
- `StringVar` / `BooleanVar` for bound UI state
- Widget height fixed where needed (`height=56` for step cards) to prevent layout drift
- `pack_propagate(False)` and `grid_propagate(False)` on frames with fixed dimensions

## Callback Signatures

```python
# Progress update from worker to UI
on_progress: Callable[[FlashProgress], None] | None

# Log line from worker to UI
on_log: Callable[[str], None] | None

# Completion signal
on_finished: Callable[[bool], None] | None
```

## Contribution Guidelines

1. **Keep `main_window.py` focused on layout and event wiring** — business logic belongs in `flash_worker.py` or profiles.
2. **Add new devices via a new profile module** under `flash_tool/profiles/` rather than branching inside `MainWindow`.
3. **Update `FlashTool.spec` hiddenimports** whenever a new module is added, or the PyInstaller build will break.
4. **Test both source-run (`python main.py`) and PyInstaller binary** before committing UI changes.
5. **Match existing comment style**: concise, action-oriented; use Unicode dividers for major sections.
