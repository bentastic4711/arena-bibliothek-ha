"""Sensoren: Anzahl Ausleihen, naechste Rueckgabe, ueberfaellige Medien."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import ArenaCoordinator
from .entity import ArenaEntity


@dataclass(frozen=True, kw_only=True)
class ArenaSensorDescription(SensorEntityDescription):
    """Beschreibt einen Sensor samt Wert- und Attributfunktion."""

    value_fn: Callable[[ArenaCoordinator], Any]
    attributes_fn: Callable[[ArenaCoordinator], dict[str, Any]] | None = None


def _loan_attributes(coordinator: ArenaCoordinator) -> dict[str, Any]:
    loans = sorted(coordinator.loans, key=lambda loan: loan.due_date or date.max)
    return {
        "loans": [loan.as_dict() for loan in loans],
        "renewable_count": sum(1 for loan in loans if loan.renewable),
        "titles": [loan.title for loan in loans],
    }


def _next_due_attributes(coordinator: ArenaCoordinator) -> dict[str, Any]:
    due = coordinator.next_due_date
    if due is None:
        return {"days_left": None, "titles": [], "all_renewable": None}
    affected = [loan for loan in coordinator.loans if loan.due_date == due]
    return {
        "days_left": (due - date.today()).days,
        "titles": [loan.title for loan in affected],
        "all_renewable": all(loan.renewable for loan in affected),
    }


SENSORS: tuple[ArenaSensorDescription, ...] = (
    ArenaSensorDescription(
        key="loans",
        translation_key="loans",
        icon="mdi:bookshelf",
        native_unit_of_measurement="Medien",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda coordinator: len(coordinator.loans),
        attributes_fn=_loan_attributes,
    ),
    ArenaSensorDescription(
        key="next_due_date",
        translation_key="next_due_date",
        icon="mdi:calendar-clock",
        device_class=SensorDeviceClass.DATE,
        value_fn=lambda coordinator: coordinator.next_due_date,
        attributes_fn=_next_due_attributes,
    ),
    ArenaSensorDescription(
        key="days_until_due",
        translation_key="days_until_due",
        icon="mdi:timer-sand",
        native_unit_of_measurement="d",
        value_fn=lambda coordinator: (
            None
            if coordinator.next_due_date is None
            else (coordinator.next_due_date - date.today()).days
        ),
    ),
    ArenaSensorDescription(
        key="overdue",
        translation_key="overdue",
        icon="mdi:alert-circle-outline",
        native_unit_of_measurement="Medien",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda coordinator: coordinator.overdue_count,
        attributes_fn=lambda coordinator: {
            "titles": [loan.title for loan in coordinator.loans if loan.overdue]
        },
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: ArenaCoordinator = entry.runtime_data
    async_add_entities(
        ArenaSensor(coordinator, entry, description) for description in SENSORS
    )


class ArenaSensor(ArenaEntity, SensorEntity):
    """Ein einzelner Kontowert."""

    entity_description: ArenaSensorDescription

    def __init__(
        self,
        coordinator: ArenaCoordinator,
        entry: ConfigEntry,
        description: ArenaSensorDescription,
    ) -> None:
        super().__init__(coordinator, entry, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> Any:
        return self.entity_description.value_fn(self.coordinator)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self.entity_description.attributes_fn is None:
            return None
        return self.entity_description.attributes_fn(self.coordinator)
