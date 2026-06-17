# Salesforce Dynamic Training Mock Pack

Reusable standalone HTML video templates for Salesforce-style release demos.

Current implemented demos:

```text
1. field_added_layout
2. update_record_object_action
3. create_record_object_action
4. screen_flow_action
```

## Folder structure

```text
sf_dynamic_training_mock_pack_actions/
├── catalog/
│   ├── action_types.json
│   ├── demo_registry.json
│   └── scene_primitives.json
├── config/
│   ├── field_added_demo.json
│   └── action_update_record_demo.json
├── docs/
│   └── ARCHITECTURE.md
├── outputs/
├── samples/
│   ├── account_opportunity_mock_data.json
│   ├── action_update_record_mock_data.json
│   └── bad_chars_torture_test.json
├── scripts/
│   ├── build_mock_video_html.py
│   ├── catalog_lint.py
│   └── smoke_test_bad_chars.py
└── templates/
    ├── dynamic_salesforce_mock_template.html
    └── action_update_record_template.html
```


## Create an org-aware scenario with the wizard

The new first-step workflow is story-first: choose the scenario, run-as alias, object, record, and fields, optionally refresh a compact org UI cache, then write a small config that the HTML builder already understands.

```bash
python3 scripts/org_ui_wizard.py \
  --target-org claytonboss+seoboss@gmail.com \
  --refresh-cache \
  --output config/wizard_demo.json

python3 scripts/build_mock_video_html.py \
  --config config/wizard_demo.json \
  --target-org claytonboss+seoboss@gmail.com \
  --output outputs/wizard_demo.html
```

A static front-end planner is also available at `web/ui-planner.html`; it produces the same universal scenario JSON shape for quick copy/paste iteration.

## Additional generic action-modal use cases

```bash
python3 scripts/build_mock_video_html.py \
  --config config/create_related_record_action_demo.json \
  --target-org claytonboss+seoboss@gmail.com \
  --output outputs/create_related_record_action_demo.html

python3 scripts/build_mock_video_html.py \
  --config config/screen_flow_action_demo.json \
  --target-org claytonboss+seoboss@gmail.com \
  --output outputs/screen_flow_action_demo.html
```

## Generate the new object action demo offline

```bash
cd sf_dynamic_training_mock_pack_actions
python3 scripts/build_mock_video_html.py \
  --sample samples/action_update_record_mock_data.json \
  --output outputs/action_update_record_demo_sample.html
```

Output duration:

```js
window.__VIDEO_DURATION_SECONDS = 48;
```

## Generate the object action demo from an org

```bash
sf org login web --alias my-sandbox

python3 scripts/build_mock_video_html.py \
  --config config/action_update_record_demo.json \
  --target-org my-sandbox \
  --output outputs/action_update_record_from_org.html \
  --snapshot-out outputs/action_update_record_snapshot.json
```

## Configure an update-record object action

Edit this file:

```text
config/action_update_record_demo.json
```

Core fields:

```json
{
  "demo": {
    "type": "update_record_object_action"
  },
  "record": {
    "object_api_name": "Opportunity",
    "record_id": "006000000000000AAA"
  },
  "action": {
    "api_name": "Mark_At_Risk",
    "label": "Mark At Risk",
    "fields": [
      {"field": "Opportunity.StageName", "after": "Negotiation/Review"},
      {"field": "Opportunity.NextStep", "after": "Schedule manager review"}
    ]
  }
}
```

Rules:

```text
- action.fields[].field must be a direct field on the configured object
- header_fields and record_fields may include relationship fields like Opportunity.Account.Name
- values are embedded through safe JSON, not executable JS strings
- apostrophes, quotes, <tags>, ampersands, and literal </script> text are escaped safely
```

## Catalog management

Validate the local catalog and registered demos:

```bash
python3 scripts/catalog_lint.py
```

The catalog gives you a clean growth path:

```text
catalog/action_types.json      # supported demo/action types
catalog/scene_primitives.json  # reusable UI animation steps
catalog/demo_registry.json     # known demos and their config/sample/template paths
```

This is the part that keeps future demos from becoming one-off spaghetti.

## Existing field-added demo still works

```bash
python3 scripts/build_mock_video_html.py \
  --config config/field_added_demo.json \
  --target-org my-sandbox \
  --output outputs/field_added_demo_from_org.html
```

Or offline:

```bash
python3 scripts/build_mock_video_html.py \
  --sample samples/account_opportunity_mock_data.json \
  --output outputs/field_added_demo_sample.html
```
