# FlashTool — Project Roadmap

## Current State (v1.1.6)

| Area | Status |
|------|--------|
| G6 RAMBA flashing | Stable — 16–18 step profile with unlock, vbmeta, partition flash, erase, reboot |
| Generic "Other Model" flashing | Stable — flexible partition list, fastbootd, region variants |
| PS11 script-backed flashing | Stable — 4-phase visual decomposition |
| E11 / E10 script-backed flashing | Stable — auto ROM detect, multi-variant |
| Real-time sparse progress | Working — parsed from fastboot stdout |
| Skip SUW post-flash | Working — marks device provisioned after reboot |
| Cross-platform builds | Stable — PyInstaller Linux + Windows binaries, .deb package |
| CI/CD | Stable — GitHub Actions auto-release on version tags |

## Known Gaps

| ID | Gap | Impact | Mitigation |
|----|-----|--------|------------|
| GAP-1 | No bundled adb/fastboot | Users must install platform-tools manually | Document install steps; consider bundling in future |
| GAP-2 | No automated test coverage | Regressions only caught by manual flashing | Add unit tests for `config.scan_rom_folder`, `device_manager`, and profile builders |
| GAP-3 | No logging to file | Hard to diagnose failures after the fact | Add file handler to `flash_worker` logs |
| GAP-4 | Windows script profiles require WSL/Git Bash | PS11/E11/E10 unavailable on native Windows | Document requirement; consider PowerShell ports |
| GAP-5 | `main_window.py` is 1399 lines | Difficult to navigate and review | Extract sidebar, center, and footer into sub-modules |
| GAP-6 | No retry logic for transient fastboot failures | User must restart entire flash | Add per-step retry with exponential backoff |
| GAP-7 | Sparse progress parser only handles one pattern | Other devices may use different progress formats | Make progress regex configurable per profile |
| GAP-8 | No signature/integrity verification of ROM images | Corrupted images may brick device | Add SHA256 checksum validation if checksum files present |

## Potential Improvements

| Priority | Improvement | Effort | Benefit |
|----------|-------------|--------|---------|
| P1 | Modularize `main_window.py` into sidebar/center/footer sub-modules | Medium | Maintainability, faster code reviews |
| P1 | Add pytest suite for core modules | Medium | Confidence in refactors, CI gate |
| P2 | Log to rotating file (`logs/flashtool_*.log`) | Low | Post-mortem debugging |
| P2 | Configurable progress regex per profile | Low | Support more devices out of the box |
| P2 | Retry failed fastboot steps (up to N attempts) | Medium | Reduce manual restarts |
| P3 | Bundle adb/fastboot binaries in PyInstaller build | High | Zero-dependency user experience |
| P3 | Dark / light theme toggle | Low | Accessibility preference |
| P3 | Save/load last used ROM folder and image selections | Low | Faster repeated flashes |

## Future Device Support

| Device Family | Estimated Complexity | Notes |
|---------------|----------------------|-------|
| G6 successor (RAMBA2+) | Low | Reuse `g6_ramba.py` with partition mapping tweaks |
| Additional Sharp variants | Low | Add variant to existing `flash_ps11.sh` or new script profile |
| Qualcomm QDL (EDL mode) | High | `qdl/` C library exists but is not integrated into the Python app |
| Samsung Odin protocol | High | Entirely different protocol; new worker class needed |
| MediaTek SP Flash Tool | High | Requires BROM/VCOM drivers and new protocol layer |

## Release Milestone Ideas

| Version | Theme |
|---------|-------|
| v1.2.0 | Test coverage + modularized UI + log-to-file |
| v1.3.0 | Retry logic + per-profile progress parsers + saved preferences |
| v2.0.0 | QDL/EDL integration (leverage `qdl/` C library) + bundled platform-tools |
