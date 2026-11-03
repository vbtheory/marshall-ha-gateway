"""Connection-state binary sensor for the Marshall CODE integration."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import MarshallCodeConfigEntry, MarshallCodeCoordinator
from .entity import MarshallCodeEntity

CONNECTED_DESCRIPTION = BinarySensorEntityDescription(
    key="connected",
    translation_key="connected",
    device_class=BinarySensorDeviceClass.CONNECTIVITY,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MarshallCodeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the connection-state binary sensor."""
    async_add_entities([MarshallCodeConnectedSensor(entry.runtime_data)])


class MarshallCodeConnectedSensor(MarshallCodeEntity, BinarySensorEntity):
    """Whether the amp is currently BLE-connected."""

    def __init__(self, coordinator: MarshallCodeCoordinator) -> None:
        super().__init__(coordinator, CONNECTED_DESCRIPTION)

    @property
    def available(self) -> bool:
        # Unlike other entities, this sensor is always "available" - it's
        # the thing that reports connectivity in the first place.
        return True

    @property
    def is_on(self) -> bool:
        return self.coordinator.connected


__all__ = ["async_setup_entry"]
