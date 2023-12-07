import asyncio
import logging
import uuid

from homeassistant.components.todo import TodoListEntity, TodoItem, TodoItemStatus, TodoListEntityFeature
from homeassistant.helpers.update_coordinator import (CoordinatorEntity,
                                                      DataUpdateCoordinator)
from homeassistant.util import slugify

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass, config, async_add_entities, discovery_info=None
):
    """Setup the ToDo platform."""
    lists = hass.data[DOMAIN]["conf"]["lists"]
    coordinator = hass.data[DOMAIN]["coordinator"]
    entities = []
    for list in lists:
        list_name = list["name"]
        list_uuid = list["uuid"]
        entities.append(BringTodoList(coordinator, list_uuid, list_name))

    async_add_entities(entities, True)

class BringTodoList(CoordinatorEntity, TodoListEntity):
    def __init__(self, coordinator, list_uuid, list_name):
        super().__init__(coordinator)
        self.uuid = list_uuid
        self._name = list_name
        self._attr_unique_id = slugify(list_name)
        self._attr_name = list_name
        self._attrs = {
            "uuid": self.uuid,
            "name": self.name
        }
        self._items = []
        self._processed_items = []

    @property
    def unique_id(self):
        """Return the unique ID of the sensor."""
        return self._attr_unique_id

    @property
    def name(self):
        return f"Bring Todo {self._name}"

    @property
    def extra_state_attributes(self):
        return self._attrs

    @property
    def supported_features(self):
        return TodoListEntityFeature.CREATE_TODO_ITEM | TodoListEntityFeature.DELETE_TODO_ITEM | TodoListEntityFeature.UPDATE_TODO_ITEM

    @property
    def todo_items(self):
        return self._items

    @property
    def state(self):
        _LOGGER.debug(f"Getting state for {self.name}")
        all_items = self.coordinator.data[self.uuid]
        for item in all_items["purchase"]:
            bring_item = BringTodoItem(self.coordinator.bring_api, item["name"], self.uuid)
            if item["specification"] and item["specification"] != "":
                bring_item.set_specification(item["specification"])
            #These are active items -- lets do our thing
            if item['name'] not in self._processed_items:
                _LOGGER.debug(f"Found new item {item['name']}")
                _LOGGER.debug(bring_item)
                self._items.append(bring_item)
                self._processed_items.append(item["name"])
            elif item['name'] in self._processed_items and bring_item not in self._items:
                _LOGGER.debug("Existing item found, changing status to NEEDS_ACTION")
                bring_item.set_status(TodoItemStatus.COMPLETED)
                item_key = self._items.index(bring_item)
                self._items[item_key].set_status(TodoItemStatus.NEEDS_ACTION)
        for item in all_items["recently"]:
            bring_item = BringTodoItem(self.coordinator.bring_api, item["name"], self.uuid)
            bring_item.set_status(TodoItemStatus.COMPLETED)
            if item["specification"] and item["specification"] != "":
                bring_item.set_specification(item["specification"])
            # These are completed items
            if item['name'] not in self._processed_items:
                self._items.append(bring_item)
                self._processed_items.append(item["name"])
            elif item['name'] in self._processed_items and bring_item not in self._items:
                _LOGGER.debug("Existing item found, changing status to COMPLETED")
                bring_item.set_status(TodoItemStatus.NEEDS_ACTION)
                item_key = self._items.index(bring_item)
                self._items[item_key].set_status(TodoItemStatus.COMPLETED)

        # Now lets go the other way, remove HA list items that aren't in Bring
        self.remove_outdated_list_items()
        return len(all_items["purchase"])

    async def async_remove_outdated_list_items(self):
        await asyncio.to_thread(self.remove_outdated_list_items)

    def remove_outdated_list_items(self):
        bring_todo_items = []
        all_items = self.coordinator.data[self.uuid]
        for api_item in all_items["purchase"]:
            todo_item = BringTodoItem(self.coordinator.bring_api, api_item["name"], self.uuid)
            if api_item["specification"] and api_item["specification"] != "":
                todo_item.set_specification(api_item["specification"])
            bring_todo_items.append(todo_item)
        for api_item in all_items["recently"]:
            todo_item = BringTodoItem(self.coordinator.bring_api, api_item["name"], self.uuid)
            if api_item["specification"] and api_item["specification"] != "":
                todo_item.set_specification(api_item["specification"])
            todo_item.set_status(TodoItemStatus.COMPLETED)
            bring_todo_items.append(todo_item)

        for existing_ha_item in self._items:
            #_LOGGER.debug(f"Checking if {existing_ha_item} no longer exists in Bring!")
            _LOGGER.debug(f"Checking if {existing_ha_item.get_summary()} {existing_ha_item.get_specification()} no longer exists in Bring!")
            if existing_ha_item not in bring_todo_items:
                _LOGGER.debug(f"Removing {existing_ha_item.get_summary()} from list")
                self._items.remove(existing_ha_item)
                self._processed_items.remove(existing_ha_item.get_summary())

    async def async_create_todo_item(self, item):
        await self.coordinator.bring_api.set_list_by_uuid(self.uuid)
        item_summary = item.summary
        item_specification = None
        if ":" in item.summary:
            split = item.summary.split(":")
            item_summary = split[0]
            item_specification = split[1]
        _LOGGER.debug(f"Creating new item with Summary: {item_summary}  Specification: {item_specification}")
        await self.coordinator.bring_api.purchase_item(item_summary, item_specification)
        bring_item = BringTodoItem(self.coordinator.bring_api, item_summary, self.uuid)
        if item_specification:
            bring_item.set_specification(item_specification)
        self._items.append(bring_item)
        self._processed_items.append(bring_item.get_summary())
        await self.coordinator.async_request_refresh()

    # Note: This removes it from the API, and lets the List state remove it from the lst
    async def async_delete_todo_items(self, uids: list[str]) -> None:
        for uid in uids:
            for item in self._items:
                item_uid = item.get_uid()
                if item_uid == uid:
                    item_summary = item.get_summary()
                    item_specification = item.get_specification()
                    break
            await self.coordinator.bring_api.set_list_by_uuid(self.uuid)
            await self.coordinator.bring_api.remove_item(item_summary, item_specification)
            await self.coordinator.async_request_refresh()
        _LOGGER.debug("Syncing removed items")
        await self.async_remove_outdated_list_items()

    def find_item_by_uid(self, uid):
        for item in self._items:
            item_uid = item.get_uid()
            if item_uid == uid:
                return item

    def find_item_position_by_uid(self, uid):
        for index, item in enumerate(self._items):
            item_uid = item.get_uid()
            if item_uid == uid:
                return index

    async def async_update_todo_item(self, item: TodoItem) -> None:
        _LOGGER.debug(f"Updating item {item.summary}")
        await self.coordinator.bring_api.set_list_by_uuid(self.uuid)
        search_bring_item = BringTodoItem(self.coordinator.bring_api, item.summary, self.uuid)
        if search_bring_item not in self._items:
            #Its been marked as completed, so lets update the status
            search_bring_item.set_status(TodoItemStatus.COMPLETED)
        if search_bring_item not in self._items:
            _LOGGER.debug(f"{item} has been changed, sync changes to Bring!")
            # The item has changed its name -- we need to deal with this!
            found_item_key = self.find_item_position_by_uid(item.uid)
            _LOGGER.debug(f"Found {item.uid} at position {found_item_key}")
            found_item = self._items[found_item_key]
            found_item_summary = found_item.get_summary()
            found_item_specification = found_item.get_specification()
            self._items[found_item_key].set_summary(item.summary)
            _LOGGER.debug(f"Removing old item {found_item_summary} from Bring!")
            await self.coordinator.bring_api.remove_item(found_item_summary, found_item_specification)
            if item.status == TodoItemStatus.NEEDS_ACTION:
                _LOGGER.debug("Create new item ready to purchase")
                await search_bring_item.purchase_item()
            else:
                _LOGGER.debug("Create new item in recent list")
                await search_bring_item.recent_item()
        else:
            item_key = self._items.index(search_bring_item)
            bring_item = self._items[item_key]
            await bring_item.update_status()
        await self.coordinator.async_request_refresh()



