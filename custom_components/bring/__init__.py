import asyncio
import logging
import random
from datetime import timedelta
from json.decoder import JSONDecodeError

import async_timeout
import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from h11 import Data
from homeassistant import core
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.exceptions import IntegrationError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import (DataUpdateCoordinator,
                                                      UpdateFailed)

from .const import DOMAIN, PLATFORMS
from .bring import BringApi

_LOGGER = logging.getLogger(__name__)

async def async_setup(_hass, _config):
    return True

async def async_setup_entry(hass: core.HomeAssistant, entry: ConfigEntry)-> bool:
    """Set up the platform."""

    username = entry.data.get(CONF_USERNAME)
    password = entry.data.get(CONF_PASSWORD)
    bring = BringApi(username, password)
    _LOGGER.debug(bring)
    await bring.login()
    bring_lists = await bring.get_lists()
    _LOGGER.debug(bring_lists)

    lists = []
    for bring_list in bring_lists:
        _LOGGER.debug(bring_list)
        list_name = bring_list.get("name")
        list_uuid = bring_list.get("listUuid")
        #coordinator = BringCoordinator(hass, bring, bring_list)
        lists.append({"name": list_name, "uuid": list_uuid})

    conf = {"username": username,
            "password": password,
            "lists": lists}

    coordinator = BringCoordinator(hass, conf, bring)
    await coordinator.async_config_entry_first_refresh()
    _LOGGER.debug("Coordinator Synced")
    hass.data[DOMAIN] = {
        "conf": conf,
        "coordinator": coordinator
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

class BringCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, conf, bring_api):
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=60),
        )
        self.conf = conf
        self.bring_api = bring_api

    async def _async_update_data(self):
        """Fetch data from API endpoint.

        This is the place to pre-process the data to lookup tables
        so entities can quickly look up their data.
        """
        bring_lists = self.conf["lists"]
        products = {}
        for bring_list in bring_lists:
            _LOGGER.debug(f"Selecting list {bring_list['name']}::{bring_list['uuid']}")
            #await self.bring_api.select_list(bring_list["name"])
            await self.bring_api.set_list(bring_list["name"], bring_list["uuid"])
            #bring_list_products = await self.bring_api.load_products()
            #bring_list_products = await self.bring_api.get_items_detail()
            #bring_list_products = await self.bring_api.get_current_items()
            bring_list_products = await self.bring_api.get_items()
            _LOGGER.debug(f"Found {bring_list_products} for  list {bring_list['name']}::{bring_list['uuid']}")

            products[bring_list["uuid"]] = bring_list_products
        _LOGGER.debug(f"Products: {products}")
        return products

