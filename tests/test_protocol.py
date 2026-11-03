"""Unit tests for the pure-python protocol layer (no HA/bleak required).

Several expected byte strings below are the literal SysEx constants found
in the decompiled Marshall Gateway app (`SysEx.java`), used here as ground
truth to make sure our Python re-implementation produces byte-identical
messages.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from custom_components.marshall_code import protocol  # noqa: E402
from custom_components.marshall_code.const import (  # noqa: E402
    DEVICE_TYPE_MODULATION,
    DEVICE_TYPE_PEDAL,
    DEVICE_TYPE_PRE_AMP,
)


def _hex(data: bytes) -> str:
    return data.hex().upper()


def test_request_device_info_matches_app_literal():
    assert _hex(protocol.request_device_info()) == "F00021157F7F7F10F7"


def test_request_bluetooth_version_matches_app_literal():
    assert _hex(protocol.request_bluetooth_version()) == "F00021157F7F7F620104F7"


def test_request_active_preset_matches_app_literal():
    assert _hex(protocol.request_active_preset()) == "F00021157F7F7F730100F7"


def test_request_indexed_preset_matches_app_literal():
    assert _hex(protocol.request_indexed_preset(5)) == "F00021157F7F7F720105F7"


def test_request_preset_name_matches_app_literal():
    assert _hex(protocol.request_preset_name(5)) == "F00021157F7F7F720705F7"


def test_set_active_preset_program_change():
    assert _hex(protocol.set_active_preset(3)) == "C003"


def test_set_knob_value_uses_correct_midi_code():
    assert _hex(protocol.set_knob_value("gain", 50)) == "B04632"
    assert _hex(protocol.set_knob_value("treble", 99)) == "B04963"


def test_set_device_on_and_model():
    assert _hex(protocol.set_device_on(DEVICE_TYPE_PEDAL, True)) == "B04B01"
    assert _hex(protocol.set_device_on(DEVICE_TYPE_PEDAL, False)) == "B04B00"
    assert _hex(protocol.set_device_model(DEVICE_TYPE_MODULATION, 0x02)) == "B05602"


def test_parser_control_change_updates_knob():
    state = protocol.AmpState()
    parser = protocol.ProtocolParser(state)
    updated = parser.handle_message(bytes.fromhex("B04632"))  # gain = 0x32
    assert updated == {"knobs"}
    assert state.knobs["gain"] == 0x32


def test_parser_control_change_updates_effect_toggle():
    state = protocol.AmpState()
    parser = protocol.ProtocolParser(state)
    updated = parser.handle_message(bytes.fromhex("B06C01"))  # reverb on
    assert updated == {"effects"}
    assert state.effects["REVERB"].is_on is True


def test_parser_program_change_updates_preset_index():
    state = protocol.AmpState()
    parser = protocol.ProtocolParser(state)
    updated = parser.handle_message(bytes.fromhex("C007"))
    assert updated == {"active_preset_index"}
    assert state.active_preset_index == 7


def _build_preset_frame(
    *,
    slot_index: int = 0,
    name: str = "DEFAULT",
    gain: int = 10,
    bass: int = 20,
    middle: int = 30,
    treble: int = 40,
    volume: int = 50,
    pedal_on: bool = True,
    preamp_model: int = 0x06,
    gate: int = 5,
) -> bytes:
    payload = bytearray(75)
    payload[0] = protocol.SYSEX_START if hasattr(protocol, "SYSEX_START") else 0xF0
    payload[0] = 0xF0
    payload[1:7] = bytes([0x00, 0x21, 0x15, 0x7F, 0x7F, 0x7F])
    payload[7] = 0x73
    payload[8] = 0x03
    payload[9] = slot_index
    name_bytes = name.encode("ascii").ljust(18, b" ")
    payload[10:28] = name_bytes
    payload[28] = 0x00
    payload[29] = gain
    payload[30] = bass
    payload[31] = middle
    payload[32] = treble
    payload[33] = volume
    payload[34] = 0x01 if pedal_on else 0x00
    payload[35] = 0x00  # pedal model (compressor)
    payload[41] = preamp_model
    payload[42] = gate
    payload[74] = 0xF7
    return bytes(payload)


def test_parser_active_preset_sysex_updates_full_state():
    state = protocol.AmpState()
    parser = protocol.ProtocolParser(state)
    frame = _build_preset_frame()
    updated = parser.handle_message(frame)
    assert "preset_name" in updated
    assert state.preset_name == "DEFAULT"
    assert state.active_preset_index == 0
    assert state.knobs["gain"] == 10
    assert state.knobs["bass"] == 20
    assert state.knobs["middle"] == 30
    assert state.knobs["treble"] == 40
    assert state.knobs["volume"] == 50
    assert state.knobs["gate"] == 5
    assert state.effects[DEVICE_TYPE_PEDAL].is_on is True
    assert state.preamp_model == "Plexi"


def test_is_sysex_complete():
    assert protocol.is_sysex_complete(bytes.fromhex("F0002115F7")) is True
    assert protocol.is_sysex_complete(bytes.fromhex("F0002115")) is False
    assert protocol.is_sysex_complete(b"") is False
