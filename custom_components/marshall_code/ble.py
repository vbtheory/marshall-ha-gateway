"""Low-level BLE client for Marshall CODE amps.

Wraps `bleak`/`bleak-retry-connector` to replicate the connect/subscribe
handshake and SysEx fragment-reassembly logic from the official app's
`BTLE.java`/`AmpManager.java`.
"""
from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from bleak.backends.device import BLEDevice
from bleak.exc import BleakCharacteristicNotFoundError, BleakError
from bleak_retry_connector import BleakClientWithServiceCache, establish_connection

from .bluez import async_prefer_le_bearer
from .bond import async_bond_classic
from .const import (
    MIDI_SERVICE_UUID,
    NOTIFY_UUID,
    WRITE_WITH_RESPONSE_UUID,
    WRITE_WITHOUT_RESPONSE_UUID,
)
from .protocol import SYSEX_START, is_sysex_complete

if TYPE_CHECKING:
    from bleak.backends.characteristic import BleakGATTCharacteristic

_LOGGER = logging.getLogger(__name__)

DISCONNECT_DELAY = 10

MessageCallback = Callable[[bytes], None]
DisconnectCallback = Callable[[], None]


class _SourceFilteredManager:
    """Proxy for HA's Bluetooth manager exposing only one scanner's devices."""

    def __init__(self, manager: Any, source: str) -> None:
        self._manager = manager
        self._source = source

    def async_scanner_devices_by_address(
        self, address: str, connectable: bool
    ) -> list[Any]:
        return [
            device
            for device in self._manager.async_scanner_devices_by_address(
                address, connectable
            )
            if device.scanner.source == self._source
        ]

    def __getattr__(self, name: str) -> Any:
        return getattr(self._manager, name)


def _pinned_client_class(source: str | None) -> type[BleakClientWithServiceCache]:
    """Client class that only connects through the scanner/proxy `source`.

    HA's client wrapper normally picks the best scanner itself; this narrows
    that choice to the one the user selected.
    """
    if source is None:
        return BleakClientWithServiceCache

    class PinnedClient(BleakClientWithServiceCache):
        def _async_get_best_available_backend_and_device(self, manager: Any) -> Any:
            return super()._async_get_best_available_backend_and_device(
                _SourceFilteredManager(manager, source)
            )

    return PinnedClient


class MarshallCodeBLEClient:
    """Maintains a persistent GATT connection to a single amp."""

    def __init__(
        self,
        ble_device: BLEDevice,
        on_message: MessageCallback,
        on_disconnect: DisconnectCallback | None = None,
        source: str | None = None,
        pair: bool = False,
    ) -> None:
        self._pair = pair
        self._bleak_pair = pair
        self._source = source
        self._ble_device = ble_device
        self._on_message = on_message
        self._on_disconnect = on_disconnect
        self._client: BleakClientWithServiceCache | None = None
        self._sysex_buffer = bytearray()

    @property
    def address(self) -> str:
        return self._ble_device.address

    @property
    def is_connected(self) -> bool:
        return bool(self._client and self._client.is_connected)

    def gatt_services(self) -> dict[str, list[str]]:
        """Service UUID -> characteristic UUIDs of the live connection."""
        if self._client is None or not self._client.is_connected:
            return {}
        return {
            svc.uuid: [c.uuid for c in svc.characteristics]
            for svc in self._client.services
        }

    def update_ble_device(self, ble_device: BLEDevice) -> None:
        """Update the cached BLEDevice (address/rssi may change between
        advertisements seen by Home Assistant's bluetooth scanner)."""
        self._ble_device = ble_device

    async def connect(self) -> None:
        """Connect, discover services, and subscribe to notifications."""
        if self.is_connected:
            return

        # Bond over classic Bluetooth through the local BlueZ (needed before
        # BlueZ will use the amp's BLE service); if that isn't possible
        # (e.g. an ESPHome proxy), fall back to bleak's pairing.
        self._bleak_pair = self._pair
        if self._pair and await async_bond_classic(self.address):
            self._bleak_pair = False
        try:
            await self._connect_and_subscribe(use_cache=True)
        except BleakCharacteristicNotFoundError:
            _LOGGER.warning(
                "%s: notify characteristic missing, retrying with fresh service "
                "discovery",
                self.address,
            )
            await self.disconnect()
            await self._connect_and_subscribe(use_cache=False)

    async def _connect_and_subscribe(self, *, use_cache: bool) -> None:
        await async_prefer_le_bearer(self.address)
        client = await establish_connection(
            _pinned_client_class(self._source),
            self._ble_device,
            self._ble_device.name or self.address,
            disconnected_callback=self._handle_client_disconnect,
            use_services_cache=use_cache,
            pair=self._bleak_pair,
            ble_device_callback=lambda: self._ble_device,
        )
        self._client = client

        self._sysex_buffer = bytearray()
        try:
            await client.start_notify(NOTIFY_UUID, self._notification_handler)
        except BleakCharacteristicNotFoundError:
            _LOGGER.warning(
                "%s: GATT services (cache=%s): %s",
                self.address,
                use_cache,
                {
                    svc.uuid: [c.uuid for c in svc.characteristics]
                    for svc in client.services
                },
            )
            raise
        _LOGGER.debug("%s: connected and subscribed", self.address)

    def _handle_client_disconnect(self, _client: BleakClientWithServiceCache) -> None:
        _LOGGER.debug("%s: disconnected", self.address)
        if self._on_disconnect is not None:
            self._on_disconnect()

    async def disconnect(self) -> None:
        if self._client is not None:
            await self._client.disconnect()
        self._client = None

    def _notification_handler(
        self, _characteristic: BleakGATTCharacteristic, data: bytearray
    ) -> None:
        payload = bytes(data)
        if not payload:
            return

        if payload[0] == SYSEX_START or self._sysex_buffer:
            self._sysex_buffer.extend(payload)
            if is_sysex_complete(bytes(self._sysex_buffer)):
                message = bytes(self._sysex_buffer)
                self._sysex_buffer = bytearray()
                self._on_message(message)
            return

        # Plain 2-3 byte MIDI message, passed straight through.
        self._on_message(payload)

    async def send(self, data: bytes, *, with_response: bool = True) -> None:
        if self._client is None or not self._client.is_connected:
            raise BleakError(f"{self.address}: not connected")
        uuid = WRITE_WITH_RESPONSE_UUID if with_response else WRITE_WITHOUT_RESPONSE_UUID
        await self._client.write_gatt_char(uuid, data, response=with_response)


__all__ = ["MIDI_SERVICE_UUID", "MarshallCodeBLEClient"]
