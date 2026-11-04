"""Bond with the amp over classic Bluetooth through BlueZ's D-Bus API.

The amp only lets BlueZ use its BLE control service after it has been bonded
over classic Bluetooth once (confirmed manually with `bluetoothctl`):

    scan (classic) -> find device -> trust -> pair (confirm) -> prefer LE

This module performs that sequence. It registers a temporary BlueZ agent that
accepts the numeric-comparison confirmation and service authorisation, which
is what answering "yes" in `bluetoothctl` does. Everything is best effort and
never raises; callers fall back to the normal BLE pairing path.

(No `from __future__ import annotations` here: dbus_fast reads the string
annotations on the agent methods as D-Bus signatures.)
"""
import asyncio
import contextlib
import logging

from dbus_fast import BusType, Variant
from dbus_fast.aio import MessageBus
from dbus_fast.service import ServiceInterface, method

_LOGGER = logging.getLogger(__name__)

BLUEZ = "org.bluez"
ADAPTER_IFACE = "org.bluez.Adapter1"
DEVICE_IFACE = "org.bluez.Device1"
AGENT_MANAGER_IFACE = "org.bluez.AgentManager1"
PROPS_IFACE = "org.freedesktop.DBus.Properties"
AGENT_PATH = "/marshall_code/agent"

DISCOVERY_TIMEOUT = 30
PAIR_TIMEOUT = 45


class _AcceptAgent(ServiceInterface):
    """BlueZ agent that accepts every confirmation request."""

    def __init__(self) -> None:
        super().__init__("org.bluez.Agent1")

    @method(name="Release")
    def release(self):
        return

    @method(name="RequestConfirmation")
    def request_confirmation(self, device: "o", passkey: "u"):  # noqa: F821
        _LOGGER.debug("Accepting pairing confirmation for %s", device)

    @method(name="RequestAuthorization")
    def request_authorization(self, device: "o"):  # noqa: F821
        return

    @method(name="AuthorizeService")
    def authorize_service(self, device: "o", uuid: "s"):  # noqa: F821
        return

    @method(name="RequestPinCode")
    def request_pin_code(self, device: "o") -> "s":  # noqa: F821
        return "0000"

    @method(name="RequestPasskey")
    def request_passkey(self, device: "o") -> "u":  # noqa: F821
        return 0

    @method(name="DisplayPasskey")
    def display_passkey(
        self, device: "o", passkey: "u", entered: "q"  # noqa: F821
    ):
        return

    @method(name="DisplayPinCode")
    def display_pin_code(self, device: "o", pincode: "s"):  # noqa: F821
        return

    @method(name="Cancel")
    def cancel(self):
        return


async def _objects(bus: MessageBus) -> dict:
    introspection = await bus.introspect(BLUEZ, "/")
    manager = bus.get_proxy_object(BLUEZ, "/", introspection).get_interface(
        "org.freedesktop.DBus.ObjectManager"
    )
    return await manager.call_get_managed_objects()


def _find_device(objects: dict, address: str) -> tuple[str, dict] | None:
    for path, interfaces in objects.items():
        props = interfaces.get(DEVICE_IFACE)
        if props and str(props["Address"].value).upper() == address.upper():
            return path, props
    return None


async def _iface(bus: MessageBus, path: str, name: str):
    introspection = await bus.introspect(BLUEZ, path)
    return bus.get_proxy_object(BLUEZ, path, introspection).get_interface(name)


async def _set_property(bus: MessageBus, path: str, prop: str, signature: str, value):
    props = await _iface(bus, path, PROPS_IFACE)
    await props.call_set(DEVICE_IFACE, prop, Variant(signature, value))


async def _discover_classic(bus: MessageBus, address: str) -> tuple[str, dict] | None:
    """Run a BR/EDR discovery on every adapter until the amp shows up."""
    adapters = [
        path
        for path, interfaces in (await _objects(bus)).items()
        if ADAPTER_IFACE in interfaces
    ]
    started = []
    try:
        for path in adapters:
            adapter = await _iface(bus, path, ADAPTER_IFACE)
            try:
                await adapter.call_set_discovery_filter(
                    {"Transport": Variant("s", "bredr")}
                )
                await adapter.call_start_discovery()
                started.append(adapter)
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("%s: classic discovery on %s failed: %s", address, path, err)
        for _ in range(DISCOVERY_TIMEOUT):
            found = _find_device(await _objects(bus), address)
            if found and "Class" in found[1]:
                return found
            await asyncio.sleep(1)
        return None
    finally:
        for adapter in started:
            with contextlib.suppress(Exception):
                await adapter.call_stop_discovery()


async def async_bond_classic(address: str) -> bool:
    """Bond with the amp over classic Bluetooth, then prefer the LE bearer.

    Returns True if the amp is bonded afterwards (including "already was").
    The amp must be in pairing mode and not connected to anything else.
    """
    bus = None
    agent_registered = False
    try:
        bus = await MessageBus(bus_type=BusType.SYSTEM).connect()
        found = _find_device(await _objects(bus), address)
        if found and found[1].get("Paired") and found[1]["Paired"].value:
            _LOGGER.debug("%s: already bonded", address)
            return True

        if found is None or "Class" not in found[1]:
            _LOGGER.info("%s: scanning classic Bluetooth for the amp", address)
            found = await _discover_classic(bus, address)
        if found is None:
            _LOGGER.warning(
                "%s: amp not found by classic scan; is it in pairing mode?", address
            )
            return False
        path, props = found

        bus.export(AGENT_PATH, _AcceptAgent())
        manager = await _iface(bus, "/org/bluez", AGENT_MANAGER_IFACE)
        await manager.call_register_agent(AGENT_PATH, "DisplayYesNo")
        agent_registered = True
        await manager.call_request_default_agent(AGENT_PATH)

        await _set_property(bus, path, "Trusted", "b", True)
        if "PreferredBearer" in props:
            await _set_property(bus, path, "PreferredBearer", "s", "bredr")

        device = await _iface(bus, path, DEVICE_IFACE)
        _LOGGER.info("%s: pairing over classic Bluetooth", address)
        async with asyncio.timeout(PAIR_TIMEOUT):
            await device.call_pair()

        if "PreferredBearer" in props:
            await _set_property(bus, path, "PreferredBearer", "s", "le")
        _LOGGER.info("%s: bonded over classic Bluetooth", address)
        return True
    except Exception as err:  # noqa: BLE001
        _LOGGER.warning("%s: classic bonding failed: %s: %s", address, type(err).__name__, err)
        return False
    finally:
        if bus is not None:
            if agent_registered:
                with contextlib.suppress(Exception):
                    manager = await _iface(bus, "/org/bluez", AGENT_MANAGER_IFACE)
                    await manager.call_unregister_agent(AGENT_PATH)
            bus.disconnect()
