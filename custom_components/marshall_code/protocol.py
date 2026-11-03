"""Pure-python MIDI/SysEx protocol encode/decode for Marshall CODE amps.

This module has no Home Assistant or BLE dependencies so it can be unit
tested in isolation. It mirrors the logic found in `Amp.java`,
`MIDI.java` and `SysEx.java` of the official Marshall Gateway app.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .const import (
    AVAILABLE_PRESETS,
    DEVICE_TYPE_CABINET,
    DEVICE_TYPE_DELAY,
    DEVICE_TYPE_MODULATION,
    DEVICE_TYPE_PEDAL,
    DEVICE_TYPE_POWER_AMP,
    DEVICE_TYPE_PRE_AMP,
    DEVICE_TYPE_REVERB,
    DEVICE_TYPE_SELECT_MIDI_CODE,
    DEVICE_TYPE_STATE_MIDI_CODE,
    EFFECT_DEVICE_TYPES,
    MIDI_CONTROL_CHANGE,
    MIDI_PROGRAM_CHANGE,
    MIDI_STATE_ON,
    MIDI_TUNER_SUBCOMMAND,
    PREAMP_PARAMETER_MIDI_CODES,
    PRESET_NAME_CHAR_LIMIT,
    SYSEX_BT_SUB_VERSION,
    SYSEX_CMD_ACTIVE_PRESET,
    SYSEX_CMD_BLUETOOTH,
    SYSEX_CMD_GET_DEVICE_INFO,
    SYSEX_CMD_GET_DEVICE_INFO_RESPONSE,
    SYSEX_CMD_INDEXED_PRESET,
    SYSEX_END,
    SYSEX_PREFIX,
    SYSEX_START,
    SYSEX_SUB_GET,
    SYSEX_SUB_GET_1_NAME,
    SYSEX_SUB_GET_REPLY,
)

# Reverse lookup: midi code (int) -> parameter key, for the 6 preamp knobs.
_MIDI_CODE_TO_KNOB = {code: name for name, code in PREAMP_PARAMETER_MIDI_CODES.items()}


def _sysex(command: int, payload: bytes = b"") -> bytes:
    """Build a full SysEx message: F0 00 21 15 7F 7F 7F <command> <payload> F7."""
    return (
        bytes([SYSEX_START])
        + SYSEX_PREFIX
        + bytes([command])
        + payload
        + bytes([SYSEX_END])
    )


def request_device_info() -> bytes:
    """SysEx request for device info (serial number, firmware versions).

    Matches the app's literal constant `F00021157F7F7F10F7` - no payload.
    """
    return _sysex(SYSEX_CMD_GET_DEVICE_INFO)


def request_bluetooth_version() -> bytes:
    """Matches the app's literal constant `F00021157F7F7F620104F7`."""
    return _sysex(SYSEX_CMD_BLUETOOTH, bytes([SYSEX_SUB_GET, SYSEX_BT_SUB_VERSION]))


def request_active_preset() -> bytes:
    return _sysex(SYSEX_CMD_ACTIVE_PRESET, bytes([SYSEX_SUB_GET, 0x00]))


def request_indexed_preset(preset_index: int) -> bytes:
    return _sysex(SYSEX_CMD_INDEXED_PRESET, bytes([SYSEX_SUB_GET, preset_index]))


def request_preset_name(preset_index: int) -> bytes:
    return _sysex(SYSEX_CMD_INDEXED_PRESET, bytes([SYSEX_SUB_GET_1_NAME, preset_index]))


def set_active_preset(preset_index: int) -> bytes:
    """Program Change: select preset slot (0-based) as the active preset."""
    return bytes([MIDI_PROGRAM_CHANGE, preset_index])


def set_control_change(midi_code: int, value: int) -> bytes:
    """Control Change: used for knob values, device on/off and model select."""
    return bytes([MIDI_CONTROL_CHANGE, midi_code, value])


def set_knob_value(knob: str, value: int) -> bytes:
    """Set one of the 6 preamp knobs (gate/gain/volume/bass/middle/treble)."""
    return set_control_change(PREAMP_PARAMETER_MIDI_CODES[knob], value)


def set_device_on(device_type: str, is_on: bool) -> bytes:
    """Toggle one of the 4 effect blocks (Pedal/Modulation/Delay/Reverb)."""
    return set_control_change(
        DEVICE_TYPE_STATE_MIDI_CODE[device_type], MIDI_STATE_ON if is_on else 0x00
    )


def set_device_model(device_type: str, device_id_midi_code: int) -> bytes:
    """Select the active model for a device type (e.g. switch preamp model)."""
    return set_control_change(
        DEVICE_TYPE_SELECT_MIDI_CODE[device_type], device_id_midi_code
    )


def enter_tuner_mode() -> bytes:
    return bytes([MIDI_CONTROL_CHANGE, MIDI_TUNER_SUBCOMMAND, 0x01])


def exit_tuner_mode() -> bytes:
    return bytes([MIDI_CONTROL_CHANGE, MIDI_TUNER_SUBCOMMAND, 0x00])


