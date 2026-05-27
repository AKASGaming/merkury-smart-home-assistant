# Pepper OS cloud API (Merkury Smart / Geeni)

This integration uses the **Pepper OS** REST API — the same backend as the Merkury Smart and Geeni mobile apps.

## Merkury Smart compatibility

- Use your **Merkury Smart app email and password**.
- Set **brand** to `geeni` (the Pepper brand slug for Merkury Smart accounts).
- Set **environment** to `production` for normal use.

Geeni-only accounts work the same way with brand `geeni`.

## Endpoints

| Environment | Base URL |
| ----------- | -------- |
| production | `https://api.pepperos.io` |
| staging | `https://staging.api.pepperos.io` |
| uat | `https://uat.api.pepperos.io` |
| dev | `https://dev.api.pepperos.io` |

## Authentication

Merkury Smart v3.15 (`environment: production`) uses the **global** host `https://api.pepperos.io` for login and account APIs—not `us-east-1.api.pepperos.io`.

```http
POST /authentication/byEmail
Authorization: Basic base64("geeni:you@example.com:your-password")
Content-Length: 0
```

On app startup it often refreshes with stored LoginRadius session:

```http
POST /authentication/byToken
Authorization: Basic base64("geeni:<lrToken>")
```

`lrToken` is the 36-character UUID from the login response—not the long JWT in `token`.

### Startup order (from Merkury Smart v3.15 logcat)

The app **must** finish `authenticateByToken` before signed account calls work:

1. `POST /authentication/byToken` (Basic `geeni:<lrToken>`) → profile + AWS creds
2. SDK calls `setCredentials(accessKey, secret, sessionToken, region, pepperToken)`
3. Then `GET /account/devices/` → **200**

Calls to `/account/devices/` **before** step 1–2 return **403** (no valid SigV4 session yet). Config URLs under `/config/` use a separate Bearer token and are not SigV4-signed.

Optional (realtime, not required for device list):  
`POST https://prod.move.pepperos.io/account/users/{userId}/websockets/`

This integration uses **only** the `byToken` profile for `peppertoken` and AWS keys—not the interim `byEmail` credentials.

Response fields used:

- `token` → header `peppertoken` on signed account requests
- `lrToken` → `byToken` refresh only
- `pepperUser.awsUserCredentials` → temporary AWS keys for SigV4 signing

### Session lifetime

AWS temporary credentials from login include an `Expiration` timestamp (typically **~15 minutes**, not one hour). When they expire, signed API calls return **403** (not 401). The integration refreshes proactively (2 minutes before expiry) via `byToken` when possible, falling back to `byEmail`.

## Signed requests

Service: `execute-api`  
Region: from login response (e.g. `us-east-1`)

Required headers:

- `peppertoken`
- `Authorization` (AWS4-HMAC-SHA256)
- `X-Amz-Date`
- `X-Amz-Security-Token`

Paths must include a **trailing slash** on the last segment (matches the Android SDK).

## Devices

```http
GET /account/devices/
```

Returns `PepperAccountDevice` objects with fields such as:

- `pepperDeviceId` — id used for commands
- `deviceId` — external id (e.g. `pso-d0ef76b4bfbc`); shown as device serial in HA
- `name`, `model`, `device_type`, `provider`
- `status` — cloud link state (e.g. `ATTACHED`)
- `firmware.version` — device firmware (e.g. `3.0.0.020`); mapped to HA `sw_version`
- `wifi.wifiNetworkName` — SSID the device joined during pairing
- `timeZone` — device timezone string (e.g. `CST6CDT`)
- `lastPairedAt` — ISO timestamp of last successful pairing
- `powerStateOn`, `light`, `switches`

## Control (plugs and lights)

```http
PUT /account/devices/{pepperDeviceId}/settings/powerStateOn/
PUT /account/devices/{pepperDeviceId}/settings/powerStateOff/

Body: JSON object (app sends `PepperUpdateDeviceSettings`; `{}` works for on/off toggles).
```

Empty body. Commands match activity types in the Merkury Smart app SDK.

## MI-WW334 smart plug

Discovered as a switch entity. On/off uses `powerStateOn` / `powerStateOff`. The plug remains Tuya hardware; Pepper forwards commands to the device cloud.

## Troubleshooting

| Issue | Fix |
| ----- | --- |
| `invalid_auth` | Wrong email/password, or wrong brand (use `geeni` for Merkury Smart) |
| `cannot_connect` | Wrong environment; try `production` |
| HTTP **403** on signed routes | Expired AWS session (~15 min) or SigV4 problem; integration re-authenticates automatically |
| HTTP **502** on `GET /account/devices/` after login | SigV4 passed (unsigned → 403). Backend error after IAM auth—not a wrong password. Regional host usually does not fix it. Compare a live app request via logcat/mitmproxy |
| HTTP **500** `No token supplied` on some routes | Different authorizer; ensure `peppertoken` header matches login `token` |
| Entity does not toggle | Capture app traffic — command strings may differ for some models |
| `no_devices` | No devices paired in Merkury Smart app |

Debug commands:

```bash
python tools/test_pepper_cloud.py --email ... --password ... --diagnose
python tools/compare_signers.py --email ... --password ...
```

If `powerStateOn`/`powerStateOff` fail for a specific model, open an issue with a mitmproxy capture of the app toggling the device.
