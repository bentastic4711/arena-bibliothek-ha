"""Koordiniert den periodischen Abruf des Bibliothekskontos."""

from __future__ import annotations

import logging
from datetime import date, timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import ArenaAuthError, ArenaClient, ArenaError, Loan
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class ArenaCoordinator(DataUpdateCoordinator[list[Loan]]):
    """Haelt die Ausleihliste aktuell."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: ArenaClient,
        scan_interval: timedelta,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=scan_interval,
            config_entry=entry,
        )
        self.client = client

    async def _async_update_data(self) -> list[Loan]:
        try:
            return await self.hass.async_add_executor_job(self.client.fetch_loans)
        except ArenaAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except ArenaError as err:
            raise UpdateFailed(str(err)) from err

    # -- Auswertungen, die mehrere Entities brauchen --------------------

    @property
    def loans(self) -> list[Loan]:
        return self.data or []

    @property
    def next_due_date(self) -> date | None:
        dates = [loan.due_date for loan in self.loans if loan.due_date]
        return min(dates) if dates else None

    @property
    def overdue_count(self) -> int:
        return sum(1 for loan in self.loans if loan.overdue)
