"""Helpers for logging the state of Home Assistant's Bluetooth scanners."""
from __future__ import annotations

import logging
import time

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import (
    BluetoothCallbackMatcher,
    BluetoothScanningMode,
)
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


def connectable_scanner_choices(hass: HomeAssistant, address: str) -> dict[str, str]:
    """Source -> label for every connectable scanner (adapters and proxies)."""
    seen = {
        device.scanner.source: device.advertisement.rssi
        for device in bluetooth.async_scanner_devices_by_address(
            hass, address, connectable=True
        )
    }
    choices: dict[str, str] = {}
    for scanner in bluetooth.async_current_scanners(hass):
        if not scanner.connectable:
            continue
        rssi = seen.get(scanner.source)
        status = f"sees amp, RSSI {rssi}" if rssi is not None else "doesn't see amp"
        choices[scanner.source] = (
            f"{getattr(scanner, 'name', scanner.source)} ({scanner.source}) - {status}"
        )
    return choices


def get_ble_device(hass: HomeAssistant, address: str, source: str | None):
    """The BLEDevice for `address`, optionally only via the scanner `source`."""
    if source is None:
        return bluetooth.async_ble_device_from_address(hass, address, connectable=True)
    for device in bluetooth.async_scanner_devices_by_address(
        hass, address, connectable=True
    ):
        if device.scanner.source == source:
            return device.ble_device
    return None


FRESH_ADVERT_AGE = 30
ADVERT_WAIT_TIMEOUT = 30


async def async_wait_for_fresh_advert(
    hass: HomeAssistant, address: str, source: str | None
) -> None:
    """Wait for a live connectable advertisement from the amp.

    HA keeps the last advertisement for a while, so a cached entry does not
    mean the amp is on and in range right now. Returns when one arrives (or
    the cached one is recent enough); on timeout it just returns and the
    caller falls back to whatever is cached.
    """
    info = bluetooth.async_last_service_info(hass, address, connectable=True)
    if (
        info is not None
        and (source is None or info.source == source)
        and time.monotonic() - info.time < FRESH_ADVERT_AGE
    ):
        return
    try:
        await bluetooth.async_process_advertisements(
            hass,
            lambda service_info: source is None or service_info.source == source,
            BluetoothCallbackMatcher(address=address, connectable=True),
            BluetoothScanningMode.ACTIVE,
            ADVERT_WAIT_TIMEOUT,
        )
    except TimeoutError:
        _LOGGER.debug(
            "%s: no fresh advertisement within %ss", address, ADVERT_WAIT_TIMEOUT
        )