class BringTodoItem(TodoItem):
    def __init__(self, api, summary, list_uuid):
        self._summary = summary
        self.specification = None
        self.status = TodoItemStatus.NEEDS_ACTION
        self.bring_api = api
        self.list_uuid = list_uuid

    @property
    def uid(self):
        return f"{self.list_uuid}_item_{self.summary.replace(' ', '_')}"

    @property
    def summary(self):
        return f"{self._summary}:{self.specification}" if self.specification else self._summary

    def set_summary(self, summary):
        self._summary = summary

    def set_specification(self, specification):
        self.specification = specification

    def get_specification(self):
        return self.specification

    def set_status(self, status):
        self.status = status

    def get_uid(self):
        return self.uid

    def get_summary(self):
        return self._summary

    def update_local_status(self):
        if self.status == TodoItemStatus.NEEDS_ACTION:
            self.status = TodoItemStatus.COMPLETED
        elif self.status == TodoItemStatus.COMPLETED:
            self.status = TodoItemStatus.NEEDS_ACTION

    async def update_status(self):
        if self.status == TodoItemStatus.NEEDS_ACTION:
            await self.bring_api.recent_item(self._summary, self.specification)
            self.status = TodoItemStatus.COMPLETED
        elif self.status == TodoItemStatus.COMPLETED:
            self.status = TodoItemStatus.NEEDS_ACTION
            await self.bring_api.purchase_item(self._summary, self.specification)

    async def purchase_item(self):
        await self.bring_api.purchase_item(self._summary, self.specification)

    async def recent_item(self):
        await self.bring_api.purchase_item(self._summary, self.specification)

    @property
    def state(self):
        return self.status
