"""BlueZ helpers for dual-mode amps.

The amp uses one address for classic audio (BR/EDR) and BLE GATT control.
BlueZ picks the bearer inside `Device1.Connect()` and often chooses BR/EDR,
which yields `br-connection-*` errors and no GATT services. BlueZ 5.80+ has
an experimental `PreferredBearer` property on `Device1` that forces LE.
"""
from __future__ import annotations

import logging

_LOGGER = logging.getLogger(__name__)

BLUEZ_SERVICE = "org.bluez"
DEVICE_IFACE = "org.bluez.Device1"


async def async_prefer_le_bearer(address: str) -> bool:
    """Set `PreferredBearer=le` on every BlueZ device object for `address`.

    Returns True when at least one device was set (or already set). Silently
    does nothing on BlueZ without the property, on non-Linux hosts, or when
    the device is not known to BlueZ yet; it never raises.
    """
    try:
        from dbus_fast import BusType, Variant
        from dbus_fast.aio import MessageBus
    except ImportError:
        _LOGGER.debug("dbus_fast unavailable; cannot set PreferredBearer")
        return False

    bus = None
    try:
        bus = await MessageBus(bus_type=BusType.SYSTEM).connect()
        introspection = await bus.introspect(BLUEZ_SERVICE, "/")
        manager = bus.get_proxy_object(
            BLUEZ_SERVICE, "/", introspection
        ).get_interface("org.freedesktop.DBus.ObjectManager")
        objects = await manager.call_get_managed_objects()

        done = False
        for path, interfaces in objects.items():
            props = interfaces.get(DEVICE_IFACE)
            if props is None:
                continue
            if str(props["Address"].value).upper() != address.upper():
                continue
            if "PreferredBearer" not in props:
                _LOGGER.debug(
                    "%s: %s has no PreferredBearer (BlueZ < 5.80, device not "
                    "dual-mode yet, or Experimental off)",
                    address,
                    path,
                )
                continue
            if props["PreferredBearer"].value == "le":
                done = True
                continue
            if props["Connected"].value:
                _LOGGER.debug("%s: %s connected; not changing bearer", address, path)
                continue
            device = bus.get_proxy_object(
                BLUEZ_SERVICE, path, await bus.introspect(BLUEZ_SERVICE, path)
            )
            await device.get_interface("org.freedesktop.DBus.Properties").call_set(
                DEVICE_IFACE, "PreferredBearer", Variant("s", "le")
            )
            _LOGGER.info("%s: set BlueZ PreferredBearer=le on %s", address, path)
            done = True
        return done
    except Exception as err:  # noqa: BLE001
        _LOGGER.debug("%s: could not set PreferredBearer: %s", address, err)
        return False
    finally:
        if bus is not None:
            bus.disconnect()
