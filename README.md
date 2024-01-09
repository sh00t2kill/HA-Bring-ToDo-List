[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)

# Home Assistant Todo List with Bring integration.

A custom implementation of Home Assistant's new ToDo List that synchronises with Bring Shopping List (https://getbring.com/#!/app).
The original component overrode the core shopping_list integration --- this uses the new Todo list functionality, creating a todo list for each shopping list created in Bring!
## Installation

### HACS

Add the repository url to your custom repositories in HACS: https://github.com/sh00t2kill/HA-Bring-ToDo-List
and install `Bring Todo List`.



## Usage

Add the `Bring Todo List` integration from the HA Integrations page, and enter your credentials, along with your locale.
<br>The locale is used to translate items from german into your chosen language. It defaults to en-US, which is the most complete english translation list. 
<br>If you are unsure as to what to put here, you can test at this public URL: https://web.getbring.com/locale/articles.<<LOCALE_STRING_GOES_HERE>.json
<br>Example: Italian: https://web.getbring.com/locale/articles.it-IT.json -- the locale value should be it-IT


## Force Sync
A service exists to force a sync between HA, called `bring.force_bring_sync`
It requires a todo entity, but will sync ALL todo entities with Bring lists.

```
service: bring.force_bring_sync
data: {}
target:
  entity_id: todo.bring_todo_home
```