@dataclass
class VersionInfo:
    major: int
    minor: int

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"{self.major}.{self.minor}"


@dataclass
class DeviceInfo:
    serial_number: str | None = None
    hardware_version: VersionInfo | None = None
    bootloader_version: VersionInfo | None = None
    mcu_version: VersionInfo | None = None
    dsp_version: VersionInfo | None = None
    bluetooth_version: VersionInfo | None = None


@dataclass
class EffectState:
    is_on: bool = False
    model_name: str | None = None


@dataclass
class AmpState:
    """Mutable amp state, updated in place as messages are parsed."""

    device_info: DeviceInfo = field(default_factory=DeviceInfo)
    active_preset_index: int | None = None
    preset_name: str | None = None
    preamp_model: str | None = None
    power_amp_model: str | None = None
    cabinet_model: str | None = None
    knobs: dict[str, int] = field(
        default_factory=lambda: {k: 0 for k in PREAMP_PARAMETER_MIDI_CODES}
    )
    effects: dict[str, EffectState] = field(
        default_factory=lambda: {t: EffectState() for t in EFFECT_DEVICE_TYPES}
    )


def _preset_from_sysex(data: bytes, state: AmpState) -> int | None:
    """Parse a 75-byte active/indexed preset SysEx payload into `state`.

    Layout (byte offsets within the full SysEx frame, mirroring
    `Amp.SysExToAmpPreset`):
      9       slot index
      10-27   preset name (18 bytes, space padded)
      28      reserved
      29      gain
      30      bass
      31      middle
      32      treble
      33      volume
      34      pedal on/off      35 pedal model     36-39 pedal params
      40      preamp on/off     41 preamp model    42    preamp threshold ("gate")
      43      modulation on/off 44 modulation model 45-48 modulation params
      49      delay on/off      50 delay model      51-55 delay params
      56      reverb on/off     57 reverb model     58-61 reverb params
      62      power amp on/off  63 power amp model
      64      cabinet on/off    65 cabinet model
      66-67   power amp params
      74      F7 (end byte)
    """
    if len(data) != 75 or data[0] != SYSEX_START or data[-1] != SYSEX_END:
        return None

    slot_index = data[9]
    name_bytes = data[10:28]
    preset_name = name_bytes.decode("ascii", errors="replace").rstrip(" \x00")

    state.active_preset_index = slot_index
    state.preset_name = preset_name
    state.knobs["gain"] = data[29]
    state.knobs["bass"] = data[30]
    state.knobs["middle"] = data[31]
    state.knobs["treble"] = data[32]
    state.knobs["volume"] = data[33]

    state.effects[DEVICE_TYPE_PEDAL] = EffectState(
        is_on=data[34] == 0x01,
        model_name=_effect_model_name(DEVICE_TYPE_PEDAL, data[35]),
    )
    state.preamp_model = _model_name(DEVICE_TYPE_PRE_AMP, data[41])
    state.knobs["gate"] = data[42]
    state.effects[DEVICE_TYPE_MODULATION] = EffectState(
        is_on=data[43] == 0x01,
        model_name=_effect_model_name(DEVICE_TYPE_MODULATION, data[44]),
    )
    state.effects[DEVICE_TYPE_DELAY] = EffectState(
        is_on=data[49] == 0x01,
        model_name=_effect_model_name(DEVICE_TYPE_DELAY, data[50]),
    )
    state.effects[DEVICE_TYPE_REVERB] = EffectState(
        is_on=data[56] == 0x01,
        model_name=_effect_model_name(DEVICE_TYPE_REVERB, data[57]),
    )
    state.power_amp_model = _model_name(DEVICE_TYPE_POWER_AMP, data[63])
    state.cabinet_model = _model_name(DEVICE_TYPE_CABINET, data[65])
    return slot_index


def _model_name(device_type: str, device_id: int) -> str | None:
    from .const import CABINET_MODELS, POWER_AMP_MODELS, PRE_AMP_MODELS

    table = {
        DEVICE_TYPE_PRE_AMP: PRE_AMP_MODELS,
        DEVICE_TYPE_POWER_AMP: POWER_AMP_MODELS,
        DEVICE_TYPE_CABINET: CABINET_MODELS,
    }.get(device_type, {})
    return table.get(f"{device_id:02X}")


def _effect_model_name(device_type: str, device_id: int) -> str | None:
    from .const import EFFECT_MODELS

    return EFFECT_MODELS.get(device_type, {}).get(f"{device_id:02X}")


