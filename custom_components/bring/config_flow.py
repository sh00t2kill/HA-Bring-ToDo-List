"""Config flow to configure."""
from __future__ import annotations

import logging

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from .const import CONF_LOCALE, DEFAULT_LOCALE, DEFAULT_NAME, DOMAIN

_LOGGER = logging.getLogger(__name__)

@config_entries.HANDLERS.register(DOMAIN)
class LinktapFlowHandler(config_entries.ConfigFlow):

    VERSION = 1
    def __init__(self):
        super().__init__()

    async def async_step_user(self, user_input=None):
        """Handle a flow start."""
        _LOGGER.debug(f"Starting async_step_user of {DEFAULT_NAME}")

        errors = None

        if user_input is not None:
            return self.async_create_entry(title=DEFAULT_NAME, data=user_input)

        new_user_input = {
            vol.Required(CONF_USERNAME): str,
            vol.Required(CONF_PASSWORD): str,
            vol.Required(CONF_LOCALE, default=DEFAULT_LOCALE): str,
        }

        schema = vol.Schema(new_user_input)

        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)
