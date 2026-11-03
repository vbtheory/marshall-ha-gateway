"""Pre-flight and live connection checks used by the config flow."""
from __future__ import annotations

import asyncio
import logging

from bleak.exc import BleakCharacteristicNotFoundError
from homeassistant.components import bluetooth
from homeassistant.core import HomeAssistant

from .ble import MarshallCodeBLEClient
from .protocol import request_device_info
from .scanners import log_scanners

_LOGGER = logging.getLogger(__name__)

RESPONSE_TIMEOUT = 8
CONNECT_TIMEOUT = 45

ERROR_NOT_VISIBLE = "not_visible"
ERROR_NOT_CONNECTABLE = "not_connectable"
ERROR_CANNOT_CONNECT = "cannot_connect"
ERROR_MISSING_CHARACTERISTIC = "missing_characteristic"
ERROR_NO_RESPONSE = "no_response"


async def async_verify_amp(hass: HomeAssistant, address: str) -> str | None:
    """Connect to the amp and confirm it answers protocol requests.

    Returns None on success, otherwise an error key from strings.json.
    """
    ble_device = bluetooth.async_ble_device_from_address(
        hass, address, connectable=True
    )
    if ble_device is None:
        log_scanners(hass, address, "setup check: no connectable scanner has the amp")
        if bluetooth.async_last_service_info(hass, address, connectable=False):
            return ERROR_NOT_CONNECTABLE
        return ERROR_NOT_VISIBLE

    reply = asyncio.Event()
    client = MarshallCodeBLEClient(
        ble_device,
        on_message=lambda _data: reply.set(),
        on_disconnect=lambda: None,
    )
    try:
        async with asyncio.timeout(CONNECT_TIMEOUT):
            await client.connect()
        await client.send(request_device_info())
        async with asyncio.timeout(RESPONSE_TIMEOUT):
            await reply.wait()
    except BleakCharacteristicNotFoundError:
        log_scanners(hass, address, "setup check: characteristic missing")
        return ERROR_MISSING_CHARACTERISTIC
    except TimeoutError:
        log_scanners(hass, address, "setup check: timed out")
        return ERROR_NO_RESPONSE if client.is_connected else ERROR_CANNOT_CONNECT
    except Exception as err:  # noqa: BLE001
        _LOGGER.warning(
            "%s: setup verification failed (%s: %s)",
            address,
            type(err).__name__,
            err,
        )
        log_scanners(hass, address, "setup check: connect failed")
        return ERROR_CANNOT_CONNECT
    finally:
        await client.disconnect()
    return None
