---
title: "PS11 Jenkins fastbootd mode detection"
date: 2026-08-13
tags: [ps11, fastbootd, jenkins, regression]
---

# PS11 Jenkins fastbootd mode detection

## Context

PS11 Jenkins Android 17 flashing stopped timing out around dynamic partitions.
The device remained in bootloader mode even though `fastboot devices` returned a
serial number.

## Root cause

`wait_for_device("fastbootd")` treated any `fastboot devices` response as proof
that fastbootd was ready. The actual mode contract is
`fastboot getvar is-userspace` → `yes`; the failing device reported `no`.

## Changes

- Require device enumeration plus `is-userspace: yes` before fastbootd work.
- Use the configured `FASTBOOT` binary consistently, including test harnesses.
- Bound the `reboot fastboot` transition and accept its USB disconnect only after
  a later fastbootd verification succeeds.
- Added a regression test covering both bootloader (`no`) and fastbootd (`yes`).
- Documented the mode invariant in the deployment guide.

## Verification

- 38/38 tests pass.
- `bash -n flash_ps11.sh` and `git diff --check` pass.
- Supplied Jenkins and Official PS11 ROM dry-runs complete with `Errors: 0`.
- DEB archive contains the fixed PS11 script and does not ship an unverified
  generic PS11 vbmeta asset.

## Limitation and next step

No physical flash was performed in this source/build verification run. Install
the rebuilt DEB and reproduce on the PS11 device; the log should show
`Device detected in fastbootd mode` before `delete-logical-partition` runs.
