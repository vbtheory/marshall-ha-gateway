"""Constants for the Marshall CODE integration.

All protocol values below were reverse engineered from the official
"Marshall Gateway" Android app (air.com.marshall.gateway v2.1.9) and its
bundled `assets/amp_configs/CODE1.json` / `supported_amps.json` config
files, which ship with every CODE-series amplifier profile.
"""
from __future__ import annotations

DOMAIN = "marshall_code"

# --- BLE identifiers -------------------------------------------------------

# GATT service/characteristic UUIDs used by the CODE1 family (CODE25/50/100,
# CODE1 1x12/2x12/4x12 combos and heads). CODE_LTE amps use the same
# characteristic layout under a different (vendor specific) service UUID.
MIDI_SERVICE_UUID = "14839ac4-7d7e-415c-9a42-167340cf2339"
WRITE_WITH_RESPONSE_UUID = "ba04c4b2-892b-43be-b69c-5d13f2195392"
WRITE_WITHOUT_RESPONSE_UUID = "8b00ace7-eb0b-49b0-bbe9-9aee0a26e1a3"
NOTIFY_UUID = "0734594a-a8e7-4b1a-a6b1-cd5243059a57"

# Advertised service UUID while scanning/advertising (before connecting), per
# the decompiled app's `supported_amps.json`. Observed real-world CODE1 amps
# don't reliably include this in their advertisement data though (the
# standard "Immediate Alert Service" 16-bit UUID), so `manifest.json`'s
# `bluetooth` discovery matchers intentionally key on `local_name` alone -
# requiring both would AND-combine into a matcher that can silently never
# fire. Kept here for reference/future use (e.g. post-connect verification).
ADVERTISED_SERVICE_UUID_CODE1 = "00001802-0000-1000-8000-00805f9b34fb"
ADVERTISED_SERVICE_UUID_CODE_LTE = "3923cf40-7316-429a-5c41-7e7dc49a8314"

# BLE local name prefixes used to recognise an amp while scanning.
LOCAL_NAME_PREFIXES = ("CODE V01", "CODE V02", "CODE LTE")

CONNECT_TIMEOUT = 15
RECONNECT_TIMEOUT = 60

# --- MIDI command bytes -----------------------------------------------------

MIDI_CONTROL_CHANGE = 0xB0
MIDI_PROGRAM_CHANGE = 0xC0
MIDI_TUNER = 0xA0

MIDI_TUNER_SUBCOMMAND = 0x34
MIDI_STATE_ON = 0x01
MIDI_STATE_OFF = 0x00

# --- SysEx framing -----------------------------------------------------------

SYSEX_START = 0xF0
SYSEX_END = 0xF7
# Vendor prefix + wildcard family/model/device bytes used in all outgoing
# SysEx requests: F0 00 21 15 7F 7F 7F <command> ...
SYSEX_PREFIX = bytes([0x00, 0x21, 0x15, 0x7F, 0x7F, 0x7F])

SYSEX_CMD_GET_DEVICE_INFO = 0x10
SYSEX_CMD_GET_DEVICE_INFO_RESPONSE = 0x11
SYSEX_CMD_BLUETOOTH = 0x62
SYSEX_CMD_INDEXED_PRESET = 0x72
SYSEX_CMD_ACTIVE_PRESET = 0x73

SYSEX_SUB_GET = 0x01
SYSEX_SUB_SET = 0x02
SYSEX_SUB_GET_REPLY = 0x03
SYSEX_SUB_SET_REPLY_OK = 0x04
SYSEX_SUB_SET_REPLY_ERROR = 0x05
SYSEX_SUB_GET_1_NAME = 0x07
SYSEX_SUB_GET_3_NAMES = 0x08

SYSEX_BT_SUB_ADDRESS = 0x03
SYSEX_BT_SUB_VERSION = 0x04

PRESET_NAME_CHAR_LIMIT = 18
AVAILABLE_PRESETS = 100

# --- Device types & MIDI codes ----------------------------------------------
# Pulled from CODE1.json "deviceTypes". stateMidiCode toggles on/off via a
# Control Change, selectTypeMidiCode changes the selected model via a
# Control Change whose value is the model's deviceIdMidiCode.

