# Merkury Smart — Setup Guide

Works with **Merkury Smart** and **Geeni** accounts on the Pepper OS cloud.

## Prerequisites

- Home Assistant 2024.1+
- Merkury Smart (or Geeni) app account with at least one device paired
- Devices visible in the mobile app

## Install

1. Copy `custom_components/merkury_smart` to `<HA config>/custom_components/merkury_smart`.
2. Restart Home Assistant.
3. **Settings → Devices & Services → Add Integration → Merkury Smart**.

## Configuration

| Field | Value for Merkury Smart users |
| ----- | ----------------------------- |
| Email address | Your Merkury Smart login email |
| Password | Your Merkury Smart password |
| Pepper brand slug | `geeni` (default — do not change unless instructed) |
| Pepper cloud environment | `production` |

No APK extraction, Tuya IoT project, or Smart Life account is required.

## Verify with the test script

```bash
python tools/test_pepper_cloud.py \
  --email YOUR_EMAIL \
  --password 'YOUR_PASSWORD'
```

You should see `Login OK` and a list of devices.

## After setup

- Switches and lights appear under the **Merkury Smart** hub.
- State refreshes about every 30 seconds.
- Use **Configure → Re-sync devices** if you add new devices in the app.

## Upgrading from an older config entry

Config flow version 2 uses Pepper OS only. If you configured an older version that asked for Tuya app keys, **remove the integration and add it again** with your Merkury Smart email and password.

## What does not work

- Official Tuya integration without Smart Life migration
- Tuya IoT Platform + `tinytuya wizard` for Merkury-only accounts
- Local control without local keys (not exposed by Pepper API today)

## Troubleshooting

See [PEPPER_CLOUD_API.md](PEPPER_CLOUD_API.md).
