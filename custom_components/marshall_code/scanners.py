"""Helpers for logging the state of Home Assistant's Bluetooth scanners."""
from __future__ import annotations

import logging

from homeassistant.components import bluetooth
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


def describe_scanners(hass: HomeAssistant, address: str) -> list[str]:
    """One line per scanner: mode, scanning state, and what it knows of `address`."""
    lines: list[str] = []
    for scanner in bluetooth.async_current_scanners(hass):
        try:
            data = scanner.get_discovered_device_advertisement_data(address)
            allocations = scanner.get_allocations()
            slots = (
                f"{allocations.free}/{allocations.slots}" if allocations else "n/a"
            )
            rssi = f" rssi={data[1].rssi}" if data else ""
            lines.append(
                f"{getattr(scanner, 'name', '?')} source={scanner.source} "
                f"adapter={getattr(scanner, 'adapter', None)} "
                f"connectable={scanner.connectable} scanning={scanner.scanning} "
                f"requested_mode={getattr(scanner, 'requested_mode', None)} "
                f"current_mode={getattr(scanner, 'current_mode', None)} "
                f"since_last_advert={scanner.time_since_last_detection():.0f}s "
                f"sees_amp={data is not None}{rssi} "
                f"connect_failures={scanner.connection_failures(address)} "
                f"free_slots={slots}"
            )
        except Exception as err:  # noqa: BLE001
            lines.append(f"{scanner.source}: could not inspect ({err!r})")
    return lines or ["no scanners registered"]


def log_scanners(hass: HomeAssistant, address: str, reason: str) -> None:
    _LOGGER.warning(
        "%s: %s. Bluetooth scanners:\n  %s",
        address,
        reason,
        "\n  ".join(describe_scanners(hass, address)),
    )
