"""Diagnostics for the Marshall CODE integration."""
from __future__ import annotations

import time
from typing import Any

from homeassistant.components import bluetooth
from homeassistant.core import HomeAssistant

from .coordinator import MarshallCodeConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: MarshallCodeConfigEntry
) -> dict[str, Any]:
    """Return scanner visibility and connection state for bug reports."""
    coordinator = entry.runtime_data
    address = coordinator.address

    def _info(connectable: bool) -> dict[str, Any] | None:
        info = bluetooth.async_last_service_info(hass, address, connectable=connectable)
        if info is None:
            return None
        return {
            "name": info.name,
            "rssi": info.rssi,
            "source": info.source,
            "connectable": info.connectable,
            "service_uuids": info.service_uuids,
            "manufacturer_data": {
                str(k): v.hex() for k, v in info.manufacturer_data.items()
            },
            "age_seconds": round(time.monotonic() - info.time),
        }

    return {
        "address": address,
        "connected": coordinator.connected,
        "connectable_advertisement": _info(True),
        "any_advertisement": _info(False),
        "gatt_services": coordinator.gatt_services(),
        "scanner_count": bluetooth.async_scanner_count(hass, connectable=True),
    }
