"""Connection coordinator for a Marshall CODE amp.

Rather than HA's generic `ActiveBluetoothDataUpdateCoordinator` (designed
for short poll-per-update BLE devices), this amp needs a *persistent*,
stateful GATT session - exactly like the official app keeps one open for as
long as the amp is in range. This coordinator:

- Registers a callback with HA's `bluetooth` integration so it is notified
  whenever the amp's advertisement is seen (device becomes reachable) and
  auto-connects at that point.
- Keeps the connection open, feeding incoming MIDI/SysEx notifications
  through `ProtocolParser` and dispatching updates to entities.
- Exposes `async_connect()` for the manual "connect" service, and
  `async_disconnect()` for unload/cleanup.
"""
from __future__ import annotations

import logging
import time

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .ble import MarshallCodeBLEClient
from .const import SIGNAL_MARSHALL_CODE_UPDATE
from .protocol import (
    AmpState,
    ProtocolParser,
    request_active_preset,
    request_device_info,
)
from .scanners import log_scanners

_LOGGER = logging.getLogger(__name__)

type MarshallCodeConfigEntry = ConfigEntry["MarshallCodeCoordinator"]


class MarshallCodeCoordinator:
    """Owns the BLE connection and amp protocol state for one amp."""

    def __init__(self, hass: HomeAssistant, address: str) -> None:
        self.hass = hass
        self.address = address
        self.state = AmpState()
        self._parser = ProtocolParser(self.state)
        self._client: MarshallCodeBLEClient | None = None
        self._unregister_bluetooth_callback: callback | None = None
        self._connecting = False
        self.connected = False

    @property
    def signal(self) -> str:
        return SIGNAL_MARSHALL_CODE_UPDATE.format(address=self.address)

    async def async_setup(self) -> None:
        """Start listening for the amp's advertisements and connect to it
        immediately if it is already visible."""
        self._unregister_bluetooth_callback = bluetooth.async_register_callback(
            self.hass,
            self._async_seen,
            bluetooth.BluetoothCallbackMatcher(address=self.address),
            bluetooth.BluetoothScanningMode.ACTIVE,
        )
        service_info = bluetooth.async_last_service_info(
            self.hass, self.address, connectable=True
        )
        _LOGGER.info(
            "%s: setup; last connectable advertisement: %s",
            self.address,
            self._describe(service_info),
        )
        if service_info is not None:
            await self.async_connect()

    async def async_unload(self) -> None:
        if self._unregister_bluetooth_callback is not None:
            self._unregister_bluetooth_callback()
            self._unregister_bluetooth_callback = None
        await self.async_disconnect()

    @callback
    def _async_seen(
        self,
        service_info: bluetooth.BluetoothServiceInfoBleak,
        change: bluetooth.BluetoothChange,
    ) -> None:
        """Called by HA's bluetooth integration whenever an advertisement
        from this amp is observed."""
        _LOGGER.debug(
            "%s: advertisement %s", self.address, self._describe(service_info)
        )
        if self._client is not None:
            self._client.update_ble_device(service_info.device)
        if not self.connected and not self._connecting:
            self.hass.async_create_task(self.async_connect())

    async def async_connect(self) -> bool:
        """(Re)connect to the amp. Safe to call repeatedly (e.g. from the
        manual `connect` service) - a no-op if already connected/connecting.
        """
        if self.connected or self._connecting:
            return self.connected

        ble_device = bluetooth.async_ble_device_from_address(
            self.hass, self.address, connectable=True
        )
        if ble_device is None:
            any_info = bluetooth.async_last_service_info(
                self.hass, self.address, connectable=False
            )
            _LOGGER.info(
                "%s: no connectable scanner has the amp; "
                "last non-connectable advertisement: %s",
                self.address,
                self._describe(any_info),
            )
            log_scanners(self.hass, self.address, "amp not visible to connect")
            return False
        _LOGGER.info(
            "%s: connecting via %s",
            self.address,
            ble_device.details,
        )

        self._connecting = True
        try:
            if self._client is None:
                self._client = MarshallCodeBLEClient(
                    ble_device,
                    on_message=self._handle_message,
                    on_disconnect=self._handle_disconnect,
                )
            else:
                self._client.update_ble_device(ble_device)

            await self._client.connect()
            _LOGGER.info("%s: GATT connected", self.address)
            self.connected = True
            self._async_signal_update()

            await self._client.send(request_device_info())
            await self._client.send(request_active_preset())
            return True
        except Exception as err:
            _LOGGER.warning(
                "%s: failed to connect (%s: %s)",
                self.address,
                type(err).__name__,
                err,
                exc_info=_LOGGER.isEnabledFor(logging.DEBUG),
            )
            log_scanners(self.hass, self.address, "connect failed")
            self.connected = False
            self._async_signal_update()
            return False
        finally:
            self._connecting = False

    async def async_disconnect(self) -> None:
        if self._client is not None:
            await self._client.disconnect()
        self.connected = False

    def gatt_services(self) -> dict[str, list[str]]:
        return self._client.gatt_services() if self._client else {}

    @staticmethod
    def _describe(info: bluetooth.BluetoothServiceInfoBleak | None) -> str:
        if info is None:
            return "none"
        return (
            f"name={info.name!r} rssi={info.rssi} source={info.source} "
            f"connectable={info.connectable} uuids={info.service_uuids} "
            f"mfr={list(info.manufacturer_data)} "
            f"age={time.monotonic() - info.time:.0f}s"
        )

    @callback
    def _handle_disconnect(self) -> None:
        _LOGGER.info("%s: disconnected", self.address)
        self.connected = False
        self._async_signal_update()

    @callback
    def _handle_message(self, data: bytes) -> None:
        updated = self._parser.handle_message(data)
        if updated:
            self._async_signal_update()

    @callback
    def _async_signal_update(self) -> None:
        async_dispatcher_send(self.hass, self.signal)

    async def async_send(self, data: bytes, *, with_response: bool = True) -> None:
        """Send a raw command to the amp, used by entities (number/switch)."""
        if self._client is None or not self.connected:
            raise RuntimeError(f"{self.address}: amp is not connected")
        await self._client.send(data, with_response=with_response)


__all__ = ["MarshallCodeConfigEntry", "MarshallCodeCoordinator"]
