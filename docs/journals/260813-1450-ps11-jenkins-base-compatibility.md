---
title: "PS11 Jenkins base preservation fix"
date: 2026-08-13
tags: [ps11, jenkins, avb, regression]
---

# PS11 Jenkins bootloader loop — base preservation fix

## Context

Official Android 17 A8070 boots normally, while the partial Jenkins package
declares Android 17 A8110 and returned the device to bootloader after flashing.
The Jenkins package does not contain `boot.img` or `vendor_boot.img`, so those
boot-critical images must remain from the existing Official base.

## Decision

Treat Jenkins as a same-Android-family partial update. Before the first write,
read the current Android fingerprint over ADB and require the PS11 family and
Android major version to match the Jenkins `vbmeta_system` fingerprint. A build
ID difference such as A8070 versus A8110 is allowed because the existing
Official `boot`, `vendor_boot`, and root `vbmeta` are retained; the difference
is reported as a warning.

After reboot, wait for ADB and verify the booted fingerprint. If the device
returns to fastboot, report the flash as failed and show the current slot state.

The shared root `vbmeta_verification_disabled.img` is not used by default. The
old Jenkins path always flashed that generic bundled image even when the log
said `AVB Disabled: false`; this could replace the working Official root AVB
chain. The default Jenkins path now preserves the installed root `vbmeta`.
Explicit `--disable-avb` requires a valid ROM-local disabled vbmeta and refuses
to use a generic project asset.

## Verification

- Unit/integration tests cover the PS11 A8070/A8110 hybrid case and the
  no-root-vbmeta-write regression.
- `bash -n flash_ps11.sh` passed.
- Jenkins dry-run completed without executing device writes.
- DEB package `1.3.3` metadata verified; no unverified PS11 disabled-root asset
  is bundled.

## Operational requirement

To flash this Jenkins package, the device must first boot the existing PS11
Official base and be visible through ADB. An Official A8070 base is accepted
for the Android 17 Jenkins A8110 payload; the tool warns that it is retaining
the A8070 boot chain.
