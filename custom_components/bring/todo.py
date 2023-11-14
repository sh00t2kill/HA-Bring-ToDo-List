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
        #self.todo_items = None
        self._uuids = []

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
        #self._items = []
        all_items = self.coordinator.data[self.uuid]
        for item in all_items["purchase"]:
            bring_item = BringTodoItem(self.coordinator.bring_api, item["name"], self.uuid)
            #These are active items -- lets do our thing
            if item['name'] not in self._processed_items:
                _LOGGER.debug(f"Found new item {item['name']}")
                _LOGGER.debug(bring_item)
                self._items.append(bring_item)
                self._processed_items.append(item["name"])
                self._uuids.append(bring_item.get_uid())
            elif item['name'] in self._processed_items and bring_item not in self._items:
                _LOGGER.debug("Existing item found, changing status to NEEDS_ACTION")
                bring_item.set_status(TodoItemStatus.COMPLETED)
                item_key = self._items.index(bring_item)
                self._items[item_key].set_status(TodoItemStatus.NEEDS_ACTION)
        for item in all_items["recently"]:
            bring_item = BringTodoItem(self.coordinator.bring_api, item["name"], self.uuid)
            bring_item.set_status(TodoItemStatus.COMPLETED)
            # These are completed items
            if item['name'] not in self._processed_items:
                #bring_item.set_status(TodoItemStatus.COMPLETED)
                self._items.append(bring_item)
                self._processed_items.append(item["name"])
                self._uuids.append(bring_item.get_uid())
            elif item['name'] in self._processed_items and bring_item not in self._items:
                _LOGGER.debug("Existing item found, changing status to COMPLETED")
                bring_item.set_status(TodoItemStatus.NEEDS_ACTION)
                item_key = self._items.index(bring_item)
                self._items[item_key].set_status(TodoItemStatus.COMPLETED)

        ## Now lets go the other way, remove HA list items that arent in Bring
        bring_todo_items = []
        for api_item in all_items["purchase"]:
            bring_todo_items.append(BringTodoItem(self.coordinator.bring_api, api_item["name"], self.uuid))
        for api_item in all_items["recently"]:
            todo_item = BringTodoItem(self.coordinator.bring_api, api_item["name"], self.uuid)
            todo_item.set_status(TodoItemStatus.COMPLETED)
            bring_todo_items.append(todo_item)

        for existing_ha_item in self._items:
            _LOGGER.debug(f"Checking if {existing_ha_item} no longer exists in Bring!")
            if existing_ha_item not in bring_todo_items:
                _LOGGER.debug(f"Removing {existing_ha_item.get_summary()} from list")
                self._items.remove(existing_ha_item)
                uid = existing_ha_item.get_uid()
                self._uuids.remove(uid)
                self._processed_items.remove(existing_ha_item.get_summary())
        return len(all_items["purchase"])

    async def async_create_todo_item(self, item):
        _LOGGER.debug(f"Creating new item {item.summary}")
        await self.coordinator.bring_api.set_list_by_uuid(self.uuid)
        await self.coordinator.bring_api.purchase_item(item.summary)
        bring_item = BringTodoItem(self.coordinator.bring_api, item.summary, self.uuid)
        self._items.append(bring_item)
        self._processed_items.append(item.summary)
        item_uid = bring_item.get_uid()
        self._uuids.append(item_uid)
        await self.coordinator.async_request_refresh()

    # Note: This removes it from the API, and lets the List state remove it from the lst
    async def async_delete_todo_items(self, uids: list[str]) -> None:
        for uid in uids:
            position = self._uuids.index(uid)
            item_name = self._processed_items[position]
            _LOGGER.debug(f"Removing {item_name}")
            await self.coordinator.bring_api.set_list_by_uuid(self.uuid)
            await self.coordinator.bring_api.remove_item(item_name)
            await self.coordinator.async_request_refresh()

    async def async_update_todo_item(self, item: TodoItem) -> None:
        _LOGGER.debug(f"Updating item {item.summary}")
        await self.coordinator.bring_api.set_list_by_uuid(self.uuid)
        search_bring_item = BringTodoItem(self.coordinator.bring_api, item.summary, self.uuid)
        if search_bring_item not in self._items:
            #Its been marked as completed, so lets update the status
            search_bring_item.set_status(TodoItemStatus.COMPLETED)
        item_key = self._items.index(search_bring_item)
        bring_item = self._items[item_key]
        await bring_item.update_status()
        await self.coordinator.async_request_refresh()


class BringTodoItem(TodoItem):
    def __init__(self, api, summary, list_uuid):
    #def __init__(self, name)
        #self.uid = f"bring_item_{summary.replace(' ', '_')}"
        #self.uid = uuid.uuid4()
        self.summary = summary
        self.status = TodoItemStatus.NEEDS_ACTION
        self.bring_api = api
        self.list_uuid = list_uuid

    @property
    def uid(self):
        return f"{self.list_uuid}_item_{self.summary.replace(' ', '_')}"

    def set_summary(self, summary):
        self.summary = summary

    def set_status(self, status):
        self.status = status

    def get_uid(self):
        return self.uid

    def get_summary(self):
        return self.summary

    def update_local_status(self):
        if self.status == TodoItemStatus.NEEDS_ACTION:
            self.status = TodoItemStatus.COMPLETED
        elif self.status == TodoItemStatus.COMPLETED:
            self.status = TodoItemStatus.NEEDS_ACTION

    async def update_status(self):
        if self.status == TodoItemStatus.NEEDS_ACTION:
            await self.bring_api.recent_item(self.summary)
            self.status = TodoItemStatus.COMPLETED
        elif self.status == TodoItemStatus.COMPLETED:
            self.status = TodoItemStatus.NEEDS_ACTION
            await self.bring_api.purchase_item(self.summary)

    async def purchase_item(self):
        self.bring_api.purchase_item(self.summary)

    @property
    def state(self):
        return self.status
