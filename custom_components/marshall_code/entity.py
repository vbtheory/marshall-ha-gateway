"""Common base entity for the Marshall CODE integration.

All entities are pushed to by `MarshallCodeCoordinator` via a per-amp
dispatcher signal (the amp keeps a single persistent BLE/GATT connection
open, unlike typical passive-advertisement BLE integrations, so there is no
`DataUpdateCoordinator`/polling involved).
"""
from __future__ import annotations

from homeassistant.core import callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity, EntityDescription

from .const import DOMAIN
from .coordinator import MarshallCodeCoordinator


class MarshallCodeEntity(Entity):
    """Base entity bound to one amp's coordinator."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self, coordinator: MarshallCodeCoordinator, description: EntityDescription
    ) -> None:
        self.coordinator = coordinator
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.address}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.address)},
            connections={(dr.CONNECTION_BLUETOOTH, coordinator.address)},
            manufacturer="Marshall",
            name="Marshall CODE",
        )

    @property
    def available(self) -> bool:
        return self.coordinator.connected

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, self.coordinator.signal, self._handle_update
            )
        )

    @callback
    def _handle_update(self) -> None:
        self.async_write_ha_state()


__all__ = ["MarshallCodeEntity"]
