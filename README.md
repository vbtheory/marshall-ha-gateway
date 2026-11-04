# Marshall CODE Amplifier — Home Assistant Integration

A Home Assistant custom integration for **Marshall CODE-series guitar
amplifiers** (CODE25/50/100, CODE1 combos/heads, CODE_LTE), controlling the
amp directly over its built-in Bluetooth Low Energy connection — the same
protocol used by the official "Marshall Gateway" mobile app. No phone app,
cloud account, or hub required.

> **Status:** functionally complete for the first release scope (see
> [Entities](#entities) and [Services](#services) below). Not yet tested
> against a physical amp — if you try it, please open an issue with what you
> find. CI/hassfest validation and HACS release packaging are still pending.

## Why

Marshall never published an HA integration or a public API for these amps.
This project reverse engineers the Bluetooth protocol used by the official
Android app (decompiled with `apktool`/`jadx`) so Home Assistant can discover,
auto-connect to, and control a CODE amp directly.

## Installation

### HACS (custom repository)

1. In HACS, go to **Integrations → ⋮ → Custom repositories**.
2. Add `https://github.com/vbtheory/marshall-ha-gateway` as an **Integration**.
3. Install "Marshall CODE Amplifier", then restart Home Assistant.

### Manual

1. Copy `custom_components/marshall_code` into your Home Assistant
   `config/custom_components/` directory.
2. Restart Home Assistant.

## Setup

The amp is set up like any other Bluetooth device:

- **Automatic:** if the amp is powered on and in range, Home Assistant's
  `bluetooth` integration will discover it and show a notification under
  **Settings → Devices & Services**. Click it, confirm, and you're done.
- **Manual:** go to **Settings → Devices & Services → Add Integration →
  Marshall CODE Amplifier**, and pick your amp from the list of currently
  visible devices.

Once set up, the integration keeps a persistent BLE connection open and
auto-reconnects whenever the amp comes back into range (e.g. after being
powered off/on) — there's no need to re-run the config flow.

## Entities

| Platform        | Entity               | Description                                                                 |
|-----------------|-----------------------|-------------------------------------------------------------------------------|
| `binary_sensor` | Connected             | Whether the BLE connection to the amp is currently up                        |
| `sensor`        | Preset name           | Name of the currently active preset (+ `preset_index` attribute)             |
| `sensor`        | DSP version           | DSP firmware version (+ serial number, hardware/bootloader/MCU/BT versions)   |
| `switch`        | Pedal                 | Pedal effect block on/off (+ `model` attribute, e.g. "Compressor")           |
| `switch`        | Modulation             | Modulation effect block on/off (+ `model` attribute, e.g. "Chorus")          |
| `switch`        | Delay                 | Delay effect block on/off (+ `model` attribute, e.g. "Vintage")              |
| `switch`        | Reverb                | Reverb effect block on/off (+ `model` attribute, e.g. "Room")                |
| `number`        | Gate                  | Noise gate / threshold knob (0-100)                                          |
| `number`        | Gain                  | Gain knob (0-100)                                                            |
| `number`        | Bass                  | Bass knob (0-100)                                                            |
| `number`        | Middle                | Middle knob (0-100)                                                          |
| `number`        | Treble                | Treble knob (0-100)                                                          |
| `number`        | Volume                | Volume knob (0-100)                                                          |
| `select`        | Preset                | Jump directly to any of the amp's 100 onboard preset slots ("Preset 1"-"Preset 100") |

These mirror the official app's Home screen: the preset header, the 6-knob
grid for the currently selected preamp, and the 4 effect toggle icons.

Knob values are raw MIDI CC values (0-100); the app displays these scaled
down to a 0-10 dial on screen, but the underlying value is the same.

## Services

### `marshall_code.connect`

Manually (re)connects to the amp, in case you don't want to wait for
auto-connect (e.g. right after powering it on). Takes a `device_id` target.

```yaml
service: marshall_code.connect
target:
  device_id: <device id of your amp>
```

## Troubleshooting

The amp is a dual-mode device: classic Bluetooth audio plus a BLE GATT
control service on the same address. This integration only uses BLE.

- Set the Bluetooth adapter's scanning mode to **Active** (or Auto) in
  Home Assistant's Bluetooth integration options; the amp may only expose
  its name/UUIDs in scan-response packets, which passive scans miss.
- Don't `pair`/`connect` the amp from `bluetoothctl`: that creates a
  classic (BR/EDR) link. Errors like `br-connection-key-missing` or
  `br-connection-unknown` mean BlueZ is attempting a classic connection;
  run `bluetoothctl remove <address>` and let HA rediscover it.
- Disconnect the amp from your phone (turn its Bluetooth off or force-close
  the Marshall Gateway app) while testing; the amp may not advertise while
  connected elsewhere.
- If the adapter keeps trying classic connections, use an ESPHome Bluetooth
  proxy, which connects over BLE only. If the automatic connection fails
  during setup you can pick the adapter/proxy to use; change it later via
  the integration's **Configure** button.
- If the amp only accepts bonded devices (it shows a pairing code on your
  phone), enable **Pair (bond) with the amp when connecting** in the same
  step/**Configure** dialog. Pairing happens through the selected adapter or
  ESPHome proxy, so no `bluetoothctl` is needed.
- On BlueZ 5.80+ (Home Assistant OS 16+) the integration sets the amp's
  experimental `PreferredBearer` to `le` before connecting, so BlueZ doesn't
  choose the classic link. It is skipped silently on older BlueZ or when the
  amp is only known as a classic device; the log line
  `set BlueZ PreferredBearer=le` confirms it applied.
- Enable debug logging for `custom_components.marshall_code` and
  `bleak_retry_connector`; connect failures are logged as warnings with the
  underlying cause.

## Protocol summary

- BLE GATT MIDI service `14839ac4-7d7e-415c-9a42-167340cf2339` with separate
  write-with-response / write-without-response / notify characteristics.
- Plain 3-byte MIDI messages (Control Change / Program Change) for live knob
  and effect changes; SysEx (`F0 00 21 15 7F 7F 7F <cmd> ... F7`) for device
  info, firmware versions, and full preset get/set.
- All 15 CODE1 preamp models share identical MIDI CC codes for their 6
  parameters (Gate=0x53, Gain=0x46, Volume=0x4A, Bass=0x47, Middle=0x48,
  Treble=0x49); only the active model ID differs.
- See `custom_components/marshall_code/const.py` and `protocol.py` for the
  full, documented command set, including device-type and model-name lookup
  tables for every preamp/power-amp/cabinet/effect model.

## Architecture

- `protocol.py` — pure-Python MIDI/SysEx message encode/decode, no Home
  Assistant or BLE dependency. Fully unit tested against literal byte strings
  extracted from the decompiled app.
- `ble.py` — thin `bleak`/`bleak-retry-connector` wrapper: connect, discover
  characteristics, subscribe, reassemble fragmented SysEx notifications.
- `coordinator.py` — owns the BLE connection and parsed amp state for one
  amp. Unlike most BLE integrations (which poll short-lived passive
  advertisements), the amp needs a persistent, stateful GATT session kept
  open for as long as it's in range — so this is a custom coordinator, not
  HA's generic `ActiveBluetoothDataUpdateCoordinator`. It registers with HA's
  `bluetooth` integration to auto-connect when the amp's advertisement is
  seen, and pushes state changes to entities via a dispatcher signal.
- `config_flow.py` — bluetooth-discovery and manual device-picker setup.
- `entity.py` + platform modules — one base entity class shared by all
  platforms, each subscribing to the coordinator's push updates.
- `services.py` — the `marshall_code.connect` service.

## Development

This integration's protocol/BLE logic can be developed and unit tested
without a full `homeassistant` install (which pulls in a very large
dependency tree). The dev venv only needs `bleak`, `pytest`, and `ruff`:

```bash
python3 -m venv .venv
.venv/bin/pip install pytest ruff bleak bleak-retry-connector
.venv/bin/python -m pytest tests/
.venv/bin/ruff check custom_components/ tests/
```

`protocol.py` has zero Home Assistant/BLE imports and is tested directly.
Modules that *do* import `homeassistant` (`coordinator.py`, `config_flow.py`,
`__init__.py`, the entity platforms, ...) are syntax-checked and validated by
reading the relevant APIs straight from the
[`home-assistant/core`](https://github.com/home-assistant/core) source at the
target release tag, rather than by installing the full package locally.
`tests/conftest.py` registers lightweight fake `custom_components`/
`custom_components.marshall_code` package entries so HA-independent
submodules can still be imported and tested in isolation.

### Releasing a new version (HACS)

HACS tracks available updates via GitHub Releases, so a new version only
shows up for users once both the manifest version and a matching release
tag exist:

1. Bump `"version"` in `custom_components/marshall_code/manifest.json`
   (semver, no leading `v`).
2. Commit on a branch and merge it to `main` via PR (`main` is protected).
3. Tag the merge commit and push the tag:
   ```bash
   git checkout main && git pull
   git tag vX.Y.Z
   git push origin vX.Y.Z
   ```
4. `.github/workflows/release.yml` verifies the tag matches
   `manifest.json` and publishes a GitHub Release automatically. HACS
   then shows an update to anyone with an older version installed.

## Disclaimer

This is an unofficial, community reverse-engineering project. It is not
affiliated with, endorsed by, or supported by Marshall Amplification plc.
"Marshall" and "CODE" are trademarks of their respective owners.