DEVICE_TYPE_PEDAL = "PEDAL"
DEVICE_TYPE_PRE_AMP = "PRE_AMP"
DEVICE_TYPE_MODULATION = "MODULATION"
DEVICE_TYPE_DELAY = "DELAY"
DEVICE_TYPE_REVERB = "REVERB"
DEVICE_TYPE_POWER_AMP = "POWER_AMP"
DEVICE_TYPE_CABINET = "CABINET"

# The four toggleable "effects" shown on the app's Home screen / Effect tab.
EFFECT_DEVICE_TYPES = (
    DEVICE_TYPE_PEDAL,
    DEVICE_TYPE_MODULATION,
    DEVICE_TYPE_DELAY,
    DEVICE_TYPE_REVERB,
)

DEVICE_TYPE_STATE_MIDI_CODE = {
    DEVICE_TYPE_PEDAL: 0x4B,
    DEVICE_TYPE_PRE_AMP: 0x51,
    DEVICE_TYPE_MODULATION: 0x55,
    DEVICE_TYPE_DELAY: 0x67,
    DEVICE_TYPE_REVERB: 0x6C,
    DEVICE_TYPE_POWER_AMP: 0x72,
    DEVICE_TYPE_CABINET: 0x74,
}

DEVICE_TYPE_SELECT_MIDI_CODE = {
    DEVICE_TYPE_PEDAL: 0x4C,
    DEVICE_TYPE_PRE_AMP: 0x52,
    DEVICE_TYPE_MODULATION: 0x56,
    DEVICE_TYPE_DELAY: 0x68,
    DEVICE_TYPE_REVERB: 0x6D,
    DEVICE_TYPE_POWER_AMP: 0x73,
    DEVICE_TYPE_CABINET: 0x75,
}

# The 6 "Home screen" knobs are the currently selected PRE_AMP device's own
# parameters. All 15 CODE1 preamp models (JTM45, Plexi, JCM800, ...) share
# the same MIDI codes for these parameters.
PREAMP_PARAMETER_MIDI_CODES = {
    "gate": 0x53,  # displayed as "Gate", internally "Threshold"
    "gain": 0x46,
    "volume": 0x4A,
    "bass": 0x47,
    "middle": 0x48,
    "treble": 0x49,
}
KNOB_MIN_VALUE = 0
KNOB_MAX_VALUE = 100
# Values are displayed in the app scaled down to a 0-10 dial.
KNOB_DISPLAY_SCALE = 10

# Preamp/Power-amp/Cabinet model name -> deviceIdMidiCode, as declared in
# CODE1.json "devices" (type == PRE_AMP / POWER_AMP / CABINET).
PRE_AMP_MODELS = {
    "00": "JTM45",
    "01": "Clean DSL",
    "02": "Clean American",
    "03": "Clean JVM",
    "04": "Acoustic",
    "05": "Bluesbreaker",
    "06": "Plexi",
    "07": "Crunch American",
    "08": "JCM800",
    "09": "50's British",
    "0A": "OD JVM",
    "0B": "OD DSL",
    "0C": "OD American",
    "0D": "OD Silver Jubilee",
    "0E": "Natural",
}
POWER_AMP_MODELS = {
    "00": "Classic Marshall 100w",
    "01": "Vintage Marshall 30w",
    "02": "British Class A",
    "03": "American Class A/B",
}
CABINET_MODELS = {
    "00": "1960",
    "01": "1960V",
    "02": "1960X",
    "03": "1960HW",
    "04": "1936",
    "05": "1936V",
    "06": "1912",
    "07": "1974CX",
}

# Effect-slot model names, keyed by device type then deviceIdMidiCode.
EFFECT_MODELS = {
    DEVICE_TYPE_PEDAL: {
        "00": "Compressor",
        "01": "Distortion",
        "02": "Auto Wah",
        "03": "Pitch Shifter",
    },
    DEVICE_TYPE_MODULATION: {
        "00": "Chorus",
        "01": "Flanger",
        "02": "Phaser",
        "03": "Tremolo",
    },
    DEVICE_TYPE_DELAY: {
        "00": "Studio",
        "01": "Vintage",
        "02": "Multi",
        "03": "Reverse",
    },
    DEVICE_TYPE_REVERB: {
        "00": "Room",
        "01": "Hall",
        "02": "Spring",
        "03": "Stadium",
    },
}

# --- Config entry / options keys --------------------------------------------

CONF_ADDRESS = "address"

SIGNAL_MARSHALL_CODE_UPDATE = f"{DOMAIN}_update_{{address}}"

SERVICE_CONNECT = "connect"
