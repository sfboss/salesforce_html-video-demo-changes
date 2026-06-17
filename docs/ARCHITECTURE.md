# Dynamic Training Mock Architecture

## Core pattern

```text
Salesforce org/config
→ safe snapshot JSON
→ catalog-selected template
→ standalone HTML animation
→ MP4 capture pipeline
```

## Why this avoids recreating the wheel

Every demo is split into four reusable layers:

```text
catalog/action_types.json      # what kind of change is being demoed
catalog/scene_primitives.json  # reusable animation blocks
config/*.json                  # one small manifest per release/demo
samples/*.json                 # offline sample snapshots for fast iteration
templates/*.html               # renderer only; no org-specific hardcoding
```

## Current implemented demo types

```text
field_added_layout
update_record_object_action
```

## Next catalog additions

```text
create_record_object_action
screen_flow_action
url_action
global_action
quick_action_with_validation_error
related_list_button
list_view_mass_action
```
