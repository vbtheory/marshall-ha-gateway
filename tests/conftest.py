"""Test setup helpers.

`custom_components/marshall_code/__init__.py` now imports real `homeassistant`
modules (it defines `async_setup_entry` etc.), which we deliberately do not
install in the lightweight dev venv used for protocol/BLE-layer testing.

To still be able to unit test HA-independent submodules (`protocol.py`,
`const.py`, ...) without a full `homeassistant` install, register fake
`custom_components` / `custom_components.marshall_code` *package* entries in
`sys.modules` pointing at the right directories, without executing the real
`__init__.py`. Submodule imports (`from custom_components.marshall_code import
protocol`) then resolve normally via each submodule's own file.
"""
from __future__ import annotations

import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COMPONENT_DIR = ROOT / "custom_components" / "marshall_code"

if "custom_components" not in sys.modules:
    fake_root = types.ModuleType("custom_components")
    fake_root.__path__ = [str(ROOT / "custom_components")]
    sys.modules["custom_components"] = fake_root

if "custom_components.marshall_code" not in sys.modules:
    fake_pkg = types.ModuleType("custom_components.marshall_code")
    fake_pkg.__path__ = [str(COMPONENT_DIR)]
    sys.modules["custom_components.marshall_code"] = fake_pkg
