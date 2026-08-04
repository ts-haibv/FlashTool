---
title: "X5/X5P ROM auto-detection and regional variant selection"
date: 2026-08-04
tags: [rom-detection, variants, regression-tests]
---

# X5/X5P ROM auto-detection and regional variant selection

## Context

We had a real X5P ROM folder that should have been trivial to detect, but the
app treated it like a generic PS11 package and picked the wrong image set.
The folder contained `system_ext-sx5p.img` plus regional assets under `ML2/`
(`product-ml2.img` and `vbmeta_system-ml2.img`), which is exactly the shape the
loader needed to understand.

## What changed

- Added explicit X5 and X5P markers so detection no longer relies on a broad
  PS11 `system_ext-*.img` catch-all.
- Made the image resolver variant-aware so it selects the matching regional
  `product-*` and `vbmeta_system-*` pair instead of blindly taking the first
  image it sees.
- Wired the UI to surface the variant choice for G6-family regional packages.
- Added regression tests for X5/X5P detection and variant resolution.
- Updated the README so the supported folder shapes are documented instead of
  implied.

## The Brutal Truth

This was a dumb broad-match bug. We let a generic resolver pretend it knew
enough, and then the first-image fallback quietly picked the wrong assets. That
is exactly the kind of bug that wastes time because it looks “almost working”
until a real ROM folder exposes the lie.

## Technical Details

The bad behavior came from matching `system_ext-*.img` too broadly for PS11 and
then resolving the first candidate without respecting the device family or the
regional variant directory. The fix now recognizes X5/X5P markers directly and
uses the selected variant for `product-*` and `vbmeta_system-*` resolution.

## Verification

`29` tests pass. A real X5P ROM now detects as X5P, selects `ML2`, and the UI
import flow works. The Debian build also passes.

## Lessons Learned

If a resolver can silently “guess,” it will eventually guess wrong. Family and
variant selection need to be explicit, test-covered, and visible in the UI.

## Next Steps

Keep the new regression cases close to the resolver logic so the next broad
match gets caught before it ships.
