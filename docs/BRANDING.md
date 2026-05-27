# Brand icons (HA vs HACS)

This repo follows both [Home Assistant custom integration branding](https://developers.home-assistant.io/docs/core/integration/brand_images/) and [HACS integration publishing](https://www.hacs.xyz/docs/publish/integration/#brand-assets).

## Structure audit

| Requirement | Expected path | This repo | Used by |
| ----------- | ------------- | --------- | ------- |
| HA 2026.3+ integration icon | `custom_components/merkury_smart/brand/icon.png` (256×256) | Yes | Settings → Integrations, devices |
| HA hDPI icon (optional) | `custom_components/merkury_smart/brand/icon@2x.png` (512×512) | Yes | Retina / hDPI UI |
| HACS publish “brand in repository” | `brand/icon.png` at **repository root** | Yes | HACS validation (when enabled) |
| HACS legacy fallback | `icon.png` at repository root | Yes | Older HACS builds |

Domain in `manifest.json` is `merkury_smart` and must match the integration folder name.

## Why Integrations works but HACS / Updates may not

Home Assistant **2026.3+** serves installed integration icons from your local files:

`/api/brands/integration/merkury_smart/icon.png`

That is why icons appear under **Settings → Integrations** after install.

**HACS** and the **Updates** list still often request:

`https://brands.home-assistant.io/_/merkury_smart/icon.png`

That CDN only lists domains in the [home-assistant/brands](https://github.com/home-assistant/brands) repository. New custom integrations are **no longer accepted** there (see [brands PR policy](https://github.com/home-assistant/brands/pull/9884#issuecomment-3974094976)). `merkury_smart` is not on the CDN, so HACS shows a placeholder even when your repo layout is correct.

This is a known HACS limitation, not a missing file in this repo:

- [hacs/integration#5171](https://github.com/hacs/integration/issues/5171)
- [hacs/integration#5223](https://github.com/hacs/integration/issues/5223)

Fixes are in progress in HACS (e.g. [hacs/frontend#937](https://github.com/hacs/frontend/pull/937)) to load icons from the local HA brands API or from GitHub `brand/icon.png`.

## What you can do

1. **Confirm HA branding** — After install, open `/api/brands/integration/merkury_smart/icon.png` while logged in (or check Integrations). If that works, your `custom_components/merkury_smart/brand/` files are correct.
2. **Update HACS** when a release includes the brands-proxy frontend fix.
3. **Clear HACS cache** (HACS → ⋮ → Clear cache) after updating this integration; stale metadata can keep old placeholders.
4. **Ignore placeholder in HACS** until HACS ships the fix — control and discovery are unaffected.

## Optional assets

The [brand images docs](https://developers.home-assistant.io/docs/core/integration/brand_images/) also support `logo.png`, `dark_icon.png`, and `dark_*` variants. Only `icon.png` / `icon@2x.png` are required today.
