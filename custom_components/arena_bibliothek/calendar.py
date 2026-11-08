"""Kalender mit einem ganztaegigen Eintrag je Rueckgabedatum."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .api import Loan
from .coordinator import ArenaCoordinator
from .entity import ArenaEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: ArenaCoordinator = entry.runtime_data
    async_add_entities([ArenaCalendar(coordinator, entry)])


class ArenaCalendar(ArenaEntity, CalendarEntity):
    """Rueckgabefristen als Kalender, gruppiert nach Datum."""

    _attr_translation_key = "due_dates"
    _attr_icon = "mdi:calendar-check"

    def __init__(self, coordinator: ArenaCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "due_dates")

    @staticmethod
    def _event(due: date, loans: list[Loan]) -> CalendarEvent:
        titles = ", ".join(loan.title for loan in loans)
        summary = (
            f"{len(loans)} Medien zurückgeben" if len(loans) > 1 else loans[0].title
        )
        description_lines = [
            f"- {loan.title}"
            + (f" ({loan.media_type})" if loan.media_type else "")
            + (
                f", noch {loan.renewals_left} Verlängerungen"
                if loan.renewals_left is not None
                else ", nicht verlängerbar"
            )
            for loan in loans
        ]
        return CalendarEvent(
            summary=summary,
            start=due,
            end=due + timedelta(days=1),
            description="\n".join(description_lines) or titles,
        )

    def _events(self) -> list[CalendarEvent]:
        grouped: dict[date, list[Loan]] = {}
        for loan in self.coordinator.loans:
            if loan.due_date is not None:
                grouped.setdefault(loan.due_date, []).append(loan)
        return [self._event(due, loans) for due, loans in sorted(grouped.items())]

    @property
    def event(self) -> CalendarEvent | None:
        """Naechste anstehende Rueckgabe."""
        today = dt_util.now().date()
        upcoming = [event for event in self._events() if event.end > today]
        return upcoming[0] if upcoming else None

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        start = dt_util.as_local(start_date).date()
        end = dt_util.as_local(end_date).date()
        return [
            event for event in self._events() if event.start < end and event.end > start
        ]
