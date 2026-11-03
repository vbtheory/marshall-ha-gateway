# Marshall CODE Amplifier — Home Assistant Integration

A Home Assistant custom integration for **Marshall CODE-series guitar
amplifiers** (CODE25/50/100, CODE1 combos/heads, CODE_LTE), controlling the
amp over its built-in Bluetooth Low Energy connection — the same protocol
used by the official "Marshall Gateway" mobile app.

> **Status:** under active development. The BLE/MIDI protocol has been fully
> reverse engineered from the official app; the Home Assistant integration is
> being built incrementally, with regular milestone commits.

## Why

Marshall never published an HA integration or a public API for these amps.
This project reverse engineers the Bluetooth protocol used by the official
Android app (decompiled with `apktool`/`jadx`) to let Home Assistant discover,
auto-connect to, and control a CODE amp directly — no phone app required.

## Planned features

- Auto-discovery and auto-connect using Home Assistant's built-in
  `bluetooth` integration (no manual pairing flow) plus a manual
  `marshall_code.connect` service for forcing a (re)connection attempt.
- `binary_sensor` for BLE connection state.
- `sensor` for the current preset name and firmware/version info.
- `switch` entities for the 4 toggleable effect blocks (Pedal, Modulation,
  Delay, Reverb) — mirrors the app's Home screen red effects bar.
- `number` entities for the 6 main preamp knobs (Gate, Gain, Volume, Bass,
  Middle, Treble) — mirrors the app's Home screen knob grid.
- `select` entity to jump between the amp's up-to-100 onboard presets.

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
  full, documented command set.

## Development

```bash
python3 -m venv .venv
.venv/bin/pip install pytest
.venv/bin/python -m pytest tests/
```

The `protocol.py` module has no Home Assistant or BLE dependency and is unit
tested against byte-identical literal SysEx strings extracted from the
decompiled app, so its correctness can be verified without any physical amp.

## Disclaimer

This is an unofficial, community reverse-engineering project. It is not
affiliated with, endorsed by, or supported by Marshall Amplification plc.
"Marshall" and "CODE" are trademarks of their respective owners.