class ProtocolParser:
    """Stateful parser that turns raw MIDI/SysEx byte strings into AmpState
    updates, mirroring `Amp.OnReceivedBTMessage`.
    """

    def __init__(self, state: AmpState) -> None:
        self.state = state

    def handle_message(self, data: bytes) -> set[str]:
        """Parse one already-reassembled MIDI/SysEx message.

        Returns a set of state attribute names that were updated, so callers
        can decide which entities need a refresh.
        """
        if not data:
            return set()

        if data[0] == SYSEX_START:
            return self._handle_sysex(data)
        if data[0] == MIDI_CONTROL_CHANGE and len(data) >= 3:
            return self._handle_control_change(data[1], data[2])
        if data[0] == MIDI_PROGRAM_CHANGE and len(data) >= 2:
            self.state.active_preset_index = data[1]
            return {"active_preset_index"}
        return set()

    def _handle_control_change(self, midi_code: int, value: int) -> set[str]:
        if midi_code in _MIDI_CODE_TO_KNOB:
            self.state.knobs[_MIDI_CODE_TO_KNOB[midi_code]] = value
            return {"knobs"}

        for device_type in EFFECT_DEVICE_TYPES:
            if midi_code == DEVICE_TYPE_STATE_MIDI_CODE[device_type]:
                effect = self.state.effects[device_type]
                effect.is_on = value == MIDI_STATE_ON
                return {"effects"}
            if midi_code == DEVICE_TYPE_SELECT_MIDI_CODE[device_type]:
                effect = self.state.effects[device_type]
                effect.model_name = _effect_model_name(device_type, value)
                return {"effects"}

        if midi_code == DEVICE_TYPE_SELECT_MIDI_CODE[DEVICE_TYPE_PRE_AMP]:
            self.state.preamp_model = _model_name(DEVICE_TYPE_PRE_AMP, value)
            return {"preamp_model"}
        if midi_code == DEVICE_TYPE_SELECT_MIDI_CODE[DEVICE_TYPE_POWER_AMP]:
            self.state.power_amp_model = _model_name(DEVICE_TYPE_POWER_AMP, value)
            return {"power_amp_model"}
        if midi_code == DEVICE_TYPE_SELECT_MIDI_CODE[DEVICE_TYPE_CABINET]:
            self.state.cabinet_model = _model_name(DEVICE_TYPE_CABINET, value)
            return {"cabinet_model"}
        return set()

    def _handle_sysex(self, data: bytes) -> set[str]:
        if len(data) < 9:
            return set()
        command = data[7]
        subcommand = data[8]

        if command == SYSEX_CMD_GET_DEVICE_INFO_RESPONSE:
            return self._handle_device_info(data)
        if (
            command == SYSEX_CMD_BLUETOOTH
            and subcommand == SYSEX_SUB_GET_REPLY
            and len(data) >= 20
            and data[9] == SYSEX_BT_SUB_VERSION
        ):
            return self._handle_bluetooth_version(data)
        if command in (SYSEX_CMD_ACTIVE_PRESET, SYSEX_CMD_INDEXED_PRESET) and (
            subcommand == SYSEX_SUB_GET_REPLY
        ):
            if _preset_from_sysex(data, self.state) is not None:
                return {
                    "active_preset_index",
                    "preset_name",
                    "knobs",
                    "effects",
                    "preamp_model",
                    "power_amp_model",
                    "cabinet_model",
                }
        return set()

    def _handle_device_info(self, data: bytes) -> set[str]:
        if len(data) < 24:
            return set()
        info = self.state.device_info
        info.serial_number = data[9:19].decode("ascii", errors="replace")
        info.hardware_version = VersionInfo(data[19], data[20])
        info.bootloader_version = VersionInfo(data[21], data[22])
        num_components = data[23]
        offset = 24
        for _ in range(num_components):
            if offset + 5 > len(data):
                break
            component_id = data[offset]
            major = data[offset + 3]
            minor = data[offset + 4]
            if component_id == 0x01:
                info.mcu_version = VersionInfo(major, minor)
            elif component_id == 0x21:
                info.dsp_version = VersionInfo(major, minor)
            elif component_id == 0x31:
                info.bluetooth_version = VersionInfo(major, minor)
            offset += 5
        return {"device_info"}

    def _handle_bluetooth_version(self, data: bytes) -> set[str]:
        # Payload is an ASCII version string like "v1.23", 10 bytes starting
        # at byte 10.
        if len(data) < 20:
            return set()
        raw = data[10:20].decode("ascii", errors="replace").strip().lower()
        raw = raw.replace("v", "")
        parts = raw.split(".")
        if len(parts) >= 2 and parts[0].isdigit() and parts[-1].isdigit():
            self.state.device_info.bluetooth_version = VersionInfo(
                int(parts[0]), int(parts[-1])
            )
            return {"device_info"}
        return set()


def is_sysex_complete(buffer: bytes) -> bool:
    """Mirror `BTLE.IsSysExComplete`: a SysEx message is complete once an
    0xF7 end byte has been seen."""
    return bool(buffer) and buffer[-1] == SYSEX_END


__all__ = [
    "AVAILABLE_PRESETS",
    "PRESET_NAME_CHAR_LIMIT",
    "AmpState",
    "DeviceInfo",
    "EffectState",
    "ProtocolParser",
    "VersionInfo",
    "enter_tuner_mode",
    "exit_tuner_mode",
    "is_sysex_complete",
    "request_active_preset",
    "request_bluetooth_version",
    "request_device_info",
    "request_indexed_preset",
    "request_preset_name",
    "set_active_preset",
    "set_control_change",
    "set_device_model",
    "set_device_on",
    "set_knob_value",
]
