from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DATA_CURRENT, DATA_DAY, DATA_NIGHT, DOMAIN, RECOMMENDATION_OPTIONS
from .coordinator import TogRatingCoordinator


@dataclass(frozen=True, kw_only=True)
class TogRecommendationEntityDescription(SensorEntityDescription):
    data_key: str


@dataclass(frozen=True, kw_only=True)
class TogScoreEntityDescription(SensorEntityDescription):
    data_key: str


TOG_SCORE_SENSORS: tuple[TogScoreEntityDescription, ...] = (
    TogScoreEntityDescription(
        key="current_tog",
        name="Current TOG",
        data_key=DATA_CURRENT,
    ),
    TogScoreEntityDescription(
        key="day_tog",
        name="Day TOG",
        data_key=DATA_DAY,
    ),
    TogScoreEntityDescription(
        key="night_tog",
        name="Night TOG",
        data_key=DATA_NIGHT,
    ),
)


RECOMMENDATION_SENSORS: tuple[TogRecommendationEntityDescription, ...] = (
    TogRecommendationEntityDescription(
        key="current_recommendation",
        name="Current Recommendation",
        data_key=DATA_CURRENT,
    ),
    TogRecommendationEntityDescription(
        key="day_recommendation",
        name="Day Recommendation",
        data_key=DATA_DAY,
    ),
    TogRecommendationEntityDescription(
        key="night_recommendation",
        name="Night Recommendation",
        data_key=DATA_NIGHT,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: TogRatingCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[SensorEntity] = [TogScoreSensor(coordinator, entry, description) for description in TOG_SCORE_SENSORS]
    entities.extend(TogRecommendationSensor(coordinator, entry, description) for description in RECOMMENDATION_SENSORS)
    async_add_entities(entities)


class TogBaseEntity(CoordinatorEntity[TogRatingCoordinator], SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator: TogRatingCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": entry.title,
            "manufacturer": "Custom",
            "model": "TOG Recommendation Engine",
        }


class TogScoreSensor(TogBaseEntity):
    _attr_suggested_display_precision = 1
    _attr_native_unit_of_measurement = "tog"

    def __init__(
        self,
        coordinator: TogRatingCoordinator,
        entry: ConfigEntry,
        description: TogScoreEntityDescription,
    ) -> None:
        super().__init__(coordinator, entry)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_name = description.name

    @property
    def native_value(self) -> float | None:
        snapshot = self.coordinator.data.get(self.entity_description.data_key)
        if snapshot is None:
            return None
        return snapshot.tog_rating

    @property
    def extra_state_attributes(self) -> dict[str, object] | None:
        snapshot = self.coordinator.data.get(self.entity_description.data_key)
        if snapshot is None:
            return None
        return snapshot.as_attributes()


class TogRecommendationSensor(TogBaseEntity):
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = RECOMMENDATION_OPTIONS

    def __init__(
        self,
        coordinator: TogRatingCoordinator,
        entry: ConfigEntry,
        description: TogRecommendationEntityDescription,
    ) -> None:
        super().__init__(coordinator, entry)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_name = description.name

    @property
    def native_value(self) -> str | None:
        snapshot = self.coordinator.data.get(self.entity_description.data_key)
        if snapshot is None:
            return None
        return snapshot.bucket

    @property
    def extra_state_attributes(self) -> dict[str, object] | None:
        snapshot = self.coordinator.data.get(self.entity_description.data_key)
        if snapshot is None:
            return None
        return snapshot.as_attributes()