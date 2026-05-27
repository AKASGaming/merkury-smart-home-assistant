# Merkury Smart for Home Assistant

[![GitHub](https://img.shields.io/github/stars/AKASGaming/merkury-smart-home-assistant?style=social)](https://github.com/AKASGaming/merkury-smart-home-assistant)

Home Assistant custom integration for **[Merkury Smart](https://www.merkurysmart.com/)** devices — the app-backed cloud path that actually works for current Merkury accounts.

Under the hood, Merkury Smart uses the **[Pepper OS](https://pepperos.io)** cloud API (`api.pepperos.io`). The same API powers the **Geeni** app and other Pepper-backed brands, so this integration can work for any account on that cloud — not just Merkury-labeled hardware.

## Why this exists

Merkury plugs and bulbs use Tuya chipsets, but **Merkury Smart app accounts live on Pepper OS**, not Smart Life or the Tuya IoT developer platform. The official [Tuya](https://www.home-assistant.io/integrations/tuya/) integration and [Xtend Tuya](https://github.com/azerty9971/xtend_tuya) often show **no devices** for Merkury-only users.

This integration logs in the same way the Merkury Smart Android app does — email/password to Pepper OS, AWS SigV4 signed requests over HTTP/2. No APK key extraction or Tuya developer account required.

| Approach | Merkury Smart app accounts | Notes |
| -------- | -------------------------- | ----- |
| Official Tuya + Xtend Tuya | Usually **no** | Needs Smart Life linking |
| **This integration** | **Yes** | Pepper OS; Merkury Smart + Geeni + other Pepper brands |
| Tuya CloudCutter + ESPHome | Yes | Permanent; breaks Merkury app control |

## Tested hardware

Verified against a live Merkury Smart account:

| Device | Model | Control |
| ------ | ----- | ------- |
| Smart plug | **MI-WW134-199W-B** | On/off via cloud `powerStateOn` |

Other Merkury / Geeni plugs, bulbs, and strips on the same Pepper cloud should discover automatically if they appear in the Merkury Smart app. Brightness/color control is planned; on/off works today for switches.

## Install in Home Assistant

### Option A — Copy from this repo (recommended for testing)

1. **Download or clone** this repository:
   ```bash
   git clone https://github.com/AKASGaming/merkury-smart-home-assistant.git
   ```
2. Copy the integration folder into your Home Assistant config:
   ```text
   config/custom_components/merkury_smart/
   ```
   Copy everything inside `custom_components/merkury_smart/` from the repo — `__init__.py`, `manifest.json`, `brand/`, `pepper_cloud/`, etc.
3. **Restart Home Assistant** (Settings → System → Restart).
4. **Add the integration:** Settings → Devices & Services → **Add Integration** → search **Merkury Smart**.
5. Sign in with your **Merkury Smart email and password** (same as the app).
6. Leave **brand** as **`geeni`** (required for Merkury Smart accounts on Pepper OS).
7. Choose **Production** for the cloud environment.

Home Assistant installs `httpx[http2]` automatically from `manifest.json` on first load.

### Option B — HACS (manual custom repository)

1. HACS → Integrations → ⋮ → **Custom repositories**
2. Add `https://github.com/AKASGaming/merkury-smart-home-assistant` as type **Integration**
3. Search **Merkury Smart**, install, restart HA, then add the integration as above.

### After setup

- Devices from your Merkury Smart account appear as **switch** (plugs) or **light** entities.
- Use **Configure → Re-sync devices** on the integration card to refresh the device list.
- Poll interval defaults to cloud polling; state updates when HA refreshes the coordinator.

## Command-line test (optional)

Validate login and device discovery before touching Home Assistant:

```powershell
python -m pip install "httpx[http2]"
python tools/test_pepper_cloud.py --email you@example.com --password "your-password"
```

Add `--diagnose` to print signed-request probes to stderr.

## Supported device types

| Type | Examples | Control today |
| ---- | -------- | ------------- |
| Smart plug | MI-WW134-199W-B, MI-WW334, MI-WW102 | On/off |
| Bulbs / strips | Merkury / Geeni lights | On/off (brightness read; dimming planned) |

Anything listed in the Merkury Smart or Geeni app under the same account should be discoverable via `GET /account/devices/`.

## Technical notes

- **Cloud:** Pepper OS `api.pepperos.io` (production)
- **Auth:** `POST /authentication/byEmail` → JWT `peppertoken` + temporary AWS credentials
- **Transport:** HTTP/2 required for signed routes (large auth headers); uses `httpx`
- **Control:** `PUT /account/devices/{id}/settings/powerStateOn/` with `{"valueJson":"1"|"0"}`

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) and [docs/PEPPER_CLOUD_API.md](docs/PEPPER_CLOUD_API.md).

## Project status

| Phase | Goal | Status |
| ----- | ---- | ------ |
| 0 | Architecture & docs | Done |
| 1 | Pepper OS login + discovery | Done |
| 2 | Cloud switch/light entities | Done |
| 3 | Brightness/color via settings API | Planned |
| 4 | Local LAN fallback | Research |

## License

MIT — see [LICENSE](LICENSE).
