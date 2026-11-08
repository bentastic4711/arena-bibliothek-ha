"""Einrichtung ueber die Benutzeroberflaeche."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
)

from .api import ArenaAuthError, ArenaClient, ArenaError
from .const import (
    CONF_BASE_URL,
    CONF_SCAN_HOURS,
    DEFAULT_BASE_URL,
    DEFAULT_SCAN_HOURS,
    DOMAIN,
    MAX_SCAN_HOURS,
    MIN_SCAN_HOURS,
)

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_BASE_URL, default=DEFAULT_BASE_URL): str,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)

HOURS_SELECTOR = NumberSelector(
    NumberSelectorConfig(
        min=MIN_SCAN_HOURS, max=MAX_SCAN_HOURS, step=1, mode=NumberSelectorMode.BOX
    )
)


class ArenaConfigFlow(ConfigFlow, domain=DOMAIN):
    """Fragt Basis-URL, Ausweisnummer und Passwort ab."""

    VERSION = 1

    async def _validate(self, data: Mapping[str, Any]) -> dict[str, str]:
        """Zugangsdaten einmal ausprobieren. Gibt Fehlerschluessel zurueck."""
        client = ArenaClient(
            data[CONF_BASE_URL], data[CONF_USERNAME], data[CONF_PASSWORD]
        )
        try:
            await self.hass.async_add_executor_job(client.fetch_loans)
        except ArenaAuthError:
            return {"base": "invalid_auth"}
        except ArenaError:
            return {"base": "cannot_connect"}
        return {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            await self.async_set_unique_id(
                f"{user_input[CONF_BASE_URL].rstrip('/')}::{user_input[CONF_USERNAME]}"
            )
            self._abort_if_unique_id_configured()

            errors = await self._validate(user_input)
            if not errors:
                return self.async_create_entry(
                    title=f"Bibliothek {user_input[CONF_USERNAME]}", data=user_input
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_SCHEMA, errors=errors
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Nach abgelehnter Anmeldung neues Passwort erfragen."""
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            data = {**entry.data, CONF_PASSWORD: user_input[CONF_PASSWORD]}
            errors = await self._validate(data)
            if not errors:
                return self.async_update_reload_and_abort(entry, data=data)

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_PASSWORD): str}),
            errors=errors,
            description_placeholders={"username": entry.data[CONF_USERNAME]},
        )

    @staticmethod
    @callback
    def async_get_options_flow(entry: ConfigEntry) -> OptionsFlow:
        return ArenaOptionsFlow()


class ArenaOptionsFlow(OptionsFlow):
    """Abrufintervall nachtraeglich aendern."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(
                data={CONF_SCAN_HOURS: int(user_input[CONF_SCAN_HOURS])}
            )

        current = self.config_entry.options.get(CONF_SCAN_HOURS, DEFAULT_SCAN_HOURS)
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {vol.Required(CONF_SCAN_HOURS, default=current): HOURS_SELECTOR}
            ),
        )
